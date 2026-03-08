from app.models.base import Base
from sqlalchemy.orm import  Mapped, mapped_column


class Organization(Base):
    __tablename__ = 'organization'

    id: Mapped[int] = mapped_column(primary_key=True)