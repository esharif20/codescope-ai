"""Wires routes into a FastAPI app. External import only (D-05) -- never executed."""

from fastapi import FastAPI

from .routes.users import router

app = FastAPI()
app.include_router(router)
