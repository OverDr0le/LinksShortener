from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
import redis.asyncio as aioredis

from app.api_routers.links import router as links_router
from app.auth.backend import auth_backend
from app.auth.user import fastapi_users

import uvicorn

app = FastAPI(title="Links Shortener")

app.include_router(links_router)

@app.on_event("startup")
async def startup_redis():
    redis = aioredis.from_url("redis://localhost:6379")
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")



app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"]
)


app.include_router(
    fastapi_users.get_register_router(),
    prefix="/auth",
    tags=["auth"]
)


app.include_router(
    fastapi_users.get_users_router(),
    prefix="/users",
    tags=["users"]
)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )