"""Source-only registration proofs; analysed modules are never executed."""

import pytest

from app.analysis.imports import extract_raw_imports
from app.analysis.route_resolver import resolve_route_inventory
from app.analysis.routes import extract_route_syntax


def inventory(sources, init_modules=None):
    syntax = {
        module: extract_route_syntax(source, module.replace(".", "/") + ".py", module)
        for module, source in sources.items()
    }
    raw = {
        module: extract_raw_imports(source, module.replace(".", "/") + ".py")
        for module, source in sources.items()
    }
    return resolve_route_inventory(syntax, raw, init_modules or set())


@pytest.mark.parametrize(
    "imports,constructor",
    [
        ("from fastapi import FastAPI", "FastAPI"),
        ("from fastapi import FastAPI as API", "API"),
        ("import fastapi as fa", "fa.FastAPI"),
        ("import fastapi", "fastapi.FastAPI"),
    ],
)
def test_receiver_explicit_constructor(imports, constructor):
    result = inventory(
        {"main": f'{imports}\napp = {constructor}()\n@app.get("/x")\ndef x(): pass\n'}
    )
    assert [(r.app_id, r.path) for r in result.registrations] == [("main:app", "/x")]
    assert result.registrations[0].registration_evidence[0].line == 2


@pytest.mark.parametrize(
    "source",
    [
        "app = fake()",
        "def FastAPI(): pass\napp = FastAPI()",
        "from fastapi import *\napp = FastAPI()",
        "from fastapi import FastAPI\nFastAPI = fake\napp = FastAPI()",
        "from fastapi import FastAPI\napp = FastAPI()\napp = fake",
        "from fastapi import FastAPI\nfrom elsewhere import FastAPI\napp = FastAPI()",
        "import fastapi as fa\nfa = fake\napp = fa.FastAPI()",
        "if False:\n    from fastapi import FastAPI\napp = FastAPI()",
        "def setup():\n    from fastapi import FastAPI\napp = FastAPI()",
        "def setup():\n    import fastapi as fa\napp = fa.FastAPI()",
        "from fastapi import APIRouter\napp = APIRouter(prefix=PREFIX)",
    ],
)
def test_receiver_unproven_or_shadowed(source):
    result = inventory({"main": source + '\n@app.get("/x")\ndef x(): pass\n'})
    assert result.registrations == []
    assert result.diagnostics
    assert all(d.file_path == "main.py" and d.line > 0 for d in result.diagnostics)


def test_receiver_router_declaration_stays_local():
    result = inventory(
        {
            "routes": 'from fastapi import APIRouter as Router\nr = Router()\n@r.get("/x")\ndef x(): pass\n'
        }
    )
    assert result.registrations == []
    assert len(result.declarations) == 1


ROUTES = '''from fastapi import APIRouter
router = APIRouter(prefix="/v1")
@router.get("/users/")
def users(): pass
'''


@pytest.mark.parametrize('module,imports,child,inits', [
    ('main', 'from routes import router as users', 'users', set()),
    ('main', 'import routes as users', 'users.router', set()),
    ('pkg.main', 'from .routes import router as users', 'users', set()),
    ('pkg', 'from .routes import router as users', 'users', {'pkg'}),
    ('pkg.main', 'from . import routes as users', 'users.router', set()),
    ('main', 'import pkg.routes as users', 'users.router', set()),
    ('main', 'import pkg.routes', 'pkg.routes.router', set()),
])
def test_includes_import_forms(module, imports, child, inits):
    target = 'pkg.routes' if module.startswith('pkg') or 'pkg.routes' in imports else 'routes'
    result = inventory({module: f'''from fastapi import FastAPI
{imports}
app = FastAPI()
app.include_router({child}, prefix="/api")
''', target: ROUTES}, inits)
    assert [r.path for r in result.registrations] == ['/api/v1/users/']
    assert [(e.file_path, e.line) for e in result.registrations[0].registration_evidence] == [
        (module.replace('.', '/') + '.py', 3),
        (module.replace('.', '/') + '.py', 4),
        (target.replace('.', '/') + '.py', 2),
    ]


