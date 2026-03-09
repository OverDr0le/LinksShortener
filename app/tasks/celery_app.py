from celery import Celery
import asyncio

from uuid import UUID

from app.database import async_session_maker
from app.repositories.link_repository import LinkRepository
from app.config import REDIS_URL

celery_app = Celery(
    "tasks",
    broker=f"{REDIS_URL}/0",
    backend=f"{REDIS_URL}/1",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task
def delete_link_task(link_id: str):
    """
    Удаляет ссылку по ID, если она существует.
    link_id: str (UUID)
    """
    async def delete_async():
        async with async_session_maker() as session:
            repo = LinkRepository(session)
            link = await repo.get_by_id(UUID(link_id))
            if link:
                await repo.delete(link)

    asyncio.run(delete_async())