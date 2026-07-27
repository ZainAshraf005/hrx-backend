from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Type
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AI_ACTION_PROPOSAL_TTL_SECONDS
from app.models.ai.agent_models import (
    AIActionProposal,
    AIConversation,
    AIIndexTask,
    AIKnowledgeChunk,
)
from app.models.employee.employee_model import Employee
from app.models.enums import (
    AIActionProposalStatus,
    AIConversationMode,
    AIIndexTaskStatus,
    AIKnowledgeSourceType,
    CandidateRankingStatus,
    JobStatus,
    UserRole,
)
from app.models.job.job_application_model import JobApplication
from app.models.job.job_model import Job
from app.models.organization.organization import Organization
from app.models.user.user_model import User
from app.schemas.employee_schema import EmployeeCreate, EmployeeUpdate
from app.schemas.job_schema import JobCreate, JobUpdate
from app.schemas.organization_schema import OrganizationUpdate
from app.services.ai.provider import AgentToolDefinition, AIProvider
from app.services.ai.tool_schemas import (
    ApplicationIdParams,
    ApplicationListParams,
    ApplicationQueryParams,
    ChangeApplicationStatusParams,
    CreateJobDraftParams,
    EmployeeIdParams,
    EmployeeQueryParams,
    EmptyParams,
    InviteEmployeeParams,
    JobIdParams,
    SearchJobsParams,
    SemanticSearchParams,
    ToolParams,
    TopApplicantsParams,
    UpdateEmployeeParams,
    UpdateJobParams,
    UpdateOrganizationParams,
)
from app.services.employee_service import EmployeeService
from app.services.job_application_service import JobApplicationService
from app.services.job_service import JobService
from app.services.organization_service import OrganizationService


READ_ROLES = {UserRole.ORG_ADMIN, UserRole.HR_MANAGER}
ORG_ADMIN_ONLY = {UserRole.ORG_ADMIN}


