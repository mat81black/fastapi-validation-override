from typing import Any

from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error


class Item(BaseModel):
    name: str
    price: float


class ErrorModel(BaseModel):
    message: str


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── runtime ───────────────────────────────────────────────────────────────────


async def test_valid_request_returns_200() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test", "price": 9.99})

    assert response.status_code == status.HTTP_200_OK


async def test_invalid_body_returns_target_status_code() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})  # missing price

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_invalid_body_response_has_detail_key() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})

    assert "detail" in response.json()


async def test_handle_exceptions_false_runtime_keeps_422() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST, handle_exceptions=False)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})

    assert response.status_code == 422


# ── schema: rotte con body ────────────────────────────────────────────────────


async def test_schema_422_moved_to_target_code() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses


async def test_schema_handle_exceptions_false_still_patches_schema() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST, handle_exceptions=False)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses


async def test_schema_existing_response_at_target_code_merges_description() -> None:
    app = FastAPI()

    @app.post("/items", responses={400: {"description": "Custom Bad Request"}})
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses
    assert "Validation Error" in responses["400"]["description"]


async def test_schema_existing_response_with_model_creates_anyof() -> None:
    app = FastAPI()

    @app.post("/items", responses={400: {"model": ErrorModel}})
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    response_400 = schema["paths"]["/items"]["post"]["responses"]["400"]
    content_schema = response_400["content"]["application/json"]["schema"]
    assert "anyOf" in content_schema
    assert len(content_schema["anyOf"]) == 2


# ── schema: edge case - rotte senza body ─────────────────────────────────────


async def test_schema_get_route_without_params_not_modified() -> None:
    app = FastAPI()

    @app.get("/items")
    async def list_items() -> list[str]:
        return []

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["get"]["responses"]
    assert "422" not in responses
    assert "400" not in responses


async def test_schema_get_route_with_required_query_param_is_patched() -> None:
    app = FastAPI()

    @app.get("/items")
    async def get_item(item_id: int) -> dict[str, Any]:
        return {"id": item_id}

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["get"]["responses"]
    assert "422" not in responses
    assert "400" in responses


# ── schema: custom app.openapi ────────────────────────────────────────────────


async def test_custom_openapi_is_called_and_result_is_patched() -> None:
    app = FastAPI()
    custom_called = False

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    original_openapi = app.openapi

    def my_custom_openapi() -> dict[str, Any]:
        nonlocal custom_called
        custom_called = True
        if app.openapi_schema:
            return app.openapi_schema
        schema = original_openapi()
        schema["info"]["x-custom"] = "my-value"
        app.openapi_schema = schema
        return schema

    app.openapi = my_custom_openapi
    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    assert custom_called
    assert schema["info"].get("x-custom") == "my-value"
    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses


# ── idempotenza ───────────────────────────────────────────────────────────────


async def test_double_call_idempotent_runtime() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)
    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_double_call_idempotent_schema() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)
    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses
    content = responses["400"].get("content", {}).get("application/json", {})
    assert "anyOf" not in content.get("schema", {})


# ── guard status_code=422 ─────────────────────────────────────────────────────


async def test_guard_status_code_422_is_noop_runtime() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=422)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})

    assert response.status_code == 422


async def test_guard_status_code_422_is_noop_schema() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]:
        return item.model_dump()

    override_validation_error(app, status_code=422)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" in responses
