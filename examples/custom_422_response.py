from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI(
    title="Custom 422 Response Example",
    description="A route can keep its own domain-specific 422 response; "
    "the validation error is still documented at the target status code.",
)


class Item(BaseModel):
    name: str
    price: float


class OutOfStockError(BaseModel):
    error_code: str
    item_name: str


@app.post("/items", responses={422: {"model": OutOfStockError, "description": "Item is out of stock"}})
async def create_item(item: Item) -> dict[str, Any]:
    return item.model_dump()


override_validation_error(app)
# The 422 response above is left untouched: it still documents OutOfStockError.
# The 400 response is added automatically, documenting the validation error schema,
# because this route still validates its request body regardless of what occupies 422.

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8006)
