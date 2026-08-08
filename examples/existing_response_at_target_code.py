"""
Merge the validation error schema into a response already declared at the target status code.

Run:

    uvicorn examples.existing_response_at_target_code:app --reload
"""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI(
    title="Existing Response at Target Code Example",
    description="When a route already declares a response at the target status code, "
    "the validation error schema is merged into it using anyOf.",
)


class Item(BaseModel):
    name: str
    price: float


class OutOfStockError(BaseModel):
    message: str
    item_name: str


@app.post("/items", responses={400: {"model": OutOfStockError, "description": "Out of stock"}})
async def create_item(item: Item) -> dict[str, Any]:
    return item.model_dump()


override_validation_error(app)
