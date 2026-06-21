# AI-Assisted Customer Query Management System (CQMS)

A minimalist, full-stack web application that combines a standard customer support workflow with Anthropic Claude AI for automatic triage and draft reply generation. Built with FastAPI, SQLite, and Jinja2 templates.

---

## Prerequisites

- Python 3.11 or higher
- An [Anthropic API key](https://console.anthropic.com/)

---

## Setup

### 1. Clone / open the project

```bash
cd Customer_Query_Mgt_System
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set:

```env
APP_NAME="AI Customer Query Management System"
SECRET_KEY=replace-this-with-a-long-random-string
DATABASE_URL=sqlite+aiosqlite:///./cqms.db
ANTHROPIC_API_KEY=sk-ant-api03-...
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

> `SECRET_KEY` is used to sign JWT tokens. Use any long random string in development.
> `ANTHROPIC_API_KEY` is required for AI classification and draft reply generation.

---

## Starting the App

```bash
python run.py
```

The server starts at **http://localhost:8000** with auto-reload enabled.

Alternatively, use uvicorn directly:

```bash
uvicorn app.main:app --reload
```

---

## Using the App

### Pages at a glance

| URL | Who uses it | What it does |
|---|---|---|
| `/` | Anyone | Landing page |
| `/register` | New users | Create a customer account |
| `/login` | All users | Log in (customers → portal, agents → dashboard) |
| `/portal` | Customers | View all submitted queries |
| `/portal/submit` | Customers | Submit a new query |
| `/portal/query/{id}` | Customers | View a query + conversation thread |
| `/track` | Anyone | Look up a query status by reference number (no login needed) |
| `/dashboard` | Agents | View and filter all queries |
| `/dashboard/query/{id}` | Agents | Reply to a query, see AI classification + draft |
| `/dashboard/analytics` | Agents | Charts: category, priority, sentiment, resolution rate |
| `/docs` | Developers | Interactive OpenAPI / Swagger UI |
| `/redoc` | Developers | ReDoc API documentation |

---

### Customer flow

1. Go to **http://localhost:8000/register** and create an account (leave role as `customer`).
2. After registering, log in at **/login**.
3. Click **Submit New Query** and fill in a subject and description.
4. The AI automatically classifies the query (category, priority, sentiment) and writes a one-line summary. You will see these on your query detail page.
5. Use the reference number shown at the bottom of the query page to share or track the query at **/track** without logging in.

---

### Agent flow

> **Important:** The `/register` page only creates customer accounts. Agent accounts must be created separately using one of the two methods below. Do this **once** before trying to log in as an agent.

---

#### Step 1 — Create an agent account

**Option A — Python shell (recommended, run with the server stopped)**

```bash
source .venv/bin/activate

python - <<'EOF'
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.models.user import User, UserRole
from app.services.auth import hash_password

async def create_agent():
    engine = create_async_engine("sqlite+aiosqlite:///./cqms.db")
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        agent = User(
            full_name="Support Agent",
            email="agent@example.com",
            hashed_password=hash_password("AgentPass123"),
            role=UserRole.agent,
        )
        db.add(agent)
        await db.commit()
    print("Agent created.")

asyncio.run(create_agent())
EOF
```

**Option B — Swagger UI (while the server is running)**

1. Open **http://localhost:8000/docs**.
2. Expand `POST /auth/register` → click **Try it out**.
3. Set `"role": "agent"` in the request body and click **Execute**.

---

#### Step 2 — Log in as the agent

1. Go to **http://localhost:8000/login**.
2. Enter the credentials you used above:
   - **Email:** `agent@example.com`
   - **Password:** `AgentPass123`
3. You will be redirected automatically to **/dashboard**.

---

#### Step 3 — Use the dashboard

1. The dashboard lists all customer queries with status, priority, and category badges.
2. Use the filter bar at the top to narrow by status, priority, or category.
3. Click any row to open a query detail page.
4. The first time an agent opens a query, the AI automatically generates a draft reply — shown as a yellow dashed box labelled **🤖 AI Draft**.
5. Use the draft as a starting point, or type your own reply and click **Send Reply**.
6. Use the right sidebar to update the query status or assign it to yourself.
7. Click **Analytics** in the nav bar to see category, priority, sentiment, and resolution charts.

---

## Running the Tests

```bash
python -m pytest tests/ -v
```

The test suite uses an in-memory SQLite database and mocks all Anthropic API calls — no network access or API key needed.

| Test file | Coverage |
|---|---|
| `tests/test_auth_service.py` | Password hashing and JWT token logic |
| `tests/test_ai_service.py` | AI service: response parsing, error handling, mock Anthropic client |
| `tests/test_routes.py` | HTTP routes: registration, login, portal, dashboard, analytics, tracker |

---

## API Documentation

With the server running, visit:

- **http://localhost:8000/docs** — Swagger UI (interactive, supports Try it out)
- **http://localhost:8000/redoc** — ReDoc (clean, readable format)

All JSON API endpoints require a Bearer token. Get one by calling `POST /auth/login` in the Swagger UI, then click **Authorize** (the padlock icon) and paste the token.

---

## Sample Test Queries

Use these when testing the app as a customer. Each one is designed to trigger a different AI classification so you can see the system working across different scenarios.

---

### Query 1 — Billing complaint (expected: high priority, negative sentiment)

**Subject:**
```
I was charged twice for my subscription this month — urgent refund needed
```

**Body:**
```
Hello,

I noticed two identical charges of $29.99 on my bank statement dated June 10th and June 12th, both from your platform. I only have one active subscription and I did not authorise the second payment.

I have already contacted my bank and they have advised me to raise the issue with you first before filing a chargeback. Please investigate and process a refund for the duplicate charge as soon as possible.

My account email is: testcustomer@example.com
Transaction reference: TXN-20240610-8821

Thank you.
```

> **What to expect from AI:** Category `billing`, Priority `high`, Sentiment `negative`. The AI summary will highlight the duplicate charge and urgency.

---

### Query 2 — Technical issue (expected: medium priority, neutral sentiment)

**Subject:**
```
Unable to log in after resetting my password — account locked out
```

**Body:**
```
Hi support team,

I reset my password yesterday using the "Forgot Password" link. I received the reset email, set a new password, and clicked Save. However, when I try to log in with the new password I get the error: "Invalid email or password."

I have tried three different browsers (Chrome, Firefox, Edge) and also cleared my cache and cookies. The problem persists. I have not been able to access my account for over 24 hours.

Could you please check if there is an issue with my account on your end, or if the password reset is not saving correctly?

Account email: testcustomer@example.com
Operating system: Windows 11
Browser: Chrome 124
```

> **What to expect from AI:** Category `technical`, Priority `medium`, Sentiment `neutral`. The AI summary will describe the login failure after a password reset.

---

### Query 3 — General enquiry (expected: low priority, positive sentiment)

**Subject:**
```
Interested in upgrading my plan — can you walk me through the options?
```

**Body:**
```
Hello,

I have been using your service for about six months now and I am really happy with it so far. I am growing my small business and I think I may be ready to move to a higher tier plan.

Could you give me a summary of what each plan includes? I am mainly interested in knowing:
- How many users I can add under the business plan
- Whether the higher tier includes priority support
- If there is a discount for paying annually instead of monthly

No rush on this — I just want to make sure I pick the right plan before committing.

Thanks for the great service!
```

> **What to expect from AI:** Category `general`, Priority `low`, Sentiment `positive`. The AI summary will note that this is an upgrade enquiry from a satisfied customer.

---

### Query 4 — Complaint (expected: high priority, negative sentiment)

**Subject:**
```
Extremely disappointed — my issue has been ignored for two weeks
```

**Body:**
```
To whom it may concern,

I submitted a support request on June 1st (reference #47) regarding a feature that stopped working after your last update. It has now been two weeks and I have received no response whatsoever — not even an acknowledgement email.

This feature is critical to my daily workflow and its absence is costing me significant time and money. I am a paying customer on the Professional plan and I expect a reasonable standard of service.

If I do not hear back within 48 hours I will be forced to cancel my subscription and leave a review reflecting my experience.

Account: testcustomer@example.com
Original ticket: #47
```

> **What to expect from AI:** Category `complaint`, Priority `high`, Sentiment `negative`. The AI draft reply will be empathetic and acknowledge the delayed response.

---

### How to submit these

1. Log in as a customer at `/login`.
2. Go to `/portal/submit`.
3. Paste the subject and body from any query above and click **Submit**.
4. The AI classifies the query in the background — refresh the query page after a moment to see the priority, category, and sentiment pills populated, along with the AI summary.
5. Log in as an agent, open the query on the dashboard, and observe the AI-generated draft reply in the conversation thread.

---

## Project Structure

```
Customer_Query_Mgt_System/
├── app/
│   ├── main.py              # FastAPI app, router registration, lifespan
│   ├── config.py            # Settings loaded from .env
│   ├── database.py          # Async SQLAlchemy engine + get_db dependency
│   ├── dependencies.py      # JWT auth dependencies for JSON API routes
│   ├── models/              # SQLAlchemy ORM models (User, Query, Message)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── routers/
│   │   ├── auth.py          # POST /auth/register, /auth/login, GET /auth/me
│   │   ├── queries.py       # JSON API for query CRUD
│   │   ├── portal.py        # HTML customer portal + public /track page
│   │   └── dashboard.py     # HTML agent dashboard + analytics
│   ├── services/
│   │   ├── auth.py          # bcrypt hashing + JWT helpers
│   │   └── ai.py            # Anthropic Claude integration (classify + draft)
│   ├── templates/           # Jinja2 HTML templates
│   └── static/css/          # Single stylesheet (main.css)
├── tests/
│   ├── conftest.py          # Pytest fixtures (test DB, async HTTP client)
│   ├── test_auth_service.py
│   ├── test_ai_service.py
│   └── test_routes.py
├── .env                     # Local environment variables (not committed)
├── .env.example             # Template for .env
├── requirements.txt
├── pytest.ini
└── run.py                   # Entry point: python run.py
```

---

## Key Technology Choices

| Concern | Choice | Reason |
|---|---|---|
| Web framework | FastAPI | Async, auto OpenAPI docs, dependency injection |
| Database | SQLite + aiosqlite | Zero-config, async, sufficient for a university project |
| ORM | SQLAlchemy 2.0 (async) | Modern async API, typed mapped columns |
| Auth | python-jose (JWT) + bcrypt | Stateless tokens, no session storage needed |
| AI | Anthropic Claude (claude-opus-4-8) | Best-in-class classification and text generation |
| Templates | Jinja2 | Server-side rendering, no JS framework required |
| Testing | pytest + pytest-asyncio + httpx | Full async test support with ASGI transport |