class AgentToolService:
    def __init__(
        self,
        db: AsyncSession,
        provider: AIProvider,
        job_service: JobService,
        application_service: JobApplicationService,
        employee_service: EmployeeService,
        organization_service: OrganizationService,
    ):
        self.db = db
        self.provider = provider
        self.job_service = job_service
        self.application_service = application_service
        self.employee_service = employee_service
        self.organization_service = organization_service
        self._definitions = self._build_definitions()

    def definitions(self, mode: AIConversationMode, current_user: User) -> list[AgentToolDefinition]:
        self.require_agent_user(current_user)
        definitions = [
            definition
            for definition, allowed_roles in self._definitions.values()
            if not definition.mutation and current_user.role in allowed_roles
        ]
        if mode == AIConversationMode.ACTION_MODE:
            for definition, allowed_roles in self._definitions.values():
                if definition.mutation and current_user.role in allowed_roles:
                    definitions.append(definition)
        return definitions

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        conversation_id: UUID,
        mode: AIConversationMode,
        current_user: User,
    ) -> dict[str, Any]:
        self.require_agent_user(current_user)
        entry = self._definitions.get(name)
        if not entry:
            return {"ok": False, "error": "Unsupported tool"}
        definition, allowed_roles = entry
        if current_user.role not in allowed_roles:
            return {"ok": False, "error": "Not Authorized"}
        if definition.mutation and mode != AIConversationMode.ACTION_MODE:
            return {
                "ok": False,
                "error": "This conversation is in read mode. Switch to action mode first.",
            }
        if definition.mutation:
            conversation = (
                await self.db.execute(
                    select(AIConversation)
                    .where(
                        AIConversation.id == conversation_id,
                        AIConversation.user_id == current_user.id,
                        AIConversation.organization_id == current_user.organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if not conversation:
                return {"ok": False, "error": "AI conversation not found"}
            if conversation.mode != AIConversationMode.ACTION_MODE:
                return {
                    "ok": False,
                    "error": "This conversation is no longer in action mode.",
                }

        try:
            params = self._validate_params(name, arguments)
            result = await getattr(self, f"_tool_{name}")(
                params,
                conversation_id,
                current_user,
            )
            return {"ok": True, **result}
        except ValidationError as exc:
            return {"ok": False, "error": "Invalid tool arguments", "details": exc.errors()}
        except HTTPException as exc:
            return {"ok": False, "error": str(exc.detail), "status_code": exc.status_code}
        except Exception:
            return {"ok": False, "error": "Tool execution failed"}

    def is_mutation_tool(self, name: str) -> bool:
        entry = self._definitions.get(name)
        return bool(entry and entry[0].mutation)

    @staticmethod
    def require_agent_user(current_user: User) -> UUID:
        if current_user.role not in READ_ROLES or not current_user.organization_id:
            raise HTTPException(status_code=403, detail="AI agent is not available for this role")
        return current_user.organization_id

    async def _tool_get_organization(
        self,
        params: EmptyParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        organization = await self.db.get(Organization, current_user.organization_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        return {
            "kind": "organization",
            "data": self._organization_data(organization),
        }

    async def _tool_search_jobs(
        self,
        params: SearchJobsParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        query = select(Job).where(Job.organization_id == current_user.organization_id)
        if params.title:
            query = query.where(Job.title.ilike(f"%{params.title}%"))
        if params.department:
            query = query.where(Job.department.ilike(f"%{params.department}%"))
        if params.status:
            query = query.where(Job.status == params.status)
        query = self._apply_date_range(
            query,
            Job.created_at,
            params.created_from,
            params.created_to,
            await self._organization_timezone(current_user.organization_id),
        )
        total = await self.db.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        result = await self.db.execute(
            query.order_by(Job.created_at.desc()).limit(params.limit)
        )
        jobs = result.scalars().all()
        return {
            "kind": "jobs",
            "data": [self._job_summary(job) for job in jobs],
            "count": total or 0,
            "returned_count": len(jobs),
        }

    async def _tool_get_job(
        self,
        params: JobIdParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        job = await self.job_service.get_organization_job(params.job_id, current_user)
        return {"kind": "job", "data": self._job_data(job)}

    async def _tool_count_applications(
        self,
        params: ApplicationQueryParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        query = (
            select(JobApplication.status, func.count(JobApplication.id))
            .where(JobApplication.organization_id == current_user.organization_id)
            .group_by(JobApplication.status)
        )
        if params.job_id:
            await self.job_service.get_organization_job(params.job_id, current_user)
            query = query.where(JobApplication.job_id == params.job_id)
        if params.status:
            query = query.where(JobApplication.status == params.status)
        query = self._apply_date_range(
            query,
            JobApplication.created_at,
            params.created_from,
            params.created_to,
            await self._organization_timezone(current_user.organization_id),
        )
        rows = (await self.db.execute(query)).all()
        by_status = {self._enum_value(status): count for status, count in rows}
        return {
            "kind": "application_counts",
            "data": {
                "total": sum(by_status.values()),
                "by_status": by_status,
                "job_id": str(params.job_id) if params.job_id else None,
            },
        }

    async def _tool_list_applications(
        self,
        params: ApplicationListParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        query = select(JobApplication).where(
            JobApplication.organization_id == current_user.organization_id
        )
        if params.job_id:
            await self.job_service.get_organization_job(params.job_id, current_user)
            query = query.where(JobApplication.job_id == params.job_id)
        if params.status:
            query = query.where(JobApplication.status == params.status)
        query = self._apply_date_range(
            query,
            JobApplication.created_at,
            params.created_from,
            params.created_to,
            await self._organization_timezone(current_user.organization_id),
        )
        if params.sort == "rank":
            query = query.order_by(
                case(
                    (
                        JobApplication.ranking_status == CandidateRankingStatus.COMPLETED,
                        0,
                    ),
                    else_=1,
                ),
                JobApplication.ranking_score.desc().nullslast(),
                JobApplication.created_at.desc(),
            )
        else:
            query = query.order_by(JobApplication.created_at.desc())
        count_query = query.order_by(None)
        total = await self.db.scalar(
            select(func.count()).select_from(count_query.subquery())
        )
        applications = (
            await self.db.execute(query.limit(params.limit))
        ).scalars().all()
        return {
            "kind": "applications",
            "data": [self._application_data(item) for item in applications],
            "count": total or 0,
            "returned_count": len(applications),
        }

    async def _tool_top_ranked_applicants(
        self,
        params: TopApplicantsParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        await self.job_service.get_organization_job(params.job_id, current_user)
        result = await self.db.execute(
            select(JobApplication)
            .where(
                JobApplication.organization_id == current_user.organization_id,
                JobApplication.job_id == params.job_id,
                JobApplication.ranking_status == CandidateRankingStatus.COMPLETED,
            )
            .order_by(
                JobApplication.ranking_score.desc().nullslast(),
                JobApplication.created_at.desc(),
            )
            .limit(params.limit)
        )
        applications = result.scalars().all()
        return {
            "kind": "ranked_applicants",
            "data": [self._application_data(item) for item in applications],
            "count": len(applications),
            "ranking_source": "persisted_candidate_ranking",
        }

    async def _tool_get_application(
        self,
        params: ApplicationIdParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        application = await self.application_service.get_application(
            params.application_id,
            current_user,
        )
        return {"kind": "application", "data": self._application_data(application)}

    async def _tool_semantic_search_recruiting(
        self,
        params: SemanticSearchParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        query_vector = await self.provider.embed_query(params.query)
        distance = AIKnowledgeChunk.embedding.cosine_distance(query_vector)
        query = (
            select(AIKnowledgeChunk, distance.label("distance"))
            .where(AIKnowledgeChunk.organization_id == current_user.organization_id)
            .order_by(distance)
            .limit(params.limit)
        )
        if params.source_type:
            query = query.where(
                AIKnowledgeChunk.source_type == AIKnowledgeSourceType(params.source_type)
            )
        rows = (await self.db.execute(query)).all()
        pending = await self.db.scalar(
            select(func.count(AIIndexTask.id)).where(
                AIIndexTask.organization_id == current_user.organization_id,
                AIIndexTask.status != AIIndexTaskStatus.COMPLETED,
            )
        )
        return {
            "kind": "semantic_results",
            "data": [
                {
                    "source_type": self._enum_value(chunk.source_type),
                    "source_id": str(chunk.source_id),
                    "snippet": chunk.content[:800],
                    "metadata": chunk.source_metadata,
                    "similarity": round(max(0.0, 1.0 - float(raw_distance)), 4),
                }
                for chunk, raw_distance in rows
            ],
            "indexing_incomplete": bool(pending),
        }

    async def _tool_list_employees(
        self,
        params: EmployeeQueryParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        employees = await self.employee_service.get_employees(
            current_user,
            params.include_inactive,
        )
        if params.role:
            employees = [item for item in employees if item.user.role == params.role]
        total = len(employees)
        employees = employees[: params.limit]
        return {
            "kind": "employees",
            "data": [self._employee_data(item) for item in employees],
            "count": total,
            "returned_count": len(employees),
        }

    async def _tool_get_employee(
        self,
        params: EmployeeIdParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        employee = await self.employee_service.get_employee(
            params.employee_id,
            current_user,
        )
        return {"kind": "employee", "data": self._employee_data(employee)}

    async def _tool_propose_create_job_draft(
        self,
        params: CreateJobDraftParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        values = params.model_dump(mode="json")
        values["status"] = JobStatus.DRAFT.value
        JobCreate.model_validate(values)
        self.job_service._validate_salary_range(
            params.salary_min,
            params.salary_max,
        )
        return await self._create_proposal(
            conversation_id,
            current_user,
            operation="create_job_draft",
            arguments=values,
            preview={
                "summary": f"Create draft job “{params.title}”",
                "before": None,
                "after": values,
            },
            resource_type="job",
        )

    async def _tool_propose_update_job(
        self,
        params: UpdateJobParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        job = await self.job_service.get_organization_job(params.job_id, current_user)
        changes = params.model_dump(mode="json", exclude_unset=True)
        changes.pop("job_id", None)
        if not changes:
            raise HTTPException(status_code=400, detail="No job changes were provided")
        JobUpdate.model_validate(changes)
        self.job_service._validate_salary_range(
            changes.get("salary_min", job.salary_min),
            changes.get("salary_max", job.salary_max),
        )
        before = self._job_data(job)
        after = {**before, **changes}
        return await self._create_proposal(
            conversation_id,
            current_user,
            operation="update_job",
            arguments={"job_id": str(job.id), "changes": changes},
            preview={
                "summary": f"Update job “{job.title}”",
                "before": before,
                "after": after,
            },
            resource_type="job",
            resource_id=job.id,
            expected_updated_at=job.updated_at,
        )

    async def _tool_propose_deactivate_job(
        self,
        params: JobIdParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        job = await self.job_service.get_organization_job(params.job_id, current_user)
        before = self._job_data(job)
        return await self._create_proposal(
            conversation_id,
            current_user,
            operation="deactivate_job",
            arguments={"job_id": str(job.id)},
            preview={
                "summary": f"Deactivate job “{job.title}”",
                "before": before,
                "after": {**before, "is_active": False},
            },
            resource_type="job",
            resource_id=job.id,
            expected_updated_at=job.updated_at,
        )

    async def _tool_propose_change_application_status(
        self,
        params: ChangeApplicationStatusParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        application = await self.application_service.get_application(
            params.application_id,
            current_user,
        )
        return await self._create_proposal(
            conversation_id,
            current_user,
            operation="change_application_status",
            arguments={
                "application_id": str(application.id),
                "status": params.status.value,
            },
            preview={
                "summary": (
                    f"Change {application.candidate_name} from "
                    f"{self._enum_value(application.status)} to {params.status.value}"
                ),
                "before": {"status": self._enum_value(application.status)},
                "after": {"status": params.status.value},
            },
            resource_type="application",
            resource_id=application.id,
            expected_updated_at=application.updated_at,
        )

    async def _tool_propose_invite_employee(
        self,
        params: InviteEmployeeParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        values = params.model_dump(mode="json")
        EmployeeCreate.model_validate(values)
        return await self._create_proposal(
            conversation_id,
            current_user,
            operation="invite_employee",
            arguments=values,
            preview={
                "summary": f"Invite {params.first_name} {params.last_name} as {params.role.value}",
                "before": None,
                "after": values,
            },
            resource_type="employee",
        )

    async def _tool_propose_update_employee(
        self,
        params: UpdateEmployeeParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        employee = await self.employee_service.get_employee(params.employee_id, current_user)
        changes = params.model_dump(mode="json", exclude_unset=True)
        changes.pop("employee_id", None)
        if not changes:
            raise HTTPException(status_code=400, detail="No employee changes were provided")
        EmployeeUpdate.model_validate(changes)
        before = self._employee_data(employee)
        return await self._create_proposal(
            conversation_id,
            current_user,
            operation="update_employee",
            arguments={"employee_id": str(employee.id), "changes": changes},
            preview={
                "summary": f"Update employee {employee.first_name} {employee.last_name}",
                "before": before,
                "after": {**before, **changes},
            },
            resource_type="employee",
            resource_id=employee.id,
            expected_updated_at=employee.updated_at,
        )

    async def _tool_propose_deactivate_employee(
        self,
        params: EmployeeIdParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        employee = await self.employee_service.get_employee(params.employee_id, current_user)
        before = self._employee_data(employee)
        return await self._create_proposal(
            conversation_id,
            current_user,
            operation="deactivate_employee",
            arguments={"employee_id": str(employee.id)},
            preview={
                "summary": f"Deactivate employee {employee.first_name} {employee.last_name}",
                "before": before,
                "after": {**before, "is_active": False},
            },
            resource_type="employee",
            resource_id=employee.id,
            expected_updated_at=employee.updated_at,
        )

    async def _tool_propose_update_organization(
        self,
        params: UpdateOrganizationParams,
        conversation_id: UUID,
        current_user: User,
    ) -> dict[str, Any]:
        organization = await self.organization_service.get_own_organization(current_user)
        changes = params.model_dump(mode="json", exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=400, detail="No organization changes were provided")
        OrganizationUpdate.model_validate(changes)
        before = self._organization_data(organization)
        return await self._create_proposal(
            conversation_id,
            current_user,
            operation="update_organization",
            arguments={"changes": changes},
            preview={
                "summary": f"Update organization “{organization.name}”",
                "before": before,
                "after": {**before, **changes},
            },
            resource_type="organization",
            resource_id=organization.id,
            expected_updated_at=organization.updated_at,
        )

    async def _create_proposal(
        self,
        conversation_id: UUID,
        current_user: User,
        operation: str,
        arguments: dict[str, Any],
        preview: dict[str, Any],
        resource_type: str,
        resource_id: UUID | None = None,
        expected_updated_at: datetime | None = None,
    ) -> dict[str, Any]:
        result = await self.db.execute(
            select(AIActionProposal).where(
                AIActionProposal.conversation_id == conversation_id,
                AIActionProposal.status == AIActionProposalStatus.PENDING,
            )
        )
        for pending in result.scalars().all():
            pending.status = AIActionProposalStatus.CANCELLED

        proposal = AIActionProposal(
            conversation_id=conversation_id,
            proposed_by_user_id=current_user.id,
            organization_id=current_user.organization_id,
            operation=operation,
            arguments=arguments,
            preview=preview,
            resource_type=resource_type,
            resource_id=resource_id,
            expected_updated_at=expected_updated_at,
            status=AIActionProposalStatus.PENDING,
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=AI_ACTION_PROPOSAL_TTL_SECONDS),
        )
        self.db.add(proposal)
        await self.db.commit()
        await self.db.refresh(proposal)
        return {
            "kind": "action_proposal",
            "proposal": {
                "id": str(proposal.id),
                "operation": proposal.operation,
                "preview": proposal.preview,
                "resource_type": proposal.resource_type,
                "resource_id": str(proposal.resource_id) if proposal.resource_id else None,
                "expires_at": proposal.expires_at.isoformat(),
            },
        }

    def _validate_params(self, name: str, arguments: dict[str, Any]) -> ToolParams:
        model = self._parameter_models()[name]
        return model.model_validate(arguments)

    def _build_definitions(
        self,
    ) -> dict[str, tuple[AgentToolDefinition, set[UserRole]]]:
        descriptions = {
            "get_organization": "Get the caller's HRX organization details.",
            "search_jobs": "Search and filter jobs in the caller's organization.",
            "get_job": "Get one exact organization job by UUID.",
            "count_applications": "Count applications, optionally by job, status, or date range.",
            "list_applications": "List organization applications with controlled filters and ordering.",
            "top_ranked_applicants": "Return applicants ordered only by their persisted completed ranking scores.",
            "get_application": "Get one exact application by UUID.",
            "semantic_search_recruiting": "Semantically search organization job and applicant text. Use for concepts or skills, not counts or ranking.",
            "list_employees": "List employees. Available only to organization admins.",
            "get_employee": "Get one exact employee. Available only to organization admins.",
            "propose_create_job_draft": "Prepare, but do not execute, creation of one draft job.",
            "propose_update_job": "Prepare, but do not execute, one exact job update.",
            "propose_deactivate_job": "Prepare, but do not execute, deactivation of one exact job.",
            "propose_change_application_status": "Prepare, but do not execute, one exact application status change. Map 'approve' to shortlisted.",
            "propose_invite_employee": "Prepare, but do not execute, one employee invitation. Organization admins only.",
            "propose_update_employee": "Prepare, but do not execute, one employee update. Organization admins only.",
            "propose_deactivate_employee": "Prepare, but do not execute, one employee deactivation. Organization admins only.",
            "propose_update_organization": "Prepare, but do not execute, an organization update. Organization admins only.",
        }
        mutation_names = {
            name for name in descriptions if name.startswith("propose_")
        }
        org_admin_names = {
            "list_employees",
            "get_employee",
            "propose_invite_employee",
            "propose_update_employee",
            "propose_deactivate_employee",
            "propose_update_organization",
        }
        models = self._parameter_models()
        return {
            name: (
                AgentToolDefinition(
                    name=name,
                    description=description,
                    parameters=self._inline_schema(models[name].model_json_schema()),
                    mutation=name in mutation_names,
                ),
                ORG_ADMIN_ONLY if name in org_admin_names else READ_ROLES,
            )
            for name, description in descriptions.items()
        }

    def _parameter_models(self) -> dict[str, Type[ToolParams]]:
        return {
            "get_organization": EmptyParams,
            "search_jobs": SearchJobsParams,
            "get_job": JobIdParams,
            "count_applications": ApplicationQueryParams,
            "list_applications": ApplicationListParams,
            "top_ranked_applicants": TopApplicantsParams,
            "get_application": ApplicationIdParams,
            "semantic_search_recruiting": SemanticSearchParams,
            "list_employees": EmployeeQueryParams,
            "get_employee": EmployeeIdParams,
            "propose_create_job_draft": CreateJobDraftParams,
            "propose_update_job": UpdateJobParams,
            "propose_deactivate_job": JobIdParams,
            "propose_change_application_status": ChangeApplicationStatusParams,
            "propose_invite_employee": InviteEmployeeParams,
            "propose_update_employee": UpdateEmployeeParams,
            "propose_deactivate_employee": EmployeeIdParams,
            "propose_update_organization": UpdateOrganizationParams,
        }

    def _inline_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        definitions = schema.get("$defs", {})

        def resolve(value: Any) -> Any:
            if isinstance(value, list):
                return [resolve(item) for item in value]
            if not isinstance(value, dict):
                return value
            reference = value.get("$ref")
            if reference and reference.startswith("#/$defs/"):
                name = reference.rsplit("/", 1)[-1]
                return resolve(definitions[name])
            return {
                key: resolve(item)
                for key, item in value.items()
                if key != "$defs"
            }

        return resolve(schema)

    async def _organization_timezone(self, organization_id: UUID) -> str:
        value = await self.db.scalar(
            select(Organization.timezone).where(Organization.id == organization_id)
        )
        return value or "Asia/Karachi"

    def _apply_date_range(
        self,
        query,
        column,
        start: date | None,
        end: date | None,
        timezone_name: str,
    ):
        zone = ZoneInfo(timezone_name)
        if start:
            start_at = datetime.combine(start, time.min, tzinfo=zone).astimezone(timezone.utc)
            query = query.where(column >= start_at)
        if end:
            end_at = datetime.combine(
                end + timedelta(days=1),
                time.min,
                tzinfo=zone,
            ).astimezone(timezone.utc)
            query = query.where(column < end_at)
        return query

    def _job_data(self, job: Job) -> dict[str, Any]:
        return {
            "id": str(job.id),
            "title": job.title,
            "description": job.description,
            "department": job.department,
            "location": job.location,
            "employment_type": self._enum_value(job.employment_type),
            "workplace_type": self._enum_value(job.workplace_type),
            "status": self._enum_value(job.status),
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "salary_period": self._enum_value(job.salary_period),
            "experience_level": job.experience_level,
            "requirements": job.requirements,
            "responsibilities": job.responsibilities,
            "benefits": job.benefits,
            "is_active": job.is_active,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }

    def _job_summary(self, job: Job) -> dict[str, Any]:
        return {
            "id": str(job.id),
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "employment_type": self._enum_value(job.employment_type),
            "workplace_type": self._enum_value(job.workplace_type),
            "status": self._enum_value(job.status),
            "experience_level": job.experience_level,
            "is_active": job.is_active,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }

    def _application_data(self, application: JobApplication) -> dict[str, Any]:
        return {
            "id": str(application.id),
            "job_id": str(application.job_id),
            "candidate_name": application.candidate_name,
            "status": self._enum_value(application.status),
            "ranking_score": application.ranking_score,
            "ranking_recommendation": self._enum_value(
                application.ranking_recommendation
            ),
            "ranking_rationale": application.ranking_rationale,
            "ranking_strengths": application.ranking_strengths,
            "ranking_gaps": application.ranking_gaps,
            "ranking_status": self._enum_value(application.ranking_status),
            "created_at": application.created_at.isoformat(),
            "updated_at": application.updated_at.isoformat(),
        }

    def _employee_data(self, employee: Employee) -> dict[str, Any]:
        return {
            "id": str(employee.id),
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "designation": employee.designation,
            "role": self._enum_value(employee.user.role),
            "is_active": employee.is_active,
            "created_at": employee.created_at.isoformat(),
            "updated_at": employee.updated_at.isoformat(),
        }

    def _organization_data(self, organization: Organization) -> dict[str, Any]:
        return {
            "id": str(organization.id),
            "name": organization.name,
            "email": organization.email,
            "website": organization.website,
            "description": organization.description,
            "timezone": organization.timezone,
            "updated_at": organization.updated_at.isoformat(),
        }

    def _enum_value(self, value: Any) -> Any:
        return getattr(value, "value", value)
