from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import DB_HOST, DB_NAME, DB_PASS, DB_PORT, DB_USER

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=True, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    """
    Dependency for getting database session / Зависимость для получения сессии БД

    Usage in FastAPI / Использование в FastAPI:
        @app.get("/users")
        async def get_users(session: AsyncSession = Depends(get_session)):
            ...

    Yields:
        AsyncSession: Database session / Сессия базы данных
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()