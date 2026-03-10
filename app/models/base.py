from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import DateTime
from datetime import datetime, UTC
import uuid


class Base(DeclarativeBase):
    id = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
