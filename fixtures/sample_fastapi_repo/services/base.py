"""Base service with a helper method subclasses inherit (D-01)."""


class BaseService:
    def audit(self, action, payload):
        print(action, payload)
