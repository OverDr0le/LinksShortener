import uuid

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from app.models.user import User
from app.auth.db import get_user_db
from app.config import SECRET

from typing import AsyncGenerator, Optional


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """
    Управление пользователями:
    - регистрация
    - верификация email
    - сброс пароля
    """
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.id} зарегистрирован.")

    async def on_after_forgot_password(self, user: User, token: str, request: Optional[Request]=None):
        print(f"User {user.id} запросил восстановление пароля. Токен: {token}")

    async def on_after_request_verify(self, user: User, token: str, request: Optional[Request]=None):
        print(f"User {user.id} запросил верификацию. Токен: {token}")


async def get_user_manager(user_db=Depends(get_user_db)) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)