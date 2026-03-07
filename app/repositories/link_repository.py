from typing import Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.models.link import Link

class LinkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, link: Link) -> Link:
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link

    async def get_by_id(self, link_id: UUID) -> Optional[Link]:
        result = await self.db.execute(select(Link).where(Link.id == link_id))
        return result.scalar_one_or_none()
    
    async def get_by_short_url(self, short_url: str) -> Optional[Link]:
        result = await self.db.execute(select(Link).where(Link.short_url == short_url))
        return result.scalar_one_or_none()
    
    async def get_by_original_url(self, original_url: str) -> Optional[Link]:
        result = await self.db.execute(select(Link).where(Link.original_url == original_url))
        return result.scalar_one_or_none()
    
    async def update(self, link: Link) -> Link:
        await self.db.execute(
            update(Link)
            .where(Link.short_url == link.short_url)
            .values(
                short_url=link.short_url,
                expires_at=link.expires_at
            )
        )
        await self.db.commit()
        return link
    
    async def increment_click_count(self, link: Link) -> None:
        await self.db.execute(
            update(Link)
            .where(Link.short_url == link.short_url)
            .values(
                click_count=Link.click_count + 1,
                last_accessed_at=link.last_accessed_at
            )
        )
        await self.db.commit()

    async def get_link_stats(self, link: Link) -> Optional[Link]:
        result = await self.db.execute(select(Link).where(Link.short_url == link.short_url))
        return result.scalar_one_or_none()

    async def delete(self, link: Link) -> None:
        await self.db.delete(link)
        await self.db.commit()

    async def short_url_exists(self, short_url: str) -> bool:
        result = await self.db.execute(select(Link).where(Link.short_url == short_url))
        return result.scalar_one_or_none() is not None