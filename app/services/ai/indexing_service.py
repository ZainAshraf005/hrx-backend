import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (
    AI_INDEX_WORKER_MAX_ATTEMPTS,
    GEMINI_EMBEDDING_MODEL,
)
from app.models.ai.agent_models import AIIndexTask, AIKnowledgeChunk
from app.models.enums import AIIndexTaskStatus, AIKnowledgeSourceType
from app.models.job.job_application_model import JobApplication
from app.models.job.job_model import Job


async def enqueue_index_task(
    db: AsyncSession,
    organization_id: UUID,
    source_type: AIKnowledgeSourceType,
    source_id: UUID,
) -> None:
    now = datetime.now(UTC)
    statement = (
        insert(AIIndexTask)
        .values(
            organization_id=organization_id,
            source_type=source_type,
            source_id=source_id,
            status=AIIndexTaskStatus.PENDING,
            generation=1,
            attempts=0,
            available_at=now,
            locked_at=None,
            claimed_generation=None,
            last_error=None,
        )
        .on_conflict_do_update(
            constraint="uq_ai_index_task_source",
            set_={
                "organization_id": organization_id,
                "status": AIIndexTaskStatus.PENDING,
                "generation": AIIndexTask.generation + 1,
                "attempts": 0,
                "available_at": now,
                "locked_at": None,
                "claimed_generation": None,
                "last_error": None,
                "updated_at": now,
            },
        )
    )
    await db.execute(statement)


class KnowledgeIndexService:
    def __init__(self, db: AsyncSession, embedding_provider: Any):
        self.db = db
        self.embedding_provider = embedding_provider

    async def process(self, task: AIIndexTask) -> None:
        documents = await self._source_documents(task.source_type, task.source_id)
        await self.db.execute(
            delete(AIKnowledgeChunk).where(
                AIKnowledgeChunk.source_type == task.source_type,
                AIKnowledgeChunk.source_id == task.source_id,
            )
        )
        if not documents:
            return

        chunks: list[tuple[str, dict[str, Any]]] = []
        for text, metadata in documents:
            for chunk in self._chunk_text(text):
                chunks.append((chunk, metadata))

        embeddings = await self.embedding_provider.embed_documents(
            [chunk for chunk, _ in chunks]
        )
        for index, ((content, metadata), embedding) in enumerate(zip(chunks, embeddings)):
            self.db.add(
                AIKnowledgeChunk(
                    organization_id=task.organization_id,
                    source_type=task.source_type,
                    source_id=task.source_id,
                    chunk_index=index,
                    content=content,
                    source_metadata=metadata,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    embedding_model=GEMINI_EMBEDDING_MODEL,
                    embedding=embedding,
                )
            )

    async def _source_documents(
        self,
        source_type: AIKnowledgeSourceType,
        source_id: UUID,
    ) -> list[tuple[str, dict[str, Any]]]:
        if source_type == AIKnowledgeSourceType.JOB:
            job = await self.db.get(Job, source_id)
            if not job or not job.is_active:
                return []
            metadata = {
                "source_type": "job",
                "job_id": str(job.id),
                "title": job.title,
            }
            return [
                (f"Job title: {job.title}\nDescription: {job.description}", metadata),
                (
                    "\n".join(
                        part
                        for part in (
                            f"Requirements: {job.requirements}" if job.requirements else "",
                            f"Responsibilities: {job.responsibilities}"
                            if job.responsibilities
                            else "",
                            f"Experience: {job.experience_level}" if job.experience_level else "",
                        )
                        if part
                    ),
                    metadata,
                ),
            ]

        application = await self.db.get(JobApplication, source_id)
        if not application:
            return []
        metadata = {
            "source_type": "application",
            "application_id": str(application.id),
            "job_id": str(application.job_id),
            "candidate_name": application.candidate_name,
        }
        documents = []
        if application.resume_text:
            documents.append((application.resume_text, metadata))
        if application.cover_letter:
            documents.append((f"Cover letter: {application.cover_letter}", metadata))
        if application.summary:
            documents.append((f"Candidate summary: {application.summary}", metadata))
        return documents

    def _chunk_text(self, text: str, size: int = 2400, overlap: int = 300) -> list[str]:
        normalized = " ".join(text.split())
        if not normalized:
            return []
        if len(normalized) <= size:
            return [normalized]

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(start + size, len(normalized))
            if end < len(normalized):
                boundary = normalized.rfind(" ", start, end)
                if boundary > start + size // 2:
                    end = boundary
            chunks.append(normalized[start:end].strip())
            if end >= len(normalized):
                break
            start = max(end - overlap, start + 1)
        return chunks


class IndexTaskRunner:
    def __init__(self, db: AsyncSession, index_service: KnowledgeIndexService):
        self.db = db
        self.index_service = index_service

    async def run_one(self) -> bool:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(AIIndexTask)
            .where(
                AIIndexTask.status.in_(
                    [AIIndexTaskStatus.PENDING, AIIndexTaskStatus.FAILED]
                ),
                AIIndexTask.available_at <= now,
                AIIndexTask.attempts < AI_INDEX_WORKER_MAX_ATTEMPTS,
            )
            .order_by(AIIndexTask.available_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False

        task.status = AIIndexTaskStatus.PROCESSING
        task.claimed_generation = task.generation
        task.locked_at = now
        task.attempts += 1
        claimed_generation = task.generation
        task_id = task.id
        await self.db.commit()

        try:
            await self.index_service.process(task)
        # A worker must persist and reschedule every task failure, regardless
        # of which provider/database exception produced it.
        except Exception as exc:  # noqa: BLE001
            await self.db.rollback()
            task = await self._reload_task_for_update(task_id)
            if not task:
                await self.db.rollback()
                return True
            if task.generation == claimed_generation:
                task.status = AIIndexTaskStatus.FAILED
                task.available_at = datetime.now(UTC) + timedelta(
                    seconds=min(300, 2 ** task.attempts)
                )
                task.last_error = str(exc)[:2000]
            else:
                task.status = AIIndexTaskStatus.PENDING
                task.available_at = datetime.now(UTC)
            task.locked_at = None
            task.claimed_generation = None
            await self.db.commit()
            return True

        task = await self._reload_task_for_update(task_id)
        if not task:
            await self.db.rollback()
            return True
        if task.generation == claimed_generation:
            task.status = AIIndexTaskStatus.COMPLETED
            task.last_error = None
        else:
            task.status = AIIndexTaskStatus.PENDING
            task.available_at = datetime.now(UTC)
        task.locked_at = None
        task.claimed_generation = None
        await self.db.commit()
        return True

    async def _reload_task_for_update(self, task_id: UUID) -> AIIndexTask | None:
        result = await self.db.execute(
            select(AIIndexTask)
            .where(AIIndexTask.id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def recover_stale(self, older_than_seconds: int = 600) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        result = await self.db.execute(
            update(AIIndexTask)
            .where(
                AIIndexTask.status == AIIndexTaskStatus.PROCESSING,
                AIIndexTask.locked_at < cutoff,
            )
            .values(
                status=AIIndexTaskStatus.PENDING,
                available_at=datetime.now(UTC),
                locked_at=None,
                claimed_generation=None,
                last_error="Recovered after worker interruption",
            )
        )
        await self.db.commit()
        return getattr(result, "rowcount", 0) or 0
