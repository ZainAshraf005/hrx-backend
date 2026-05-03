from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base_model import BaseModel


class OrganizationInvite(BaseModel):
    __tablename__ = "organization_invites"

    email = Column(String, nullable=False, index=True)

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )

    otp = Column(String, nullable=False, unique=True, index=True)

    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # optional but useful
    role = Column(String, nullable=False, default="org_admin")
