from datetime import datetime

from pydantic import BaseModel

from app.models.query import QueryCategory, QueryPriority, QuerySentiment, QueryStatus


class QueryCreate(BaseModel):
    subject: str
    body: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "subject": "Invoice overcharge — billed twice this month",
                "body": "Hi, I noticed two identical charges on my account for June. "
                        "Please refund the duplicate payment. My account email is john@example.com.",
            }
        }
    }


class QueryResponse(BaseModel):
    id: int
    subject: str
    body: str
    status: QueryStatus
    category: QueryCategory | None
    priority: QueryPriority | None
    sentiment: QuerySentiment | None
    ai_summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QueryListItem(BaseModel):
    id: int
    subject: str
    status: QueryStatus
    category: QueryCategory | None
    priority: QueryPriority | None
    created_at: datetime

    model_config = {"from_attributes": True}
