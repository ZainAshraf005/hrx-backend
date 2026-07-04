import uuid
from sqlalchemy import Column, String, Boolean, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel
from app.models.enums import UserRole, enum_values


class User(BaseModel):
    __tablename__ = "users"

    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)  # set after OTP

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True
    )

    role = Column(
        SAEnum(UserRole, values_callable=enum_values, name="user_role"),
        nullable=False,
        default=UserRole.EMPLOYEE,
    )

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    organization = relationship("Organization")
    employee = relationship("Employee", back_populates="user", uselist=False)
