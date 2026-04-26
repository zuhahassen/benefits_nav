from datetime import datetime
from uuid import uuid4
import json

from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents.experimental.chat_agent.protocol import build_llm_message_history
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

# ── Bento: Benefits Navigator Orchestrator ───────────────────────────────────
# Entry point for all user interactions. Routes to sub-agents:
#   - EligibilityAgent: determines which benefits user qualifies for
#   - ApplicationAgent: personalized application guidance per benefit
#   - PolicyWatcherAgent: surfaces relevant policy changes
#   - NavigatorAgent: complex cases, denials, appeals, mixed-status households

ELIGIBILITY_AGENT_ADDRESS = "agent1qfqwm8m0fxaehg2denssmehr32etc6tyjl4079fnfy5cqnyzrt2auynq9u3"
APPLICATION_AGENT_ADDRESS = "agent1qv3jz94qczu93eyvuunf0ma6wumg4h4jta6prxefd7rt3r3nmktdzu9fhg6"
POLICY_WATCHER_AGENT_ADDRESS = "agent1qd8ks3rlfpa4rcuy803ar3kdkk7lpye3td882e95juqx7fylw8jms46k5ud"
NAVIGATOR_AGENT_ADDRESS = "agent1qvshm6xkg0tpxga0xz3el0zlpa3rdeyytxttv6zfqjx9dp3s6pvc7dvjx5e"

SYSTEM_PROMPT = """You are Bento, a warm and trusted US government benefits navigator.
You help low-income individuals and families discover SNAP, Medicaid, TANF, WIC, and LIHEAP benefits.

Your role is to:
1. Greet users warmly and explain what you do
2. Collect their household profile through natural conversation
3. Once you have enough info, summarize what you've learned and confirm before checking eligibility
4. Present eligibility results in a clear, encouraging way
5. Guide them to apply for matched benefits

Information you need to collect (conversationally, not all at once):
- State of residence
- Household size (who they live and eat with)
- Ages of household members
- Gross monthly income (approximate ranges are fine)
- Any special circumstances: pregnancy, postpartum, breastfeeding, child under 5, disability
- Current benefits (SNAP, Medicaid, TANF — helps with WIC categorical eligibility)
- Employment situation
- Immigration/residency status (handle with extreme care — always show privacy note)

Privacy note to show when asking about immigration:
"This is only used to find benefits you qualify for. It is never stored or shared with any government agency. You can skip this question."

When you have: state, household_size, monthly_income, and ages — you have enough to run eligibility.
Build a profile JSON internally and tell the user you're checking their eligibility.

Tone: Warm, clear, non-judgmental. 6th grade reading level. Never overwhelming.
"""

# ── Lookup tables matching what page.tsx sends ───────────────────────────────
AGE_MAP = {
    "Under 1": 0, "1-4": 2, "5-12": 8,
    "13-17": 15, "18-25": 21, "26-40": 32,
    "41-59": 45, "60+": 65
}

EMPLOYMENT_MAP = {
    "Working full-time (35+ hours/week)": "full_time",
    "Working part-time (under 35 hours/week)": "part_time",
    "Currently unemployed / looking for work": "unemployed",
    "Unable to work due to disability or caregiving": "unable_to_work",
    "Self-employed": "self_employed",
    "Student": "student",
    "Retired": "retired",
}

IMMIGRATION_MAP = {
    "U.S. citizen or U.S. national": "citizen",
    "Lawful Permanent Resident (Green Card holder)": "lpr",
    "DACA (Deferred Action for Childhood Arrivals)": "daca",
    "Refugee, asylee, or humanitarian status": "refugee",
    "Other visa or immigration status": "visa",
    "Prefer not to say / not sure": "unknown",
}


