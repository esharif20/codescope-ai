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
