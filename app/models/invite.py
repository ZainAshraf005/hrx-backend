from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Invite(Base):
    __tablename__ = "invites"


    email: Mapped[str] = mapped_column(String)

    token: Mapped[str] = mapped_column(String, unique=True)

    role: Mapped[str] = mapped_column(String)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id")
    )

    is_used: Mapped[bool] = mapped_column(default=False)
