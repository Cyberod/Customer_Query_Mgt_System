import json
import logging

from anthropic import AsyncAnthropic

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def classify_query(subject: str, body: str) -> dict | None:
    """
    Returns {"category", "priority", "sentiment", "ai_summary"} or None on failure.
    """
    try:
        response = await _get_client().messages.create(
            model="claude-opus-4-8",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": (
                    "You are a customer support triage assistant. "
                    "Analyze the query below and respond with ONLY a valid JSON object — no markdown, no explanation.\n\n"
                    f"Subject: {subject}\nBody: {body}\n\n"
                    "Required JSON format:\n"
                    '{"category":"<billing|technical|general|complaint|other>",'
                    '"priority":"<low|medium|high>",'
                    '"sentiment":"<positive|neutral|negative>",'
                    '"ai_summary":"<one concise sentence summarising the issue>"}'
                ),
            }],
        )
        text = response.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        return json.loads(text)
    except Exception as exc:
        logger.warning("AI classification failed: %s", exc)
        return None


async def generate_draft_reply(
    subject: str,
    body: str,
    prior_messages: list[dict],
) -> str | None:
    """
    Returns a draft reply string, or None on failure.
    prior_messages: list of {"body": str, "is_ai_draft": bool}
    """
    try:
        thread = f"Customer message:\n{body}"
        for m in prior_messages:
            if not m["is_ai_draft"]:
                thread += f"\n\nAgent reply:\n{m['body']}"

        response = await _get_client().messages.create(
            model="claude-opus-4-8",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": (
                    "You are a helpful customer support agent. "
                    "Write a professional, empathetic reply to the customer query below. "
                    "Output the reply body ONLY — no subject line, no company sign-off.\n\n"
                    f"Subject: {subject}\n\n{thread}"
                ),
            }],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        logger.warning("AI draft generation failed: %s", exc)
        return None
