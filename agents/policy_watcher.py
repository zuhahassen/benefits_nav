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
    build_policy_context,
)

# ── PolicyWatcherAgent ───────────────────────────────────────────────────────
# Surfaces relevant policy changes from knowledge base based on user's profile.
# ASI-1 Mini personalizes which changes matter for this specific user.

SYSTEM_PROMPT = """You are Bento's PolicyWatcherAgent. You surface relevant policy changes to users
based on their profile.

Given a user profile and a list of policy updates, identify which updates are relevant to this
specific user and explain what they mean in plain, non-alarmist language.

Rules:
- Only surface updates relevant to the user's situation
- Be factual, not alarmist — explain what IS happening, not worst-case scenarios
- Always include a clear action the user can take
- Positive updates (benefit expansions) should be highlighted warmly
- For concerning updates, be honest but reassuring about what's not yet in effect

Return JSON only:
{
  "relevant_updates": [
    {
      "benefit": "benefit name",
      "title": "short title",
      "what_this_means_for_you": "personalized plain language explanation",
      "action": "what to do",
      "severity": "high|medium|low|positive"
    }
  ],
  "summary": "one sentence overview of what the user should know"
}

If no updates are relevant to the user, return an empty relevant_updates array.
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
        # Handle both profile-only and benefit-specific requests
        if isinstance(payload, dict) and "benefit" in payload:
            benefit = payload.get("benefit")
            profile = payload.get("profile", payload)
        else:
            benefit = None
            profile = payload
    except json.JSONDecodeError:
        await ctx.send(sender, create_text_chat(
            json.dumps({"error": "Invalid JSON"}), end_session=True
        ))
        return

    # Get policy context from knowledge base
    kb_context = build_policy_context(benefit)
    data = get_benefits_data()
    policy_updates = data.get("policy_updates", [])

    client = OpenAI(
        base_url="https://api.asi1.ai/v1",
        api_key=ctx.secrets.get("ASI1_API_KEY"),
    )

    response = client.chat.completions.create(
        model="asi1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"User profile: {json.dumps(profile)}\n\n"
                f"KNOWLEDGE BASE - Policy Updates:\n{kb_context}\n\n"
                "Return only the updates relevant to this user with personalized explanations."
            )}
        ],
    )

    try:
        raw = response.choices[0].message.content
        result = json.loads(raw)
    except Exception:
        result = {"relevant_updates": [], "summary": "No policy updates currently affect your profile."}

    await ctx.send(sender, create_text_chat(json.dumps(result), end_session=True))


agent.include(chat_proto, publish_manifest=True) 