def test_nested_multiple_mounts_cycle_and_disconnected():
    result = inventory({'main': '''from fastapi import FastAPI, APIRouter
app = FastAPI()
outer = APIRouter(prefix="/outer")
inner = APIRouter(prefix="/inner")
lost = APIRouter()
app.include_router(outer, prefix="/a")
app.include_router(outer, prefix="/b")
outer.include_router(inner, prefix="/middle")
inner.include_router(outer)
@inner.get("/x/")
def x(): pass
@lost.get("/lost")
def lost_handler(): pass
'''})
    assert [r.path for r in result.registrations] == [
        '/a/outer/middle/inner/x/', '/b/outer/middle/inner/x/']
    assert any('cycle' in d.reason for d in result.diagnostics)
    assert len(result.declarations) == 2


@pytest.mark.parametrize('imports,child', [
    ('from routes import router\nrouter = fake', 'router'),
    ('import routes as r\nr = fake', 'r.router'),
    ('import routes as r\nif False:\n    r = fake', 'r.router'),
    ('if False:\n    from routes import router', 'router'),
    ('def setup():\n    import routes as r', 'r.router'),
    ('def setup():\n    from routes import router', 'router'),
    ('from routes import *', 'router'),
    ('from bridge import router', 'router'),
    ('import routes as r\nimport routes as r', 'r.router'),
])
def test_include_scope_safety(imports, child):
    result = inventory({'main': f'''from fastapi import FastAPI
{imports}
app = FastAPI()
app.include_router({child})
''', 'routes': ROUTES, 'bridge': 'from routes import router\n'})
    assert result.registrations == []
    assert result.diagnostics
    assert all(d.file_path and d.line > 0 for d in result.diagnostics)
    if '= fake' in imports or imports.count('import routes') > 1:
        assert any('shadow' in d.reason for d in result.diagnostics)


@pytest.mark.parametrize('constructor,include', [
    ('APIRouter(**config)', 'app.include_router(router)'),
    ('APIRouter()', 'app.include_router(router, **options)'),
])
def test_include_argument_unpacking_preserved(constructor, include):
    result = inventory({'main': f'''from fastapi import FastAPI, APIRouter
app = FastAPI()
router = {constructor}
{include}
@router.get("/x")
def x(): pass
'''})
    assert result.registrations == []
    assert any(d.reason == 'argument_unpacking_unsupported' for d in result.diagnostics)


@pytest.mark.parametrize('prefix', ['PREFIX', '"bad"', '"/bad/"', '"/"'])
def test_include_invalid_prefix(prefix):
    result = inventory({'main': f'''from fastapi import FastAPI
from routes import router
app = FastAPI()
app.include_router(router, prefix={prefix})
''', 'routes': ROUTES})
    assert result.registrations == []
    assert result.diagnostics


def test_include_caps_and_determinism(monkeypatch):
    from app.analysis import route_resolver

    sources = {'main': '''from fastapi import FastAPI
from routes import router
app = FastAPI()
app.include_router(router, prefix="/a")
app.include_router(router, prefix="/b")
''', 'routes': ROUTES}
    baseline = inventory(sources)
    assert baseline.model_dump() == inventory(dict(reversed(list(sources.items())))).model_dump()
    assert not baseline.truncated
    monkeypatch.setattr(route_resolver, '_MAX_REGISTRATIONS', 1)
    capped = inventory(sources)
    assert len(capped.registrations) == 1
    assert capped.truncated
    assert any('cap' in d.reason for d in capped.diagnostics)
    monkeypatch.setattr(route_resolver, '_MAX_MOUNT_STEPS', 1)
    assert inventory(sources).truncated
