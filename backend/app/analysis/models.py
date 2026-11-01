"""Pydantic data contract for the Python symbol extractor.

These models are the stable, public shape returned by
``app.analysis.python_symbols.extract_symbols`` / ``extract_symbols_from_file``.
Nothing in this module depends on FastAPI or any web framework.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class SymbolKind(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    NESTED_FUNCTION = "nested_function"


class ParseStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    SYNTAX_ERRORS = "syntax_errors"
    DECODE_ERROR = "decode_error"


class SyntaxIssueKind(str, Enum):
    ERROR = "error"
    MISSING = "missing"


class Symbol(BaseModel):
    name: str
    qualified_name: str
    kind: SymbolKind
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int
    parent_qualified_name: str | None = None
    decorator_start_line: int | None = None
    is_async: bool = False

    @model_validator(mode="after")
    def _check_end_line_after_start_line(self) -> Symbol:
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")
        return self


class SyntaxIssue(BaseModel):
    kind: SyntaxIssueKind
    message: str
    start_line: int
    end_line: int


class ParseResult(BaseModel):
    file_path: str
    status: ParseStatus
    symbols: list[Symbol]
    errors: list[SyntaxIssue]
