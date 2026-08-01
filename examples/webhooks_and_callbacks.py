from typing import Any

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI(
    title="Webhooks and Callbacks Example",
    description="The override covers webhooks and callbacks the same way it covers regular paths.",
)


class Item(BaseModel):
    name: str
    price: float


class ItemUpdate(BaseModel):
    status: str


@app.webhooks.post("item-created")
async def item_created_webhook(item: Item) -> None:
    """Sent to subscribers when an item is created."""


callback_router = APIRouter()


@callback_router.post("{$callback_url}/updated")
async def item_updated_callback(update: ItemUpdate) -> None: ...


@app.post("/items", callbacks=callback_router.routes)
async def create_item(item: Item) -> dict[str, Any]:
    return item.model_dump()


override_validation_error(app)
# The webhook and the callback each get their own 400 response documented, independently of
# /items and of each other.

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8008)