def build_profile(form_data: dict) -> dict:
    """
    Convert intake form answers from Next.js into a structured UserProfile.
    """
    raw_ages = form_data.get("member_ages", [])
    numeric_ages = [AGE_MAP.get(a, 25) for a in raw_ages]

    health_flags = form_data.get("health_flags", [])
    is_pregnant = "Currently pregnant" in health_flags
    is_postpartum = "Postpartum (up to 6 months after pregnancy)" in health_flags
    is_breastfeeding = "Currently breastfeeding an infant under 1 year old" in health_flags
    has_disability = "Has a physical or mental disability that limits daily activities" in health_flags

    current_benefits = form_data.get("current_benefits", [])
    receives_snap = "SNAP / Food Stamps / EBT" in current_benefits
    receives_medicaid = "Medicaid or CHIP" in current_benefits
    receives_tanf = "TANF / Cash Assistance" in current_benefits

    monthly_income = form_data.get("income_range", 0)

    return {
        "state": form_data.get("state", ""),
        "household_size": form_data.get("household_size", 1),
        "monthly_income": monthly_income,
        "ages_of_members": numeric_ages,
        "has_children": any(a < 18 for a in numeric_ages),
        "has_child_under_5": any(a < 5 for a in numeric_ages),
        "has_elderly": any(a >= 60 for a in numeric_ages),
        "is_pregnant": is_pregnant,
        "is_postpartum": is_postpartum,
        "is_breastfeeding": is_breastfeeding,
        "has_disability": has_disability,
        "receives_snap": receives_snap,
        "receives_medicaid": receives_medicaid,
        "receives_tanf": receives_tanf,
        "employment_status": EMPLOYMENT_MAP.get(form_data.get("employment", ""), "unknown"),
        "immigration_status": IMMIGRATION_MAP.get(form_data.get("immigration", ""), "unknown"),
        "monthly_rent": form_data.get("housing", 0),
        "profile_source": "intake_form",
        "created_at": datetime.utcnow().isoformat(),
    }


def extract_profile_from_conversation(history: list, client: OpenAI) -> dict | None:
    """Ask ASI-1 Mini to extract a structured profile from conversation history."""
    extraction_prompt = """Extract a user profile from this conversation history.
Return JSON only, or null if not enough info yet.
Required fields: state, household_size, monthly_income
Optional: ages_of_members, immigration_status, is_pregnant, is_postpartum, is_breastfeeding,
has_child_under_5, has_children, disability, current_benefits, employment_status

Return null if state, household_size, or monthly_income is missing."""

    response = client.chat.completions.create(
        model="asi1-mini",
        messages=[
            {"role": "system", "content": extraction_prompt},
            *history,
            {"role": "user", "content": "Extract the profile JSON from this conversation. Return null if not enough info."}
        ],
    )
    try:
        raw = response.choices[0].message.content.strip()
        if raw.lower() == "null":
            return None
        return json.loads(raw)
    except Exception:
        return None


def is_complex_case(profile: dict) -> bool:
    """Flag cases that need NavigatorAgent."""
    complex_statuses = ["daca", "undocumented", "visa", "unknown"]
    return profile.get("immigration_status") in complex_statuses


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


