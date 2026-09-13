import asyncio

from app.core.config import AI_INDEX_WORKER_POLL_SECONDS
from app.core.database import AsyncSessionLocal
from app.services.ai.indexing_service import IndexTaskRunner, KnowledgeIndexService
from app.services.ai.provider import XkiroAIProvider


async def run() -> None:
    provider = XkiroAIProvider()
    recovered = False
    while True:
        async with AsyncSessionLocal() as db:
            runner = IndexTaskRunner(
                db,
                KnowledgeIndexService(db, provider),
            )
            if not recovered:
                await runner.recover_stale()
                recovered = True
            processed = await runner.run_one()
        if not processed:
            await asyncio.sleep(AI_INDEX_WORKER_POLL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
