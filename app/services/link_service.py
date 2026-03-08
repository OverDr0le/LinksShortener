import secrets
import string
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID
from fastapi import Depends

from app.models.link import Link
from app.repositories.link_repository import LinkRepository, get_link_repository
from app.schemas.link import LinkCreate, LinkUpdate, LinkResponse, LinkStats


class LinkService:
    def __init__(self, repo: LinkRepository):
        self.repo = repo

    def _generate_short_code(self, length: int = 6) -> str:
        """
        Генерация случайного короткого кода
        """
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

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
            
        link = Link(
            original_url=link_data.original_url,
            short_url=short_url,
            user_id=user_id,
            expires_at=link_data.expires_at
        )
        return await self.repo.create(link)

    async def get_link(self, short_url: str) -> Link | None:
        """
        Получение ссылки по короткому коду
        """
        return await self.repo.get_by_short_url(short_url)

    async def update_link(
        self,
        link: Link,
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
        if link_data.custom_alias:
            existing_link = await self.repo.get_by_short_url(link_data.custom_alias)
            if existing_link and existing_link.id != link.id:
                raise ValueError(f"Название {link_data.custom_alias} уже занято, выберите другое.")
            
            link.short_url = link_data.custom_alias
        if link_data.expires_at:
            link.expires_at = link_data.expires_at

        return await self.repo.update(link)

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

    async def increment_click(self, link: Link) -> None:
        """
        Обновление статистики переходов по ссылке
        """
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
        return LinkStats(
            id=link.id,
            original_url=link.original_url,
            short_url=link.short_url,
            created_at=link.created_at,
            expires_at=link.expires_at,
            click_count=link.click_count,
            last_accessed_at=link.last_accessed_at
        )
    
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

async def get_link_service(repo: LinkRepository = Depends(get_link_repository)) -> AsyncGenerator[LinkService, None]:
    yield LinkService(repo)