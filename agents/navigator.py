from datetime import datetime
from uuid import uuid4
import json

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
    check_immigration_eligible,
    semantic_search,
)

# ── NavigatorAgent ────────────────────────────────────────────────────────────
# Handles complex cases: denials, appeals, mixed-status households, legal aid.
# Uses knowledge base to find relevant benefits and resources.
# Triggered by Bento when profile has high complexity flags.

LOCAL_RESOURCES = {
    "legal_aid": {
        "national": "https://www.lawhelp.org",
        "description": "Free legal aid for benefits denials and appeals"
    },
    "211": {
        "how_to_reach": "Call or text 211, or visit 211.org",
        "description": "Free 24/7 hotline connecting to local social services, food, housing, and benefits navigators"
    },
    "benefits_navigators": {
        "url": "https://localhelp.benefits.gov",
        "description": "Find in-person benefits enrollment help near you"
    },
    "immigration_legal": {
        "url": "https://www.immigrationadvocates.org/nonprofit/legaldirectory/",
        "description": "Free immigration legal services — for benefits questions related to immigration status"
    },
    "food_banks": {
        "url": "https://www.feedingamerica.org/find-your-local-foodbank",
        "description": "Local food banks while waiting for SNAP approval"
    }
}

SYSTEM_PROMPT = """You are Bento's NavigatorAgent — a compassionate guide for people in complex situations.

You handle cases that are too complicated for standard eligibility checks:
- Benefit denials and how to appeal
- Mixed-status households (some members eligible, some not)
- DACA recipients and state-specific options
- Disability-related benefit questions
- Homeless or unstable housing situations
- Recent life changes (job loss, divorce, birth)
- General confusion about next steps

Your job:
1. Acknowledge their situation with warmth — never make them feel judged
2. Explain their options clearly
3. Connect them to real local resources
4. For appeals: explain the process briefly and urgently (there are deadlines)

Appeal deadlines (critical):
- SNAP: 90 days from denial notice to request a fair hearing
- Medicaid: 90 days from denial  
- TANF: varies by state, typically 30-90 days
- Always say: "Check your denial letter — the deadline is on it. Don't wait."

Return JSON only:
{
  "situation_summary": "brief empathetic summary of what you understand",
  "immediate_actions": ["action 1", "action 2"],
  "resources": [
    {"name": "resource name", "contact": "how to reach", "why": "why this helps them"}
  ],
  "appeal_info": "appeal guidance if relevant, null if not",
  "encouragement": "one warm closing sentence"
}
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

    try:
        payload = json.loads(user_text)
        profile = payload.get("profile", {})
        situation = payload.get("situation", "")
    except json.JSONDecodeError:
        profile = {}
        situation = user_text

    # Get relevant benefits from knowledge base
    api_key = ctx.secrets.get("ASI1_API_KEY")
    benefits_data = get_benefits_data()
    
    # Check which benefits might be available for this profile
    immigration = profile.get("immigration_status", "unknown")
    available_benefits = []
    for benefit_name in ["SNAP", "Medicaid", "TANF", "WIC", "LIHEAP"]:
        eligible, reason = check_immigration_eligible(benefit_name, immigration)
        if eligible:
            available_benefits.append(f"{benefit_name}: eligible")
        else:
            available_benefits.append(f"{benefit_name}: {reason}")

    client = OpenAI(
        base_url="https://api.asi1.ai/v1",
        api_key=api_key,
    )

    response = client.chat.completions.create(
        model="asi1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"User profile: {json.dumps(profile)}\n"
                f"Situation/question: {situation}\n\n"
                f"KNOWLEDGE BASE - Benefits eligibility for this immigration status ({immigration}):\n"
                f"{chr(10).join(available_benefits)}\n\n"
                f"Available resources: {json.dumps(LOCAL_RESOURCES)}\n\n"
                "Provide compassionate, actionable guidance."
            )}
        ],
    )

    try:
        raw = response.choices[0].message.content
        result = json.loads(raw)
    except Exception:
        result = {
            "situation_summary": "We understand you're dealing with a complex situation.",
            "immediate_actions": ["Call 211 for free local help", "Visit lawhelp.org for free legal aid"],
            "resources": [{"name": "211", "contact": "Call or text 211", "why": "Connects you to local benefits navigators"}],
            "appeal_info": None,
            "encouragement": "You deserve support — help is available."
        }

    await ctx.send(sender, create_text_chat(json.dumps(result), end_session=True))


agent.include(chat_proto, publish_manifest=True) 