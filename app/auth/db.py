from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_users.db import SQLAlchemyUserDatabase

from app.database import get_session
from app.models.user import User


async def get_user_db(session: AsyncSession = Depends(get_session)) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)