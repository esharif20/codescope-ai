"""Fixture's own test file (D-16) -- parse target only, never collected by the real pytest suite."""

from ..services.auth import AuthService


def test_login_succeeds():
    svc = AuthService()
    assert svc.login({"id": 1}) is True
