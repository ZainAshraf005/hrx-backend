from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.agent_models import (
    AIActionAudit,
    AIActionProposal,
    AIConversation,
)
from app.models.employee.employee_model import Employee
from app.models.enums import (
    AIActionProposalStatus,
    AIConversationMode,
    JobStatus,
    UserRole,
)
from app.models.job.job_application_model import JobApplication
from app.models.job.job_model import Job
from app.models.organization.organization import Organization
from app.models.user.user_model import User
from app.schemas.employee_schema import EmployeeCreate, EmployeeUpdate
from app.schemas.job_application_schema import JobApplicationStatusUpdate
from app.schemas.job_schema import JobCreate, JobUpdate
from app.schemas.organization_schema import OrganizationUpdate
from app.services.employee_service import EmployeeService
from app.services.job_application_service import JobApplicationService
from app.services.job_service import JobService
from app.services.organization_service import OrganizationService


class AIActionService:
    def __init__(
        self,
        db: AsyncSession,
        job_service: JobService,
        application_service: JobApplicationService,
        employee_service: EmployeeService,
        organization_service: OrganizationService,
    ):
        self.db = db
        self.job_service = job_service
        self.application_service = application_service
        self.employee_service = employee_service
        self.organization_service = organization_service

    async def confirm(
        self,
        proposal_id: UUID,
        current_user: User,
        confirmation_key: str,
        frontend_url: str,
    ) -> AIActionProposal:
        if not confirmation_key.strip():
            raise HTTPException(status_code=400, detail="Idempotency-Key is required")

        seed_proposal = await self.db.get(AIActionProposal, proposal_id)
        if not seed_proposal:
            raise HTTPException(status_code=404, detail="Action proposal not found")
        if (
            seed_proposal.proposed_by_user_id != current_user.id
            or seed_proposal.organization_id != current_user.organization_id
        ):
            raise HTTPException(status_code=403, detail="Not Authorized")
        conversation = (
            await self.db.execute(
                select(AIConversation)
                .where(
                    AIConversation.id == seed_proposal.conversation_id,
                    AIConversation.user_id == current_user.id,
                    AIConversation.organization_id == current_user.organization_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="AI conversation not found")
        proposal = await self._locked_proposal(proposal_id)
        if proposal.status == AIActionProposalStatus.EXECUTED:
            if proposal.proposed_by_user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Not Authorized")
            return proposal
        self._validate_pending_proposal(proposal, current_user)
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            await self._expire(proposal, "Action proposal has expired")
            raise HTTPException(status_code=409, detail="Action proposal has expired")

        existing_key = await self.db.scalar(
            select(AIActionProposal.id).where(
                AIActionProposal.confirmation_key == confirmation_key,
                AIActionProposal.id != proposal.id,
            )
        )
        if existing_key:
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key was already used for another proposal",
            )

        if conversation.mode != AIConversationMode.ACTION_MODE:
            await self._expire(proposal, "Conversation is no longer in action mode")
            raise HTTPException(
                status_code=409,
                detail="Conversation is no longer in action mode",
            )

        await self._validate_target_version(proposal)

        proposal.status = AIActionProposalStatus.EXECUTED
        proposal.confirmation_key = confirmation_key
        proposal.executed_at = datetime.now(UTC)
        initial_audit = AIActionAudit(
            organization_id=proposal.organization_id,
            actor_user_id=current_user.id,
            conversation_id=proposal.conversation_id,
            proposal_id=proposal.id,
            event_type="action_execution_started",
            operation=proposal.operation,
            resource_type=proposal.resource_type,
            resource_id=proposal.resource_id,
            details={"preview": proposal.preview},
        )
        self.db.add(initial_audit)
        await self.db.flush()

        try:
            resource = await self._execute(
                proposal,
                current_user,
                frontend_url,
            )
        except HTTPException as exc:
            await self.db.rollback()
            persisted = await self._locked_proposal(proposal_id)
            if persisted.status == AIActionProposalStatus.EXECUTED:
                persisted.error = str(exc.detail)
                warning_result = {
                    "executed": True,
                    "warning": str(exc.detail),
                }
                persisted.result = warning_result
                self.db.add(
                    self._result_audit(
                        persisted,
                        current_user,
                        "action_executed_with_warning",
                        warning_result,
                    )
                )
                await self.db.commit()
                await self.db.refresh(persisted)
                return persisted
            await self._mark_failed(persisted, current_user, str(exc.detail))
            raise
        # The action boundary must convert unknown service failures into a
        # stable API error after recording the proposal outcome.
        except Exception:  # noqa: BLE001
            await self.db.rollback()
            persisted = await self._locked_proposal(proposal_id)
            if persisted.status == AIActionProposalStatus.EXECUTED:
                persisted.error = "The action committed but a follow-up side effect failed"
                warning_result = {
                    "executed": True,
                    "warning": persisted.error,
                }
                persisted.result = warning_result
                self.db.add(
                    self._result_audit(
                        persisted,
                        current_user,
                        "action_executed_with_warning",
                        warning_result,
                    )
                )
                await self.db.commit()
                await self.db.refresh(persisted)
                return persisted
            await self._mark_failed(
                persisted,
                current_user,
                "Action execution failed",
            )
            raise HTTPException(status_code=500, detail="Action execution failed")

        result_payload = {
            "executed": True,
            "resource": self._resource_result(resource),
        }
        proposal.result = result_payload
        if getattr(resource, "id", None):
            proposal.resource_id = resource.id
        self.db.add(
            self._result_audit(
                proposal,
                current_user,
                "action_executed",
                result_payload,
            )
        )
        await self.db.commit()
        await self.db.refresh(proposal)
        return proposal

    async def cancel(
        self,
        proposal_id: UUID,
        current_user: User,
    ) -> AIActionProposal:
        proposal = await self._locked_proposal(proposal_id)
        if proposal.proposed_by_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not Authorized")
        if proposal.status == AIActionProposalStatus.CANCELLED:
            return proposal
        if proposal.status != AIActionProposalStatus.PENDING:
            raise HTTPException(status_code=409, detail="Proposal is no longer pending")
        proposal.status = AIActionProposalStatus.CANCELLED
        self.db.add(
            AIActionAudit(
                organization_id=proposal.organization_id,
                actor_user_id=current_user.id,
                conversation_id=proposal.conversation_id,
                proposal_id=proposal.id,
                event_type="action_cancelled",
                operation=proposal.operation,
                resource_type=proposal.resource_type,
                resource_id=proposal.resource_id,
                details={},
            )
        )
        await self.db.commit()
        await self.db.refresh(proposal)
        return proposal

    async def _execute(
        self,
        proposal: AIActionProposal,
        current_user: User,
        frontend_url: str,
    ) -> Any:
        arguments = proposal.arguments
        if proposal.operation == "create_job_draft":
            data = JobCreate.model_validate(
                {**arguments, "status": JobStatus.DRAFT}
            )
            return await self.job_service.create_job(data, current_user)

        if proposal.operation == "update_job":
            return await self.job_service.update_job(
                UUID(arguments["job_id"]),
                JobUpdate.model_validate(arguments["changes"]),
                current_user,
            )

        if proposal.operation == "deactivate_job":
            return await self.job_service.delete_job(
                UUID(arguments["job_id"]),
                current_user,
            )

        if proposal.operation == "change_application_status":
            return await self.application_service.update_application_status(
                UUID(arguments["application_id"]),
                JobApplicationStatusUpdate.model_validate(
                    {"status": arguments["status"]}
                ),
                current_user,
            )

        if proposal.operation == "invite_employee":
            return await self.employee_service.create_employee(
                EmployeeCreate.model_validate(arguments),
                current_user,
                frontend_url,
            )

        if proposal.operation == "update_employee":
            return await self.employee_service.update_employee(
                UUID(arguments["employee_id"]),
                EmployeeUpdate.model_validate(arguments["changes"]),
                current_user,
            )

        if proposal.operation == "deactivate_employee":
            return await self.employee_service.delete_employee(
                UUID(arguments["employee_id"]),
                current_user,
            )

        if proposal.operation == "update_organization":
            return await self.organization_service.update_own_organization(
                OrganizationUpdate.model_validate(arguments["changes"]),
                current_user,
            )

        raise HTTPException(status_code=400, detail="Unsupported action operation")

    async def _validate_target_version(self, proposal: AIActionProposal) -> None:
        if not proposal.resource_id or not proposal.expected_updated_at:
            return
        model_by_type = {
            "job": Job,
            "application": JobApplication,
            "employee": Employee,
            "organization": Organization,
        }
        if proposal.resource_type is None:
            raise HTTPException(status_code=400, detail="Unsupported action target")
        model = model_by_type.get(proposal.resource_type)
        if not model:
            raise HTTPException(status_code=400, detail="Unsupported action target")
        target = await self.db.get(model, proposal.resource_id)
        if (
            not target
            or getattr(target, "organization_id", target.id)
            != proposal.organization_id
        ):
            await self._expire(proposal, "Target no longer exists")
            raise HTTPException(status_code=409, detail="Action target no longer exists")
        if target.updated_at != proposal.expected_updated_at:
            await self._expire(proposal, "Target changed after proposal")
            raise HTTPException(
                status_code=409,
                detail="Action target changed; generate a new proposal",
            )

    def _validate_pending_proposal(
        self,
        proposal: AIActionProposal,
        current_user: User,
    ) -> None:
        if (
            proposal.proposed_by_user_id != current_user.id
            or proposal.organization_id != current_user.organization_id
            or current_user.role not in {UserRole.ORG_ADMIN, UserRole.HR_MANAGER}
        ):
            raise HTTPException(status_code=403, detail="Not Authorized")
        if proposal.status != AIActionProposalStatus.PENDING:
            raise HTTPException(status_code=409, detail="Proposal is no longer pending")

    async def _locked_proposal(self, proposal_id: UUID) -> AIActionProposal:
        proposal = (
            await self.db.execute(
                select(AIActionProposal)
                .where(AIActionProposal.id == proposal_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if not proposal:
            raise HTTPException(status_code=404, detail="Action proposal not found")
        return proposal

    async def _expire(self, proposal: AIActionProposal, reason: str) -> None:
        proposal.status = AIActionProposalStatus.EXPIRED
        proposal.error = reason
        await self.db.commit()

    async def _mark_failed(
        self,
        proposal: AIActionProposal,
        current_user: User,
        error: str,
    ) -> None:
        proposal.status = AIActionProposalStatus.FAILED
        proposal.error = error
        self.db.add(
            self._result_audit(
                proposal,
                current_user,
                "action_failed",
                {"error": error},
            )
        )
        await self.db.commit()

    def _result_audit(
        self,
        proposal: AIActionProposal,
        current_user: User,
        event_type: str,
        details: dict[str, Any],
    ) -> AIActionAudit:
        return AIActionAudit(
            organization_id=proposal.organization_id,
            actor_user_id=current_user.id,
            conversation_id=proposal.conversation_id,
            proposal_id=proposal.id,
            event_type=event_type,
            operation=proposal.operation,
            resource_type=proposal.resource_type,
            resource_id=proposal.resource_id,
            details=details,
        )

    def _resource_result(self, resource: Any) -> dict[str, Any]:
        if isinstance(resource, Job):
            return {
                "id": str(resource.id),
                "title": resource.title,
                "status": getattr(resource.status, "value", resource.status),
                "is_active": resource.is_active,
            }
        if isinstance(resource, JobApplication):
            return {
                "id": str(resource.id),
                "job_id": str(resource.job_id),
                "candidate_name": resource.candidate_name,
                "status": getattr(resource.status, "value", resource.status),
            }
        if isinstance(resource, Employee):
            return {
                "id": str(resource.id),
                "first_name": resource.first_name,
                "last_name": resource.last_name,
                "designation": resource.designation,
                "is_active": resource.is_active,
            }
        if isinstance(resource, Organization):
            return {
                "id": str(resource.id),
                "name": resource.name,
                "email": resource.email,
                "timezone": resource.timezone,
            }
        return jsonable_encoder(resource)
