from uuid import UUID
from fastapi_users import FastAPIUsers

from app.models.user import User
from app.auth.manager import get_user_manager
from app.auth.backend import auth_backend

fastapi_users = FastAPIUsers[User, UUID](
    get_user_manager,
    [auth_backend],
)

current_user = fastapi_users.current_user()
current_user_optional = fastapi_users.current_user(optional=True)