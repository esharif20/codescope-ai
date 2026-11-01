"""Multiple callers into routes/services, plus every deliberately unresolvable call pattern (D-14)."""

from .routes.users import get_user
from .services.auth import get_current_user

_HANDLERS = {"create": "handle_create", "update": "handle_update"}


def call_get_user_directly(user_id):
    return get_user(user_id)


def warm_cache():
    get_current_user()


def call_twice():
    get_current_user()
    get_current_user()


def dispatch(action, payload):
    handler_name = _HANDLERS[action]
    handler = getattr(router_handlers, handler_name)
    return handler(payload)


def run_task(callback, request):
    return callback(request)


def process(handler):
    handler.process_item()


router_handlers = object()
