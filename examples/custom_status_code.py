"""
Use a custom status code (409) instead of the default 400.

Run:

    uvicorn examples.custom_status_code:app --reload
"""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI(
    title="Custom Status Code Example",
    description="Use a custom status code (409) instead of the default 400.",
)


class Item(BaseModel):
    name: str
    price: float


@app.post("/items")
async def create_item(item: Item) -> dict[str, Any]:
    return item.model_dump()


override_validation_error(app, status_code=409)
