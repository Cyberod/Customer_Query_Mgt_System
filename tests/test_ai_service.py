"""Unit tests for app/services/ai.py — Anthropic client is always mocked."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai import classify_query, generate_draft_reply


def _make_response(text: str):
    """Build a minimal mock that looks like an Anthropic Messages response."""
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


def _mock_client(response_text: str):
    """Return a mock AsyncAnthropic client whose messages.create returns response_text."""
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_response(response_text))
    return client


VALID_CLASSIFY_JSON = json.dumps({
    "category": "billing",
    "priority": "high",
    "sentiment": "negative",
    "ai_summary": "Customer was charged twice and wants a refund.",
})


# ── classify_query ─────────────────────────────────────────────────────────────

async def test_classify_query_returns_parsed_dict():
    with patch("app.services.ai._get_client", return_value=_mock_client(VALID_CLASSIFY_JSON)):
        result = await classify_query("Duplicate charge", "I was billed twice.")
    assert result["category"] == "billing"
    assert result["priority"] == "high"
    assert result["sentiment"] == "negative"
    assert "refund" in result["ai_summary"].lower()


async def test_classify_query_strips_markdown_fence():
    fenced = f"```json\n{VALID_CLASSIFY_JSON}\n```"
    with patch("app.services.ai._get_client", return_value=_mock_client(fenced)):
        result = await classify_query("Subject", "Body")
    assert result is not None
    assert result["category"] == "billing"


async def test_classify_query_returns_none_on_api_exception():
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=Exception("API unreachable"))
    with patch("app.services.ai._get_client", return_value=client):
        result = await classify_query("Subject", "Body")
    assert result is None


async def test_classify_query_returns_none_on_invalid_json():
    with patch("app.services.ai._get_client", return_value=_mock_client("not json at all")):
        result = await classify_query("Subject", "Body")
    assert result is None


# ── generate_draft_reply ───────────────────────────────────────────────────────

DRAFT_TEXT = "Thank you for contacting us. We are looking into this matter and will get back to you shortly."


async def test_generate_draft_reply_returns_string():
    with patch("app.services.ai._get_client", return_value=_mock_client(DRAFT_TEXT)):
        result = await generate_draft_reply("Subject", "Customer body", [])
    assert result == DRAFT_TEXT


async def test_generate_draft_reply_returns_none_on_exception():
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=RuntimeError("timeout"))
    with patch("app.services.ai._get_client", return_value=client):
        result = await generate_draft_reply("Subject", "Body", [])
    assert result is None


async def test_generate_draft_excludes_ai_draft_messages_from_thread():
    """AI draft messages should not be included as prior context."""
    captured_prompt = {}

    async def _fake_create(**kwargs):
        captured_prompt["content"] = kwargs["messages"][0]["content"]
        return _make_response(DRAFT_TEXT)

    client = MagicMock()
    client.messages.create = _fake_create

    prior = [
        {"body": "Agent real reply", "is_ai_draft": False},
        {"body": "AI draft — should be ignored", "is_ai_draft": True},
    ]
    with patch("app.services.ai._get_client", return_value=client):
        await generate_draft_reply("Subject", "Customer body", prior)

    prompt_text = captured_prompt["content"]
    assert "Agent real reply" in prompt_text
    assert "AI draft — should be ignored" not in prompt_text


async def test_generate_draft_with_empty_prior_messages():
    with patch("app.services.ai._get_client", return_value=_mock_client(DRAFT_TEXT)):
        result = await generate_draft_reply("Hello", "Need help please", [])
    assert result is not None
    assert len(result) > 0
