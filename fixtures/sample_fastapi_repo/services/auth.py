"""Auth service: inherited self-call, own-class self-call, and a bare module-level helper."""

from .base import BaseService


class AuthService(BaseService):
    def login(self, user):
        self.audit("login", user)
        return self.check_password(user)

    def check_password(self, user):
        return True


def get_current_user():
    return {"id": 1, "name": "demo"}


__all__ = ["AuthService", "get_current_user"]
