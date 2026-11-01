"""Two route handlers (D-13). Each mixes a resolved call with an unresolved one (D-14)."""

from fastapi import APIRouter, Depends

from ..callers import dispatch
from ..services import AuthService, get_current_user

router = APIRouter()


@router.get("/users/me")
def get_user(user_id: int):
    user = get_current_user()
    auth = AuthService()
    auth.login(user)
    return user


@router.put("/users/{user_id}")
def update_user(user_id: int, payload: dict):
    get_current_user()
    return dispatch("update", payload)
