from typing import TYPE_CHECKING
from uuid import UUID as PyUUID

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel
from app.models.enums import UserRole, enum_values

if TYPE_CHECKING:
    from app.models.employee.employee_model import Employee
    from app.models.organization.organization import Organization


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_one_active_hr_per_organization",
            "organization_id",
            unique=True,
            postgresql_where=text(
                "role = 'hr_manager'::user_role AND is_active IS TRUE"
            ),
        ),
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="",
        server_default="",
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    organization_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, values_callable=enum_values, name="user_role"),
        nullable=False,
        default=UserRole.EMPLOYEE,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=True, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)

    organization: Mapped["Organization | None"] = relationship("Organization")
    employee: Mapped["Employee | None"] = relationship(
        "Employee",
        back_populates="user",
        uselist=False,
    )
