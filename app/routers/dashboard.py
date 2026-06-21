from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.message import Message
from app.models.query import Query, QueryStatus
from app.models.user import User, UserRole
from app.services.ai import generate_draft_reply

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


async def _agent_user(request: Request, db: AsyncSession) -> User | None:
    from jose import JWTError, jwt
    from app.config import settings
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or user.role != UserRole.agent:
        return None
    return user


# ── Dashboard home ─────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status_filter: str = "",
    priority_filter: str = "",
    category_filter: str = "",
):
    agent = await _agent_user(request, db)
    if not agent:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    # Build filtered query
    stmt = select(Query).order_by(Query.created_at.desc())
    if status_filter:
        stmt = stmt.where(Query.status == status_filter)
    if priority_filter:
        stmt = stmt.where(Query.priority == priority_filter)
    if category_filter:
        stmt = stmt.where(Query.category == category_filter)

    result = await db.execute(stmt.options(selectinload(Query.customer)))
    queries = result.scalars().all()

    # Stats
    stats_result = await db.execute(
        select(Query.status, func.count(Query.id)).group_by(Query.status)
    )
    stats = {row[0]: row[1] for row in stats_result.all()}

    return templates.TemplateResponse("agent/dashboard.html", {
        "request": request,
        "agent": agent,
        "queries": queries,
        "stats": stats,
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "category_filter": category_filter,
        "total": sum(stats.values()),
    })


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/dashboard/analytics", response_class=HTMLResponse)
async def analytics(request: Request, db: AsyncSession = Depends(get_db)):
    agent = await _agent_user(request, db)
    if not agent:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    by_status_rows = await db.execute(
        select(Query.status, func.count(Query.id)).group_by(Query.status)
    )
    by_status = dict(by_status_rows.all())

    by_category_rows = await db.execute(
        select(Query.category, func.count(Query.id))
        .where(Query.category.isnot(None))
        .group_by(Query.category)
    )
    by_category = dict(by_category_rows.all())

    by_priority_rows = await db.execute(
        select(Query.priority, func.count(Query.id))
        .where(Query.priority.isnot(None))
        .group_by(Query.priority)
    )
    by_priority = dict(by_priority_rows.all())

    by_sentiment_rows = await db.execute(
        select(Query.sentiment, func.count(Query.id))
        .where(Query.sentiment.isnot(None))
        .group_by(Query.sentiment)
    )
    by_sentiment = dict(by_sentiment_rows.all())

    pending_ai_row = await db.execute(
        select(func.count(Query.id)).where(Query.category.is_(None))
    )
    pending_ai = pending_ai_row.scalar() or 0

    total = sum(by_status.values()) if by_status else 0

    return templates.TemplateResponse("agent/analytics.html", {
        "request": request,
        "agent": agent,
        "total": total,
        "by_status": by_status,
        "by_category": by_category,
        "by_priority": by_priority,
        "by_sentiment": by_sentiment,
        "pending_ai": pending_ai,
    })


# ── Query detail ───────────────────────────────────────────────────────────────

@router.get("/dashboard/query/{query_id}", response_class=HTMLResponse)
async def agent_query_detail(
    request: Request,
    query_id: int,
    db: AsyncSession = Depends(get_db),
):
    agent = await _agent_user(request, db)
    if not agent:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    async def _load_query():
        r = await db.execute(
            select(Query)
            .where(Query.id == query_id)
            .options(
                selectinload(Query.customer),
                selectinload(Query.messages).selectinload(Message.sender),
            )
        )
        return r.scalar_one_or_none()

    query = await _load_query()
    if not query:
        return templates.TemplateResponse(
            "shared/404.html", {"request": request}, status_code=404
        )

    # Generate an AI draft reply if none exists yet
    if not any(m.is_ai_draft for m in query.messages):
        prior = [{"body": m.body, "is_ai_draft": m.is_ai_draft} for m in query.messages]
        draft_text = await generate_draft_reply(query.subject, query.body, prior)
        if draft_text:
            db.add(Message(
                query_id=query.id,
                sender_id=agent.id,
                body=draft_text,
                is_ai_draft=True,
            ))
            await db.commit()
            query = await _load_query()

    return templates.TemplateResponse("agent/query_detail.html", {
        "request": request,
        "agent": agent,
        "query": query,
        "statuses": [s.value for s in QueryStatus],
    })


# ── Reply ──────────────────────────────────────────────────────────────────────

@router.post("/dashboard/query/{query_id}/reply")
async def agent_reply(
    request: Request,
    query_id: int,
    body: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    agent = await _agent_user(request, db)
    if not agent:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    if not query:
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

    msg = Message(query_id=query_id, sender_id=agent.id, body=body, is_ai_draft=False)
    db.add(msg)

    # Auto-move to in_progress when agent first replies
    if query.status == QueryStatus.open:
        query.status = QueryStatus.in_progress

    await db.commit()
    return RedirectResponse(
        f"/dashboard/query/{query_id}", status_code=status.HTTP_302_FOUND
    )


# ── Status update ──────────────────────────────────────────────────────────────

@router.post("/dashboard/query/{query_id}/status")
async def update_status(
    request: Request,
    query_id: int,
    new_status: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    agent = await _agent_user(request, db)
    if not agent:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    if query:
        query.status = new_status
        await db.commit()

    return RedirectResponse(
        f"/dashboard/query/{query_id}", status_code=status.HTTP_302_FOUND
    )


# ── Assign to self ─────────────────────────────────────────────────────────────

@router.post("/dashboard/query/{query_id}/assign")
async def assign_to_self(
    request: Request,
    query_id: int,
    db: AsyncSession = Depends(get_db),
):
    agent = await _agent_user(request, db)
    if not agent:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    if query:
        query.assigned_agent_id = agent.id
        await db.commit()

    return RedirectResponse(
        f"/dashboard/query/{query_id}", status_code=status.HTTP_302_FOUND
    )
