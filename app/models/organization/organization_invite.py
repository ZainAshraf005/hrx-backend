from sqlalchemy import Column, String, DateTime, Boolean, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base_model import BaseModel
from app.models.enums import UserRole, enum_values


class OrganizationInvite(BaseModel):
    __tablename__ = "organization_invites"

    email = Column(String, nullable=False, index=True)

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )

    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # optional but useful
    role = Column(
        SAEnum(UserRole, values_callable=enum_values, name="user_role"),
        nullable=False,
        default=UserRole.ORG_ADMIN,
    )