agent = Agent()
chat_proto = Protocol(spec=chat_protocol_spec)
session_store = {}


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id),
    )

    # Handle session start
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"New session: {sender}")
            welcome = (
                "Hi! I'm Bento 🌿 I help people find government benefits they may qualify for — "
                "like food assistance, health coverage, and more.\n\n"
                "To get started, what state do you live in?"
            )
            await ctx.send(sender, create_text_chat(welcome))
            return

    user_text = " ".join(
        item.text for item in msg.content if isinstance(item, TextContent)
    ).strip()

    if not user_text:
        return

    ctx.logger.info(f"User: {user_text}")

    # ── Check if this is a JSON intake form submission ────────────────────────
    try:
        form_data = json.loads(user_text)
        if isinstance(form_data, dict) and "state" in form_data:
            # This is an intake form submission — build profile and route
            profile = build_profile(form_data)
            ctx.logger.info(f"Profile built from intake form:\n{json.dumps(profile, indent=2)}")

            if is_complex_case(profile):
                ctx.logger.info("Complex immigration case — routing to NavigatorAgent")
                await ctx.send(
                    NAVIGATOR_AGENT_ADDRESS,
                    create_text_chat(json.dumps({
                        "profile": profile,
                        "situation": "Complex immigration status — determine available benefits"
                    }))
                )
                await ctx.send(sender, create_text_chat(
                    "Your situation has some nuances I want to handle carefully. Getting you specific guidance..."
                ))
            else:
                ctx.logger.info("Routing to EligibilityAgent")
                await ctx.send(ELIGIBILITY_AGENT_ADDRESS, create_text_chat(json.dumps(profile)))
                await ctx.send(sender, create_text_chat(
                    "Great — I have what I need! Checking your eligibility for SNAP, Medicaid, TANF, WIC, and LIHEAP now..."
                ))
            return
    except (json.JSONDecodeError, TypeError):
        pass  # Not JSON — continue with conversational flow

    # ── Conversational flow ───────────────────────────────────────────────────
    client = OpenAI(
        base_url="https://api.asi1.ai/v1",
        api_key=ctx.secrets.get("ASI1_API_KEY"),
    )

    history = build_llm_message_history(ctx, sender)
    user_lower = user_text.lower()

    # Check for apply request
    apply_keywords = ["apply for", "how to apply", "start application", "apply to"]
    benefit_names = ["snap", "medicaid", "tanf", "wic", "liheap"]
    is_apply_request = any(kw in user_lower for kw in apply_keywords)
    mentioned_benefit = next((b.upper() for b in benefit_names if b in user_lower), None)

    # Check for navigator triggers
    navigator_keywords = ["denied", "denial", "appeal", "rejected", "kicked off", "lost my benefits", "complex", "confused"]
    needs_navigator = any(kw in user_lower for kw in navigator_keywords)

    # Check for policy updates
    policy_keywords = ["policy", "changes", "news", "updates", "cut", "new rules"]
    wants_policy = any(kw in user_lower for kw in policy_keywords)

    # Try to extract profile from conversation
    profile = extract_profile_from_conversation(history + [{"role": "user", "content": user_text}], client)

    if needs_navigator and profile:
        ctx.logger.info("Routing to NavigatorAgent")
        await ctx.send(NAVIGATOR_AGENT_ADDRESS, create_text_chat(
            json.dumps({"profile": profile, "situation": user_text})
        ))
        await ctx.send(sender, create_text_chat(
            "Let me connect you with specific guidance for your situation..."
        ))
        return

    if wants_policy and profile:
        ctx.logger.info("Routing to PolicyWatcherAgent")
        await ctx.send(POLICY_WATCHER_AGENT_ADDRESS, create_text_chat(json.dumps(profile)))
        await ctx.send(sender, create_text_chat(
            "Let me check what policy changes might affect you..."
        ))
        return

    if is_apply_request and mentioned_benefit and profile:
        ctx.logger.info(f"Routing to ApplicationAgent for {mentioned_benefit}")
        await ctx.send(APPLICATION_AGENT_ADDRESS, create_text_chat(
            json.dumps({"benefit": mentioned_benefit, "profile": profile})
        ))
        await ctx.send(sender, create_text_chat(
            f"Let me pull together your personalized guide for applying to {mentioned_benefit}..."
        ))
        return

    if profile and not session_store.get(sender):
        session_store[sender] = profile
        ctx.logger.info(f"Routing to EligibilityAgent with profile: {profile}")

        if is_complex_case(profile):
            await ctx.send(NAVIGATOR_AGENT_ADDRESS, create_text_chat(
                json.dumps({"profile": profile, "situation": "Complex immigration status — need guidance"})
            ))
            await ctx.send(sender, create_text_chat(
                "Your situation has some nuances I want to handle right. Getting you specific guidance..."
            ))
            return

        await ctx.send(ELIGIBILITY_AGENT_ADDRESS, create_text_chat(json.dumps(profile)))
        await ctx.send(sender, create_text_chat(
            "Great — I have what I need! Checking your eligibility for SNAP, Medicaid, TANF, WIC, and LIHEAP now..."
        ))
        return

    # Default: conversational intake via ASI-1 Mini
    response = client.chat.completions.create(
        model="asi1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": user_text},
        ],
    )

    reply = response.choices[0].message.content
    await ctx.send(sender, create_text_chat(reply))


@chat_proto.on_message(ChatMessage, replies=ChatMessage)
async def handle_agent_response(ctx: Context, sender: str, msg: ChatMessage):
    """Receive responses from sub-agents and forward to user."""
    ctx.logger.info(f"Response from sub-agent {sender}")


agent.include(chat_proto, publish_manifest=True)
