import redis.asyncio as redis
from typing import AsyncGenerator
from app.config import REDIS_URL

pool = redis.ConnectionPool.from_url(REDIS_URL)
redis_client = redis.Redis.from_pool(pool)

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    yield redis_client