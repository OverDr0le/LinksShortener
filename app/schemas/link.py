from typing import Optional

from pydantic import BaseModel, HttpUrl, Field, ConfigDict
from datetime import datetime
from uuid import UUID


class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        description="Пользовательский псевдоним для короткой ссылки (опционально)"
        )
    expires_at: Optional[datetime] = Field(
        None,
        description="Дата и время с точностью до минуты истечения срока действия ссылки (опционально)"
        )
    
class LinkResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    original_url: HttpUrl
    short_url: str
    created_at: datetime
    expires_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class LinkStats(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    original_url: HttpUrl
    short_url: str
    created_at: datetime = Field(
        ...,
        description = "Дата и время создания ссылки"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Дата и время истечения срока действия ссылки"
    )
    click_count: int
    last_accessed_at: Optional[datetime] = Field(
        None,
        description="Дата и время последнего доступа к ссылке"
    )

    model_config = ConfigDict(from_attributes=True)

class LinkUpdate(BaseModel):
    expires_at: Optional[datetime] = Field(
        None,
        description="Новая дата и время с точностью до минуты истечения срока действия ссылки (опционально)"
    )
    custom_alias: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        description="Новый пользовательский псевдоним для короткой ссылки (опционально)"
    )

class LinkSearchResponse(BaseModel):
    short_url: str
    original_url: HttpUrl

    

