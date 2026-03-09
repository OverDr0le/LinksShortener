import secrets
import string
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends
import redis.asyncio as redis

from app.models.link import Link
from app.repositories.link_repository import LinkRepository, get_link_repository
from app.schemas.link import LinkCreate, LinkUpdate, LinkResponse, LinkStats
from app.tasks.celery_app import delete_link_task
from app.core.redis import get_redis


class LinkService:
    CACHE_TTL = 3600 # Время жизни кэша в секундах (1 час)

    def __init__(self, repo: LinkRepository,redis: redis.Redis):
        self.repo = repo
        self.redis = redis

    def _generate_short_code(self, length: int = 6) -> str:
        """
        Генерация случайного короткого кода
        """
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))



    def _normalize_expires_at(self, dt: datetime | None) -> datetime | None:
        if not dt:
            return None

        # если пришёл naive datetime (например из формы)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # переводим в UTC
        dt = dt.astimezone(timezone.utc)

        # обрезаем секунды
        dt = dt.replace(second=0, microsecond=0)

        return dt

    def _cache_key(self, short_url:str):
        return f"short_url:{short_url}"

    async def create_link(
        self,
        link_data: LinkCreate,
        user_id: UUID | None = None,
        max_attempts: int = 5
    ) -> Link:
        """
        Создание укороченной ссылки для зарегистрированного или незарегистрированного пользователя
        max_attempts - максимальное количество попыток генерации уникального короткого кода при отсутствии alias
        """
        if link_data.custom_alias:
            existing_link = await self.repo.get_by_short_url(link_data.custom_alias)
            if existing_link:
                raise ValueError(f"Название {link_data.custom_alias} уже занято, выберите другое.")
            short_url = link_data.custom_alias
        else:
            for _ in range(max_attempts):
                short_url = self._generate_short_code()
                existing_link = await self.repo.get_by_short_url(short_url)
                if not existing_link:
                    break
            else:
                raise RuntimeError("Не удалось сгенерировать уникальный короткий код, попробуйте снова.")
            
        normalized_expires = self._normalize_expires_at(link_data.expires_at)

        link = Link(
            original_url=str(link_data.original_url),
            short_url=short_url,
            user_id=user_id,
            expires_at=normalized_expires
        )
        
        link = await self.repo.create(link)

        if link.expires_at:
            delete_link_task.apply_async(
                args=[str(link.id)],
                eta=link.expires_at
            )

        return link

    async def get_link(self, short_url: str) -> Link | None:
        """
        Получение ссылки по короткому коду с использованием кэша Redis для оптимизации производительности
        """
        cache_key = self._cache_key(short_url)
        cached_link = await self.redis.get(cache_key)
        if cached_link:
            return cached_link
        
        link = await self.repo.get_by_short_url(short_url)
        if not link:
            return None
        
        await self.redis.set(cache_key, link.original_url, ex=self.CACHE_TTL)

        return link.original_url

    async def update_link(
        self,
        short_url: str,
        link_data: LinkUpdate,
        current_user_id: UUID
    ) -> Link:
        """
        Обновление ссылки (alias и/или expires_at)
        Доступно только для зарегестрированных пользователей и только для их собственных ссылок
        """
        link = await self.repo.get_by_short_url(short_url)
        if not link:
            raise ValueError("Ссылка не найдена.")
        if not link.user_id:
            raise PermissionError("Незарегистрированные пользователи не могут обновлять ссылки.")
        if link.user_id != current_user_id:
            raise PermissionError("Вы можете обновлять только свои собственные ссылки.")
        
        old_alias = link.short_url
        alias_changed = False

        if link_data.custom_alias:

            existing_link = await self.repo.get_by_short_url(link_data.custom_alias)
            if existing_link and existing_link.id != link.id:
                raise ValueError(f"Название {link_data.custom_alias} уже занято, выберите другое.")
            
            link.short_url = link_data.custom_alias
            alias_changed = True
            


        if link_data.expires_at:
            normalized = self._normalize_expires_at(link_data.expires_at)
            link.expires_at = normalized

            delete_link_task.apply_async(
                args=[str(link.id)],
                eta=link.expires_at
            )
        
        link = await self.repo.update(link)

        # Если изменился alias, обновляем кэш Redis
        if alias_changed:
            await self.redis.delete(self._cache_key(old_alias))
            await self.redis.set(self._cache_key(link.short_url), link.original_url, ex=self.CACHE_TTL)
            
        return link

    async def delete_link(self, short_url: str, current_user_id: UUID) -> None:
        """
        Удаление ссылки
        Доступно только для зарегестрированных пользователей и только для их собственных ссылок
        """
        link = await self.repo.get_by_short_url(short_url)
        if not link:
            raise ValueError("Ссылка не найдена.")
        if not link.user_id:
            raise PermissionError("Незарегистрированные пользователи не могут удалять ссылки.")
        if link.user_id != current_user_id:
            raise PermissionError("Вы можете удалять только свои собственные ссылки.")
        
        await self.repo.delete(link)
        await self.redis.delete(self._cache_key(short_url))

    async def increment_click(self, short_url: str) -> None:
        """
        Обновление статистики переходов по ссылке
        """
        link = await self.repo.get_by_short_url(short_url)
        if not link:
            raise ValueError("Ссылка не найдена.")
        link.click_count += 1
        link.last_accessed_at = datetime.utcnow()
        await self.repo.update(link)

    async def get_stats(self, short_code: str) -> LinkStats:
        """
        Возвращает статистику ссылки
        """
        link = await self.repo.get_by_short_url(short_code)
        if not link:
            raise ValueError("Ссылка не найдена.")
        return LinkStats.from_orm(link)
    
    async def get_by_original_url(self, original_url: str) -> Link | None:
        """
        Получение ссылки по оригинальному URL
        """
        return await self.repo.get_by_original_url(original_url)

    async def to_response(self, link: Link) -> LinkResponse:
        """
        Преобразует ORM объект в Pydantic схему LinkResponse
        """
        return LinkResponse(
            id=link.id,
            original_url=link.original_url,
            short_url=link.short_url,
            user_id=link.user_id,
            created_at=link.created_at,
            expires_at=link.expires_at
        )

async def get_link_service(repo: LinkRepository = Depends(get_link_repository), redis: redis.Redis = Depends(get_redis)) -> AsyncGenerator[LinkService, None]:
    yield LinkService(repo, redis)