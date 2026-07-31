from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import BaseModel
from app.models.enums import UserRole, enum_values


class OrganizationInvite(BaseModel):
    __tablename__ = "organization_invites"

    email: Mapped[str] = mapped_column(String, nullable=False, index=True)

    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    is_used: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # optional but useful
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, values_callable=enum_values, name="user_role"),
        nullable=False,
        default=UserRole.ORG_ADMIN,
    )
