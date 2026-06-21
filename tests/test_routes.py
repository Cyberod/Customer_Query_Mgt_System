"""
Integration tests for HTTP routes — uses an in-memory SQLite test database
and mocks both AI service functions so no real Anthropic API calls are made.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.auth import hash_password


# Patch target paths — used individually in tests that call AI-enabled endpoints
AI_CLASSIFY_PATCH = "app.routers.portal.classify_query"
AI_DRAFT_PATCH = "app.routers.dashboard.generate_draft_reply"


# ── Public pages ───────────────────────────────────────────────────────────────

async def test_landing_page(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "AI-Powered" in r.text


async def test_track_page_loads(client):
    r = await client.get("/track")
    assert r.status_code == 200
    assert "Track Your Query" in r.text


async def test_register_page_loads(client):
    r = await client.get("/register")
    assert r.status_code == 200


async def test_login_page_loads(client):
    r = await client.get("/login")
    assert r.status_code == 200


# ── Auth: register & login ─────────────────────────────────────────────────────

async def test_register_new_customer(client):
    r = await client.post("/register", data={
        "full_name": "Alice Customer",
        "email": "alice@example.com",
        "password": "Password123",
    }, follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


async def test_register_duplicate_email_returns_400(client):
    payload = {
        "full_name": "Bob",
        "email": "bob@example.com",
        "password": "Password123",
    }
    await client.post("/register", data=payload)
    r = await client.post("/register", data=payload)
    assert r.status_code == 400
    assert "already registered" in r.text.lower()


async def test_login_wrong_password_returns_401(client):
    await client.post("/register", data={
        "full_name": "Carol",
        "email": "carol@example.com",
        "password": "RealPassword",
    })
    r = await client.post("/login", data={
        "email": "carol@example.com",
        "password": "WrongPassword",
    })
    assert r.status_code == 401


async def test_login_nonexistent_user_returns_401(client):
    r = await client.post("/login", data={
        "email": "ghost@example.com",
        "password": "anything",
    })
    assert r.status_code == 401


# ── Auth-protected pages redirect when unauthenticated ────────────────────────

async def test_dashboard_redirects_without_auth(client):
    r = await client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


async def test_portal_redirects_without_auth(client):
    r = await client.get("/portal", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


async def test_submit_page_redirects_without_auth(client):
    r = await client.get("/portal/submit", follow_redirects=False)
    assert r.status_code == 302


# ── Customer portal flow ───────────────────────────────────────────────────────

async def _login_as_customer(client, email="eve@example.com", password="Pass123"):
    """Register + login a customer; returns the cookie-bearing client."""
    await client.post("/register", data={
        "full_name": "Eve",
        "email": email,
        "password": password,
    })
    r = await client.post("/login", data={"email": email, "password": password},
                          follow_redirects=False)
    assert r.status_code == 302, "Login failed"
    # httpx AsyncClient stores cookies automatically
    return client


async def test_customer_can_view_portal(client):
    await _login_as_customer(client)
    r = await client.get("/portal")
    assert r.status_code == 200
    assert "My Queries" in r.text


async def test_customer_can_submit_query(client):
    await _login_as_customer(client)
    with patch(AI_CLASSIFY_PATCH, new=AsyncMock(return_value={
        "category": "general",
        "priority": "low",
        "sentiment": "neutral",
        "ai_summary": "Customer has a general enquiry.",
    })):
        r = await client.post("/portal/submit", data={
            "subject": "Test question",
            "body": "I have a question about my account.",
        }, follow_redirects=False)
    assert r.status_code == 302
    assert "/portal/query/" in r.headers["location"]


async def test_submitted_query_appears_in_portal(client):
    await _login_as_customer(client)
    with patch(AI_CLASSIFY_PATCH, new=AsyncMock(return_value=None)):
        await client.post("/portal/submit", data={
            "subject": "Visible query",
            "body": "Body text here.",
        })
    r = await client.get("/portal")
    assert "Visible query" in r.text


async def test_track_page_finds_submitted_query(client):
    await _login_as_customer(client, "frank@example.com")
    with patch(AI_CLASSIFY_PATCH, new=AsyncMock(return_value=None)):
        r = await client.post("/portal/submit", data={
            "subject": "Trackable issue",
            "body": "Please help me track this.",
        }, follow_redirects=False)
    query_id = r.headers["location"].split("/")[-1]

    r = await client.get(f"/track?ref={query_id}")
    assert r.status_code == 200
    assert "Trackable issue" in r.text


async def test_track_page_missing_query_shows_error(client):
    r = await client.get("/track?ref=99999")
    assert r.status_code == 200
    assert "No query found" in r.text


async def test_track_page_bad_ref_shows_error(client):
    r = await client.get("/track?ref=notanumber")
    assert r.status_code == 200
    assert "valid" in r.text.lower()


# ── Agent dashboard flow ───────────────────────────────────────────────────────

async def _seed_agent(db_session):
    """Insert an agent user directly into the test DB."""
    from app.models.user import User, UserRole
    agent = User(
        full_name="Agent Smith",
        email="agent@example.com",
        hashed_password=hash_password("AgentPass1"),
        role=UserRole.agent,
    )
    db_session.add(agent)
    await db_session.commit()
    return agent


async def test_agent_can_login_and_reach_dashboard(client, db_session):
    await _seed_agent(db_session)
    r = await client.post("/login", data={
        "email": "agent@example.com",
        "password": "AgentPass1",
    }, follow_redirects=False)
    assert r.status_code == 302
    assert "/dashboard" in r.headers["location"]

    r = await client.get("/dashboard")
    assert r.status_code == 200
    assert "Agent Smith" in r.text


async def test_analytics_page_loads_for_agent(client, db_session):
    await _seed_agent(db_session)
    await client.post("/login", data={
        "email": "agent@example.com",
        "password": "AgentPass1",
    })
    r = await client.get("/dashboard/analytics")
    assert r.status_code == 200
    assert "Analytics Overview" in r.text


async def test_analytics_page_redirects_without_auth(client):
    r = await client.get("/dashboard/analytics", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]
