"""Tests for app.analysis.calls raw call-expression extraction.

These tests are written against the pinned contract in
`.planning/phases/02-imports-resolution-call-graph/02-04-PLAN.md`'s
<interfaces>/<behavior> sections. `extract_raw_calls` does not resolve
anything -- these tests only assert the raw, pre-resolution shape.
"""

from __future__ import annotations

from app.analysis.calls import RawCall, extract_raw_calls

# ---------------------------------------------------------------------------
# Task 1: extract_raw_calls -- receiver classification
# ---------------------------------------------------------------------------


def test_call_bare_name_inside_function():
    source = "def foo():\n    bar()\n"
    calls = extract_raw_calls(source, "module.py")

    assert len(calls) == 1
    call = calls[0]
    assert isinstance(call, RawCall)
    assert call.enclosing_symbol == "foo"
    assert call.receiver_kind == "bare"
    assert call.expression == "bar"
    assert call.line == 2
    assert call.file_path == "module.py"


def test_call_self_receiver_inside_method():
    source = "class C:\n    def m(self):\n        self.bar()\n"
    calls = extract_raw_calls(source, "module.py")

    assert len(calls) == 1
    call = calls[0]
    assert call.enclosing_symbol == "C.m"
    assert call.receiver_kind == "self"
    assert call.expression == "self.bar"
    assert call.line == 3


def test_call_cls_receiver_classified_syntactically_not_by_decorator():
    # D-04: classify by literal receiver text "cls", not by @classmethod.
    source = "class C:\n    def m(cls):\n        cls.bar()\n"
    calls = extract_raw_calls(source, "module.py")

    assert len(calls) == 1
    call = calls[0]
    assert call.enclosing_symbol == "C.m"
    assert call.receiver_kind == "cls"
    assert call.expression == "cls.bar"


def test_call_attribute_receiver_single_segment():
    source = "def foo():\n    obj.baz()\n"
    calls = extract_raw_calls(source, "module.py")

    assert len(calls) == 1
    call = calls[0]
    assert call.enclosing_symbol == "foo"
    assert call.receiver_kind == "attribute"
    assert call.expression == "obj.baz"


def test_call_attribute_receiver_chained_full_text():
    source = "def foo():\n    a.b.c()\n"
    calls = extract_raw_calls(source, "module.py")

    assert len(calls) == 1
    call = calls[0]
    assert call.receiver_kind == "attribute"
    assert call.expression == "a.b.c"


def test_call_at_module_level_produces_no_raw_call():
    source = "foo()\n"
    calls = extract_raw_calls(source, "module.py")

    assert calls == []


def test_call_inside_class_body_outside_method_produces_no_raw_call():
    source = "class C:\n    x = foo()\n"
    calls = extract_raw_calls(source, "module.py")

    assert calls == []


def test_multiple_calls_inside_one_function_body():
    source = "def foo():\n    bar()\n    self_ish = 1\n    obj.baz()\n"
    calls = extract_raw_calls(source, "module.py")

    assert len(calls) == 2
    assert calls[0].expression == "bar"
    assert calls[0].receiver_kind == "bare"
    assert calls[1].expression == "obj.baz"
    assert calls[1].receiver_kind == "attribute"


def test_call_inside_nested_function_has_nested_enclosing_symbol():
    source = "def outer():\n    def inner():\n        bar()\n"
    calls = extract_raw_calls(source, "module.py")

    assert len(calls) == 1
    assert calls[0].enclosing_symbol == "outer.<locals>.inner"
    assert calls[0].expression == "bar"
