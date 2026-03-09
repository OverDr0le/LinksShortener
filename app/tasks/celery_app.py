from celery import Celery
import asyncio

from uuid import UUID

from app.database import async_session_maker
from app.repositories.link_repository import LinkRepository


celery_app = Celery(
    "tasks",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
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