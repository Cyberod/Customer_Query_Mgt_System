from datetime import datetime
from enum import Enum

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QueryStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class QueryCategory(str, Enum):
    billing = "billing"
    technical = "technical"
    general = "general"
    complaint = "complaint"
    other = "other"


class QueryPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class QuerySentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)

    status: Mapped[QueryStatus] = mapped_column(String(20), default=QueryStatus.open)
    category: Mapped[QueryCategory | None] = mapped_column(String(20), nullable=True)
    priority: Mapped[QueryPriority | None] = mapped_column(String(10), nullable=True)
    sentiment: Mapped[QuerySentiment | None] = mapped_column(String(10), nullable=True)

    # AI-generated summary stored for dashboard display
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped["User"] = relationship(
        "User", back_populates="queries", foreign_keys=[customer_id]
    )
    assigned_agent: Mapped["User | None"] = relationship(
        "User", foreign_keys=[assigned_agent_id]
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="query", cascade="all, delete-orphan"
    )
