from pydantic import Field, field_validator
from uuid import UUID
from fastapi_users import schemas
from datetime import datetime


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(
        ...,
        min_length =8,
        max_length = 50,
        description = "Пароль должен быть от 8 до 50 символов и содержать как минимум одну заглавную букву, одну строчную букву и одну цифру"
        )

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        Проверка сложности пароля
        """
        if not any(c.isupper() for c in v):
            raise ValueError('Пароль должен содержать заглавную букву')
        if not any(c.islower() for c in v):
            raise ValueError('Пароль должен содержать строчную букву')
        if not any(c.isdigit() for c in v):
            raise ValueError('Пароль должен содержать цифру')
        return v

class UserRead(schemas.BaseUser[UUID]):
    """
    Модель ответа с данными пользователя
    """
    created_at: datetime


class UserUpdate(schemas.BaseUserUpdate):
    """
    Обновление пользователя
    """
    password: str | None = Field(
        None,
        min_length=8,
        max_length=50
    )


    