from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.query import Query
from app.models.user import User
from app.services.ai import classify_query
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(tags=["portal"])
templates = Jinja2Templates(directory="app/templates")


def _get_user_from_cookie(request: Request) -> dict | None:
    from jose import JWTError, jwt
    from app.config import settings
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None


async def _current_user(request: Request, db: AsyncSession) -> User | None:
    payload = _get_user_from_cookie(request)
    if not payload:
        return None
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    return result.scalar_one_or_none()


# ── Public query tracker ─────────────────────────────────────────────────────

@router.get("/track", response_class=HTMLResponse)
async def track_query(
    request: Request,
    ref: str = "",
    db: AsyncSession = Depends(get_db),
):
    query = None
    error = None

    if ref:
        try:
            qid = int(ref.strip())
            result = await db.execute(select(Query).where(Query.id == qid))
            query = result.scalar_one_or_none()
            if not query:
                error = f"No query found with reference #{qid}. Please check the number and try again."
        except ValueError:
            error = "Please enter a valid numeric reference number."

    return templates.TemplateResponse("shared/track.html", {
        "request": request,
        "query": query,
        "error": error,
        "searched": bool(ref),
        "ref": ref,
    })


# ── Landing ──────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("shared/landing.html", {"request": request})


# ── Auth pages ───────────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("customer/register.html", {"request": request})


@router.post("/register")
async def register_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        return templates.TemplateResponse(
            "customer/register.html",
            {"request": request, "error": "Email already registered."},
            status_code=400,
        )
    user = User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        role="customer",
    )
    db.add(user)
    await db.commit()
    return RedirectResponse("/login?registered=1", status_code=status.HTTP_302_FOUND)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    registered = request.query_params.get("registered")
    return templates.TemplateResponse(
        "customer/login.html",
        {"request": request, "registered": registered},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "customer/login.html",
            {"request": request, "error": "Invalid email or password."},
            status_code=401,
        )
    token = create_access_token({"sub": str(user.id)})
    redirect_to = "/dashboard" if user.role == "agent" else "/portal"
    response = RedirectResponse(redirect_to, status_code=status.HTTP_302_FOUND)
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response


# ── Customer portal ───────────────────────────────────────────────────────────

@router.get("/portal", response_class=HTMLResponse)
async def portal_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    result = await db.execute(
        select(Query)
        .where(Query.customer_id == user.id)
        .order_by(Query.created_at.desc())
    )
    queries = result.scalars().all()
    return templates.TemplateResponse(
        "customer/portal.html",
        {"request": request, "user": user, "queries": queries},
    )


@router.get("/portal/submit", response_class=HTMLResponse)
async def submit_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        "customer/submit.html", {"request": request, "user": user}
    )


@router.post("/portal/submit")
async def submit_query_form(
    request: Request,
    subject: str = Form(...),
    body: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    query = Query(customer_id=user.id, subject=subject, body=body)
    db.add(query)
    await db.commit()
    await db.refresh(query)

    # AI classification — best-effort, never blocks the submission
    ai = await classify_query(subject, body)
    if ai:
        query.category = ai.get("category")
        query.priority = ai.get("priority")
        query.sentiment = ai.get("sentiment")
        query.ai_summary = ai.get("ai_summary")
        await db.commit()

    return RedirectResponse(f"/portal/query/{query.id}", status_code=status.HTTP_302_FOUND)


@router.get("/portal/query/{query_id}", response_class=HTMLResponse)
async def query_detail(
    request: Request, query_id: int, db: AsyncSession = Depends(get_db)
):
    user = await _current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    result = await db.execute(
        select(Query)
        .where(Query.id == query_id)
        .options(selectinload(Query.messages))
    )
    query = result.scalar_one_or_none()
    if not query or query.customer_id != user.id:
        return templates.TemplateResponse(
            "shared/404.html", {"request": request}, status_code=404
        )
    return templates.TemplateResponse(
        "customer/query_detail.html",
        {"request": request, "user": user, "query": query},
    )
