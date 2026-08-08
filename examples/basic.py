"""
Minimal setup: override the default 422 validation error with 400.

Run:

    uvicorn examples.basic:app --reload
"""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI(
    title="Basic Example",
    description="Replace the default 422 validation error with 400.",
)


class Item(BaseModel):
    name: str
    price: float


@app.post("/items")
async def create_item(item: Item) -> dict[str, Any]:
    return item.model_dump()


override_validation_error(app)
