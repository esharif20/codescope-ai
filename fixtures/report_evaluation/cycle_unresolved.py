"""Inert static-analysis fixture: never import or execute this module."""

raise RuntimeError("REPORT_EVALUATION_SOURCE_MUST_NOT_EXECUTE")

from fastapi import FastAPI

app = FastAPI()


def first():
    return second()


def second():
    return first()


@app.get("/cycle")
def endpoint():
    return first()


def unrelated():
    return 1


def dynamic(callback):
    return callback()
