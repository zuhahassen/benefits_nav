from datetime import datetime
from uuid import uuid4
import json
import re

from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

# Import knowledge base
from knowledge_base import (
    get_benefits_data,
    get_benefit_info,
    get_income_limit,
    get_fpl,
    check_immigration_eligible,
    build_eligibility_context,
)

# ── EligibilityAgent ─────────────────────────────────────────────────────────
# Receives a JSON user profile from Bento, runs rules-based filter against
# benefit thresholds from knowledge base, then calls ASI-1 Mini for edge cases.
# Returns sorted list: likely → possible → ineligible.


def rules_based_filter(profile: dict) -> dict:
    """Fast rules-based pre-filter using knowledge base. Returns verdict per benefit."""
    results = {}
    size = min(profile.get("household_size", 1), 8)
    monthly_income = profile.get("monthly_income", 0)
    immigration = profile.get("immigration_status", "citizen")
    has_children = profile.get("has_children", False)
    is_pregnant = profile.get("is_pregnant", False)
    is_postpartum = profile.get("is_postpartum", False)
    is_breastfeeding = profile.get("is_breastfeeding", False)
    has_child_under_5 = profile.get("has_child_under_5", False)
    receives_snap = profile.get("receives_snap", False)
    receives_medicaid = profile.get("receives_medicaid", False)
    receives_tanf = profile.get("receives_tanf", False)
    state = profile.get("state", "")

    # Get data from knowledge base
    snap_info = get_benefit_info("SNAP")
    medicaid_info = get_benefit_info("Medicaid")
    tanf_info = get_benefit_info("TANF")
    wic_info = get_benefit_info("WIC")
    liheap_info = get_benefit_info("LIHEAP")

    # SNAP
    snap_limit = get_income_limit("SNAP", size)
    snap_eligible, snap_reason = check_immigration_eligible("SNAP", immigration)
    if not snap_eligible and immigration in snap_info.get("ineligible_statuses", []):
        results["SNAP"] = ("ineligible", snap_reason)
    elif monthly_income <= snap_limit:
        results["SNAP"] = ("likely", f"Income ${monthly_income}/mo is within SNAP limit of ${snap_limit}/mo for household of {size}.")
    elif monthly_income <= snap_limit * 1.1:
        results["SNAP"] = ("possible", "Income is close to SNAP limit — deductions for rent, childcare, or medical expenses may qualify you.")
    else:
        results["SNAP"] = ("ineligible", "Income appears over SNAP gross limit.")

    # Medicaid
    medicaid_limit = get_income_limit("Medicaid", size)
    daca_states = medicaid_info.get("daca_state_programs", [])
    if immigration == "undocumented":
        if is_pregnant:
            results["Medicaid"] = ("possible", "Undocumented pregnant women may qualify for emergency Medicaid for prenatal care.")
        else:
            results["Medicaid"] = ("ineligible", "Undocumented individuals not eligible for federal Medicaid.")
    elif immigration == "daca":
        if state in daca_states:
            results["Medicaid"] = ("likely", f"DACA recipients can get Medicaid in {state} through a state-funded program.")
        else:
            results["Medicaid"] = ("possible", f"DACA recipients not eligible for federal Medicaid. States with programs: {', '.join(daca_states[:5])}")
    elif monthly_income <= medicaid_limit:
        results["Medicaid"] = ("likely", f"Income is within Medicaid limit for household of {size}.")
    elif is_pregnant:
        results["Medicaid"] = ("possible", "Pregnant women have higher income limits — likely eligible.")
    else:
        results["Medicaid"] = ("possible", "Income is close to limit. Expansion state rules and deductions may help.")

    # TANF
    fpl_annual = get_fpl(size)
    fpl_50_monthly = (fpl_annual * 0.50) / 12
    tanf_ineligible = tanf_info.get("ineligible_statuses", [])
    if not has_children:
        results["TANF"] = ("ineligible", "TANF requires children under 18 in the household.")
    elif immigration in tanf_ineligible:
        results["TANF"] = ("possible", "Parent may not be eligible, but US citizen children in the household can receive TANF (child-only grant).")
    elif monthly_income <= fpl_50_monthly:
        results["TANF"] = ("likely", "Income and household composition suggest TANF eligibility.")
    else:
        results["TANF"] = ("possible", "Income may be over state limit — varies significantly by state.")

    # WIC (no immigration check)
    wic_limit = get_income_limit("WIC", size)
    wic_eligible_category = is_pregnant or is_postpartum or is_breastfeeding or has_child_under_5
    if not wic_eligible_category:
        results["WIC"] = ("ineligible", "WIC requires pregnancy, recent birth, breastfeeding, or child under 5.")
    elif receives_snap or receives_medicaid or receives_tanf:
        results["WIC"] = ("likely", "Already on SNAP/Medicaid/TANF = automatically income-eligible for WIC. WIC does not check immigration status.")
    elif monthly_income <= wic_limit:
        results["WIC"] = ("likely", "Income within WIC limit. WIC does not ask about immigration status.")
    else:
        results["WIC"] = ("possible", "Income over WIC limit but categorical eligibility via other benefits may apply.")

    # LIHEAP
    liheap_limit = get_income_limit("LIHEAP", size)
    liheap_eligible, _ = check_immigration_eligible("LIHEAP", immigration)
    if monthly_income <= liheap_limit and liheap_eligible:
        results["LIHEAP"] = ("likely", "Income within LIHEAP limit. Note: funding is seasonal — apply early.")
    elif monthly_income <= liheap_limit:
        results["LIHEAP"] = ("possible", "Income within limit but check immigration eligibility for your state.")
    else:
        results["LIHEAP"] = ("ineligible", "Income appears over LIHEAP threshold.")

    return results


