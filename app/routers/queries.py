from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_customer
from app.models.query import Query
from app.models.user import User
from app.schemas.query import QueryCreate, QueryListItem, QueryResponse

router = APIRouter(prefix="/queries", tags=["queries"])


@router.post(
    "/",
    response_model=QueryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new customer query",
    description=(
        "Creates a query for the authenticated customer. "
        "AI classification (category, priority, sentiment, ai_summary) is applied "
        "asynchronously via the portal form — queries submitted through this JSON API "
        "will have those fields as `null` until classified."
    ),
)
async def submit_query(
    payload: QueryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_customer),
):
    query = Query(
        customer_id=current_user.id,
        subject=payload.subject,
        body=payload.body,
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)
    return query


@router.get(
    "/my",
    response_model=list[QueryListItem],
    summary="List all queries for the authenticated customer",
    description="Returns every query the current customer has submitted, newest first.",
)
async def my_queries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_customer),
):
    result = await db.execute(
        select(Query)
        .where(Query.customer_id == current_user.id)
        .order_by(Query.created_at.desc())
    )
    return result.scalars().all()


@router.get(
    "/{query_id}",
    response_model=QueryResponse,
    summary="Get a single query by ID",
    description=(
        "Retrieve full query details. "
        "Customers may only fetch their own queries; agents can fetch any query. "
        "Returns 404 if the query does not exist, 403 if the customer does not own it."
    ),
)
async def get_query(
    query_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    # customers can only view their own queries
    from app.models.user import UserRole
    if current_user.role == UserRole.customer and query.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return query
