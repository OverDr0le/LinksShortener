from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
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


class UserResponse(BaseModel):
    """
    Модель ответа с данными пользователя (без пароля)
    """
    id: UUID
    email: EmailStr
    created_at: datetime


    