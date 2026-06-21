from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import init_db
from app.routers import auth, queries, portal, dashboard
import app.models  # noqa: F401 — registers all models with SQLAlchemy metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


TAGS_METADATA = [
    {
        "name": "auth",
        "description": (
            "User registration and authentication. "
            "Login returns a **Bearer token** that must be supplied as "
            "`Authorization: Bearer <token>` on all protected endpoints."
        ),
    },
    {
        "name": "queries",
        "description": (
            "Customer query lifecycle. Customers submit queries; the system "
            "classifies them automatically using the Claude AI API "
            "(category, priority, sentiment, summary). "
            "Agents retrieve and manage queries through the dashboard UI."
        ),
    },
]

app = FastAPI(
    title=settings.app_name,
    description=(
        "## AI-Assisted Customer Query Management System\n\n"
        "A minimalist, production-ready CQMS that combines a standard support "
        "workflow with Anthropic Claude AI for automatic triage and draft replies.\n\n"
        "### Workflow\n"
        "1. **Customer** registers, submits a query via the portal or this API.\n"
        "2. **AI** classifies the query (category, priority, sentiment) and writes a one-line summary.\n"
        "3. **Agent** opens the dashboard, sees the AI classification, and gets an AI-drafted reply to edit and send.\n"
        "4. **Customer** tracks query status at `/track` without needing to log in.\n\n"
        "### Authentication\n"
        "HTML portal routes use httpOnly cookie sessions. "
        "This JSON API uses **OAuth2 Bearer tokens** — call `POST /auth/login` first, "
        "then add `Authorization: Bearer <token>` to subsequent requests."
    ),
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router)
app.include_router(queries.router)
app.include_router(portal.router)
app.include_router(dashboard.router)


@app.get("/health", summary="Health check", tags=["system"])
async def health_check():
    """Returns 200 when the application is running."""
    return {"status": "ok", "app": settings.app_name}
