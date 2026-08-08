"""
The override applies to every route regardless of how it's organized across APIRouters.

Run:

    uvicorn examples.with_apirouter:app --reload
"""

from typing import Any

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI(
    title="APIRouter Example",
    description="Override applies to all routes regardless of how they are organized.",
)

items_router = APIRouter(prefix="/items", tags=["items"])
users_router = APIRouter(prefix="/users", tags=["users"])


class Item(BaseModel):
    name: str
    price: float


class User(BaseModel):
    username: str
    age: int


@items_router.post("")
async def create_item(item: Item) -> dict[str, Any]:
    return item.model_dump()


@users_router.post("")
async def create_user(user: User) -> dict[str, Any]:
    return user.model_dump()


app.include_router(items_router)
app.include_router(users_router)

override_validation_error(app)
