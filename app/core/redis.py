import redis.asyncio as redis
from typing import AsyncGenerator

redis_client = redis.Redis(
    host="redis",
    port=6379,
    decode_responses=True
)

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    yield redis_client