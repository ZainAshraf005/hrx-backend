from __future__ import annotations
from app.models.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Enum

from app.models.enums import UserRole


class User(Base):
    __tablename__ = 'users'

    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    password: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(default=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole)
    )
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id")
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="users"
    )
