from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI(
    title="Custom OpenAPI Example",
    description="The developer's custom app.openapi function is preserved and patched on top.",
)


class Item(BaseModel):
    name: str
    price: float


@app.post("/items")
async def create_item(item: Item) -> dict[str, Any]:
    return item.model_dump()


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title="My API", version="1.0.0", routes=app.routes)
    schema["info"]["x-logo"] = {"url": "https://example.com/logo.png"}
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]  # ty: ignore[invalid-assignment]

override_validation_error(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8003)
