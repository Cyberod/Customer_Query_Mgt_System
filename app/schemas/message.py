from datetime import datetime

from pydantic import BaseModel


class MessageCreate(BaseModel):
    body: str


class MessageResponse(BaseModel):
    id: int
    query_id: int
    sender_id: int
    body: str
    is_ai_draft: bool
    created_at: datetime

    model_config = {"from_attributes": True}
