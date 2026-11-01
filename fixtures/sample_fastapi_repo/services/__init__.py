"""Re-exports the auth service surface (D-06: one-hop __init__.py re-export)."""

from .auth import AuthService, get_current_user

__all__ = ["AuthService", "get_current_user"]
