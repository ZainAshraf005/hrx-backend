from enum import Enum


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    ORG_ADMIN = "org_admin"
    HR_MANAGER = "hr_manager"
    EMPLOYEE = "employee"


class JobEmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"


class JobWorkplaceType(str, Enum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class JobStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class SalaryPeriod(str, Enum):
    HOURLY = "hourly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class JobApplicationStatus(str, Enum):
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    HIRED = "hired"
