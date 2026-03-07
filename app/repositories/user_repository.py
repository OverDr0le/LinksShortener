from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from uuid import UUID

from fastapi import Depends

from app.database import get_session
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user: User) -> User:
        """
        Создание нового пользователя в базе данных
        """
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Получение пользователя по ID
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id).options(selectinload(User.links))
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Получение пользователя по email
        """
        result = await self.db.execute(
            select(User).where(User.email == email).options(selectinload(User.links))
        )
        return result.scalar_one_or_none()
    
    async def delete(self, user: User) -> None:
        """
        Удаление пользователя из базы данных
        """
        await self.db.delete(user)
        await self.db.commit()

def get_user_repository(db: AsyncSession = Depends(get_session)) -> UserRepository:
    """
    Dependency для получения репозитория пользователей
    """
    return UserRepository(db)


    