def get_system_prompt(profile: dict) -> str:
    """Build system prompt with knowledge base context for this profile."""
    kb_context = build_eligibility_context(profile)
    
    return f"""You are Bento's EligibilityAgent. You analyze user profiles and return eligibility verdicts.

CRITICAL: Return ONLY valid JSON. No markdown, no explanation text, no code blocks. Just the JSON object.

KNOWLEDGE BASE (current 2025 data):
{kb_context}

You will receive a user profile and preliminary verdicts from a rules-based filter.
Your job is to reason through ambiguous cases and return final verdicts.

Focus on:
- Mixed immigration status households (some members may qualify even if parent doesn't)
- DACA recipients (WIC and LIHEAP are available, some states have Medicaid)
- Near-threshold incomes (deductions for rent, childcare, medical may help)
- Pregnancy/postpartum (higher limits, expedited processing)
- State-specific variations

Return this exact JSON structure (no other text):
{{
  "SNAP": {{"verdict": "likely", "explanation": "Your income is within the limit for your household size."}},
  "Medicaid": {{"verdict": "likely", "explanation": "You appear to qualify based on income."}},
  "TANF": {{"verdict": "possible", "explanation": "You may qualify but state rules vary."}},
  "WIC": {{"verdict": "likely", "explanation": "You meet the requirements."}},
  "LIHEAP": {{"verdict": "likely", "explanation": "You qualify for utility assistance."}}
}}

Verdict must be exactly one of: "likely", "possible", "ineligible"
Explanations: Plain language, 6th grade reading level, warm and encouraging, 1-2 sentences max.
"""


def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.utcnow(), msg_id=uuid4(), content=content)


agent = Agent()
chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id),
    )

    user_text = " ".join(
        item.text for item in msg.content if isinstance(item, TextContent)
    ).strip()

    if not user_text:
        return

    # Parse incoming profile JSON from Bento
    try:
        profile = json.loads(user_text)
    except json.JSONDecodeError:
        await ctx.send(sender, create_text_chat(
            json.dumps({"error": "Invalid profile JSON"}), end_session=True
        ))
        return

    # Step 1: rules-based filter
    preliminary = rules_based_filter(profile)

    # Step 2: ASI-1 Mini for edge cases
    ambiguous = {k: v for k, v in preliminary.items() if v[0] == "possible"}
    has_edge_case = (
        profile.get("immigration_status") in ["daca", "undocumented", "lpr_under5yr"]
        or len(ambiguous) > 0
    )

    if has_edge_case:
        client = OpenAI(
            base_url="https://api.asi1.ai/v1",
            api_key=ctx.secrets.get("ASI1_API_KEY"),
        )
        prelim_formatted = {k: {"verdict": v[0], "reason": v[1]} for k, v in preliminary.items()}
        response = client.chat.completions.create(
            model="asi1-mini",
            messages=[
                {"role": "system", "content": get_system_prompt(profile)},
                {"role": "user", "content": f"Profile: {json.dumps(profile)}\n\nPreliminary verdicts: {json.dumps(prelim_formatted)}\n\nReturn ONLY the JSON object with final verdicts. No other text."}
            ],
        )
        try:
            raw = response.choices[0].message.content.strip()
            # Try to extract JSON if wrapped in markdown code blocks
            if "```" in raw:
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
                if json_match:
                    raw = json_match.group(1)
            # Try to find JSON object
            if not raw.startswith("{"):
                json_match = re.search(r'\{[\s\S]*\}', raw)
                if json_match:
                    raw = json_match.group(0)
            final = json.loads(raw)
        except Exception as e:
            ctx.logger.warning(f"Failed to parse ASI-1 response as JSON: {e}")
            # Fall back to rules-based if parsing fails
            final = {k: {"verdict": v[0], "explanation": v[1]} for k, v in preliminary.items()}
    else:
        final = {k: {"verdict": v[0], "explanation": v[1]} for k, v in preliminary.items()}

    # Sort: likely first, then possible, then ineligible
    order = {"likely": 0, "possible": 1, "ineligible": 2}
    sorted_results = dict(sorted(final.items(), key=lambda x: order.get(x[1].get("verdict", "ineligible"), 2)))

    await ctx.send(sender, create_text_chat(json.dumps(sorted_results), end_session=True))


agent.include(chat_proto, publish_manifest=True) 