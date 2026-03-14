from __future__ import annotations
from typing import List
from app.models.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean


class Organization(Base):
    __tablename__ = 'organizations'

    name: Mapped[str] = mapped_column(String)
    industry: Mapped[str] = mapped_column(String, nullable=True)
    company_size: Mapped[str] = mapped_column(String, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)

    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="organization",
    )
