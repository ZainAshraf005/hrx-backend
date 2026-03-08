from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy import DateTime
from datetime import datetime, UTC


class Base(DeclarativeBase):
    created_at = mapped_column(DateTime, default=datetime.now(UTC))
    updated_at = mapped_column(DateTime, onupdate=datetime.now(UTC))
