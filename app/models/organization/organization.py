import uuid
from sqlalchemy import Column, String
from app.models.base_model import BaseModel


class Organization(BaseModel):
    __tablename__ = "organizations"

    name = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=True, unique=True)
    website = Column(String, nullable=True)
    description = Column(String, nullable=True)

