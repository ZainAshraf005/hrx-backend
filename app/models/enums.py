import enum


class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    OWNER = "owner"
    HR_MANAGER = "hr_manager"
    EMPLOYEE = "employee"
