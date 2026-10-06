from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import BaseModel


class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class OrganizationApplication(BaseModel):
    __tablename__ = "organization_applications"

    org_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[Status] = mapped_column(
        SAEnum(Status),
        nullable=True,
        default=Status.PENDING,
    )
