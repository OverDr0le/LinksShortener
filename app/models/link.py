import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Link(Base):
    __tablename__ = "links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    original_url: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    short_url: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True # Это позвляет хранить ссылки для незарегестрировоанных пользователей
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    click_count: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    user:Mapped["User"] = relationship(back_populates="links")

    def __repr__(self):
        return f"<Link(id={self.id}, original_url={self.original_url}, short_url={self.short_url}, created_at={self.created_at})>"
    