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
    get_benefit_info,
    build_application_context,
)

# ── ApplicationAgent ─────────────────────────────────────────────────────────
# Receives benefit name + user profile from Bento.
# Uses knowledge base + ASI-1 Mini to generate personalized application guidance.
# Output varies by state, immigration status, household composition.

SYSTEM_PROMPT = """You are Bento's ApplicationAgent — a warm, knowledgeable benefits application coach.

You receive a benefit name and a user profile. Your job is to give personalized, step-by-step 
guidance for applying for that specific benefit, tailored to their exact situation.

Personalization rules:
- If renting: mention lease or utility bill for address proof
- If DACA: explain state-specific options, be encouraging about what IS available
- If mixed-status household: clarify which members qualify and apply separately
- If already on SNAP/Medicaid: mention categorical eligibility shortcuts (especially for WIC)
- If pregnant: mention expedited processing where available
- If no SSN for some members: explain how to apply for eligible members only

Tone: Warm, step-by-step, never overwhelming. 6th grade reading level.
Mention: What to bring, where to go, what happens after you apply, how to avoid common rejections.
Always end with: "If you need in-person help, call 211 — it's free and connects you to local navigators."

Return a JSON object with this structure:
{
  "benefit": "benefit name",
  "personalized_steps": ["step 1", "step 2", ...],
  "documents_needed": ["doc 1", "doc 2", ...],
  "where_to_apply": "url or description",
  "what_to_expect": "timeline and process description",
  "avoid_rejection": ["tip 1", "tip 2"],
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
        benefit = payload.get("benefit", "")
        profile = payload.get("profile", {})
    except json.JSONDecodeError:
        await ctx.send(sender, create_text_chat(
            json.dumps({"error": "Invalid JSON. Expected {benefit, profile}."}), end_session=True
        ))
        return

    # Get context from knowledge base
    kb_context = build_application_context(benefit, profile)

    client = OpenAI(
        base_url="https://api.asi1.ai/v1",
        api_key=ctx.secrets.get("ASI1_API_KEY"),
    )

    response = client.chat.completions.create(
        model="asi1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"KNOWLEDGE BASE:\n{kb_context}\n\n"
                "Generate personalized application guidance based on this data."
            )}
        ],
    )

    try:
        raw = response.choices[0].message.content
        guidance = json.loads(raw)
    except Exception:
        guidance = {"benefit": benefit, "guidance": response.choices[0].message.content}

    await ctx.send(sender, create_text_chat(json.dumps(guidance), end_session=True))


agent.include(chat_proto, publish_manifest=True)