from enum import Enum
from sqlalchemy import Column, String, Enum as SAEnum
from app.models.base_model import BaseModel


class Status(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class OrganizationApplication(BaseModel):
    __tablename__ = "organization_applications"

    org_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    website = Column(String, nullable=True)
    description = Column(String, nullable=True)
    status = Column(SAEnum(Status), default=Status.PENDING)
