from copy import deepcopy
from typing import Any

import fastapi.openapi.utils as fastapi_openapi_utils
import pytest

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.constants import REF_PREFIX
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error, patch_422_responses
from fastapi_validation_override import overrider as overrider_module


class Item(BaseModel):  # pragma: no cover
    name: str
    price: float


class ErrorModel(BaseModel):  # pragma: no cover
    message: str


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── runtime ───────────────────────────────────────────────────────────────────


async def test_valid_request_returns_200() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> None: ...

    override_validation_error(app)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test", "price": 9.99})

    assert response.status_code == status.HTTP_200_OK


async def test_invalid_body_returns_target_status_code() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})  # missing price

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_invalid_body_response_has_detail_key() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})

    assert "detail" in response.json()


async def test_handle_exceptions_false_runtime_keeps_422() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST, handle_exceptions=False)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})

    assert response.status_code == 422


async def test_handle_exceptions_false_preserves_pre_existing_custom_handler() -> None:
    app = FastAPI()

    @app.exception_handler(RequestValidationError)
    async def custom_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"message": "custom", "errors": exc.errors()})

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST, handle_exceptions=False)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["message"] == "custom"


# ── schema: rotte con body ────────────────────────────────────────────────────


async def test_schema_422_moved_to_target_code() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses


async def test_schema_handle_exceptions_false_still_patches_schema() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST, handle_exceptions=False)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses


async def test_schema_existing_response_at_target_code_merges_description() -> None:
    app = FastAPI()

    @app.post("/items", responses={400: {"description": "Custom Bad Request"}})
    async def create_item(item: Item) -> dict[str, Any]: ...

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
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    response_400 = schema["paths"]["/items"]["post"]["responses"]["400"]
    content_schema = response_400["content"]["application/json"]["schema"]
    assert "anyOf" in content_schema
    assert len(content_schema["anyOf"]) == 2


# ── schema: edge case - anyOf merge con append ───────────────────────────────


async def test_schema_existing_anyof_response_appends_validation_error() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    orig = app.openapi

    def my_openapi() -> dict[str, Any]:
        schema = orig()
        for path_item in schema.get("paths", {}).values():
            for method, operation in path_item.items():
                if method == "post" and isinstance(operation, dict):
                    operation.setdefault("responses", {})["400"] = {
                        "description": "Error",
                        "content": {
                            "application/json": {
                                "schema": {"anyOf": [{"type": "object", "properties": {"msg": {"type": "string"}}}]}
                            }
                        },
                    }
        app.openapi_schema = schema
        return schema

    app.openapi = my_openapi
    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    response_400 = schema["paths"]["/items"]["post"]["responses"]["400"]
    content_schema = response_400["content"]["application/json"]["schema"]
    assert "anyOf" in content_schema
    assert len(content_schema["anyOf"]) == 2


# ── schema: edge case - chiavi non-HTTP nel path item ────────────────────────


async def test_schema_path_item_non_http_key_is_skipped() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    orig = app.openapi

    def my_openapi() -> dict[str, Any]:
        schema = orig()
        for path_item in schema.get("paths", {}).values():
            path_item["parameters"] = []
        app.openapi_schema = schema
        return schema

    app.openapi = my_openapi
    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses


# ── schema: edge case - rotte senza body ─────────────────────────────────────


async def test_schema_get_route_without_params_not_modified() -> None:
    app = FastAPI()

    @app.get("/items")
    async def list_items() -> list[str]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["get"]["responses"]
    assert "422" not in responses
    assert "400" not in responses


async def test_schema_get_route_with_required_query_param_is_patched() -> None:
    app = FastAPI()

    @app.get("/items")
    async def get_item(item_id: int) -> dict[str, Any]: ...

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
    async def create_item(item: Item) -> dict[str, Any]: ...

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
        schema2 = (await client.get("/openapi.json")).json()

    assert custom_called
    assert schema["info"].get("x-custom") == "my-value"
    assert schema2["info"].get("x-custom") == "my-value"
    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses


# ── idempotenza ───────────────────────────────────────────────────────────────


async def test_double_call_idempotent_runtime() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)
    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_double_call_idempotent_schema() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)
    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses
    content = responses["400"].get("content", {}).get("application/json", {})
    assert "anyOf" not in content.get("schema", {})


async def test_double_call_with_different_arguments_keeps_first_call_behavior() -> None:
    """The docstring promises the second call is ignored 'even with different arguments' — pin that
    a differing status_code, handle_exceptions, and merge_target_response on the second call have no
    effect, at runtime and in the schema."""
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)
    override_validation_error(
        app, status_code=status.HTTP_409_CONFLICT, handle_exceptions=False, merge_target_response=False
    )

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})
        schema = (await client.get("/openapi.json")).json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert "409" not in responses
    assert "400" in responses


# ── guard status_code=422 ─────────────────────────────────────────────────────


async def test_guard_status_code_422_is_noop_runtime() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=422)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})

    assert response.status_code == 422


async def test_guard_status_code_422_is_noop_schema() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=422)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" in responses


def test_status_code_true_is_rejected() -> None:
    app = FastAPI()

    with pytest.raises(TypeError, match="bool"):
        override_validation_error(app, status_code=True)


def test_status_code_false_is_rejected() -> None:
    app = FastAPI()

    with pytest.raises(TypeError, match="bool"):
        override_validation_error(app, status_code=False)


@pytest.mark.parametrize("status_code", [400.0, "400", None])
def test_status_code_non_int_is_rejected(status_code: object) -> None:
    app = FastAPI()

    with pytest.raises(TypeError, match="must be an int"):
        override_validation_error(app, status_code=status_code)  # type: ignore[arg-type]


@pytest.mark.parametrize("status_code", [-1, 0, 99, 600, 999])
def test_status_code_outside_valid_range_is_rejected(status_code: int) -> None:
    app = FastAPI()

    with pytest.raises(ValueError, match="100-599"):
        override_validation_error(app, status_code=status_code)


@pytest.mark.parametrize("status_code", [200, 400, 409, 422, 500, 599])
def test_status_code_within_valid_range_is_accepted(status_code: int) -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status_code)


@pytest.mark.parametrize("status_code", [100, 101, 199, 204, 304])
def test_status_code_incompatible_with_response_body_is_rejected(status_code: int) -> None:
    app = FastAPI()

    with pytest.raises(ValueError, match="does not support a response body"):
        override_validation_error(app, status_code=status_code)


# ── runtime: query param ──────────────────────────────────────────────────────


async def test_invalid_query_param_returns_target_status_code() -> None:
    app = FastAPI()

    @app.get("/items")
    async def get_item(item_id: int) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        response = await client.get("/items", params={"item_id": "not-a-number"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_hidden_query_param_still_documents_and_returns_target_code() -> None:
    from typing import Annotated

    from fastapi import Query

    app = FastAPI()

    @app.get("/hidden")
    async def hidden(secret: Annotated[int, Query(include_in_schema=False)]) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()
        response = await client.get("/hidden", params={"secret": "not-a-number"})

    operation = schema["paths"]["/hidden"]["get"]
    assert "parameters" not in operation
    assert "422" not in operation["responses"]
    assert "400" in operation["responses"]
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_hidden_query_param_with_existing_422_leaves_target_code_undocumented() -> None:
    """
    Regression pin for the documented limitation: a hidden parameter's operation is only detected
    as needing validation via FastAPI's own 422 response or a visible requestBody/parameters. If the
    route already occupies 422 with something else, neither signal fires, so target_code stays
    undocumented — even though the route still returns it at runtime.
    """
    from typing import Annotated

    from fastapi import Query

    class Forbidden(BaseModel):  # pragma: no cover
        reason: str

    app = FastAPI()

    @app.get("/hidden", responses={422: {"model": Forbidden, "description": "Forbidden"}})
    async def hidden(secret: Annotated[int, Query(include_in_schema=False)]) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()
        response = await client.get("/hidden", params={"secret": "not-a-number"})

    operation = schema["paths"]["/hidden"]["get"]
    assert "parameters" not in operation
    assert list(operation["responses"].keys()) == ["200", "422"]
    assert "400" not in operation["responses"]
    # The runtime behavior is unaffected by the documentation gap: it still returns target_code.
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ── schema: path con metodi multipli ─────────────────────────────────────────


async def test_schema_multiple_methods_on_same_path_all_patched() -> None:
    app = FastAPI()

    @app.get("/items")
    async def list_items(category: int) -> dict[str, Any]: ...

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    get_responses = schema["paths"]["/items"]["get"]["responses"]
    post_responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in get_responses
    assert "400" in get_responses
    assert "422" not in post_responses
    assert "400" in post_responses


# ── patch_422_responses: unit tests ─────────────────────────────────────────

_REQUEST_BODY = {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Item"}}}}


def _operation_with_422(needs_validation: bool = True, **extra_responses: dict[str, Any]) -> dict[str, Any]:
    operation: dict[str, Any] = {
        "responses": {
            "422": {
                "description": "Validation Error",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/HTTPValidationError"},
                    },
                },
            },
            **extra_responses,
        }
    }
    if needs_validation:
        operation["requestBody"] = _REQUEST_BODY
    return operation


def test_patch_422_moves_to_target_code_when_no_existing_response() -> None:
    schema = {"paths": {"/items": {"post": _operation_with_422()}}}

    result = patch_422_responses(schema, "400")

    responses = result["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert responses["400"]["content"]["application/json"]["schema"]["$ref"].endswith("HTTPValidationError")


def test_patch_422_sets_schema_when_existing_response_has_no_schema() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(**{"400": {"description": "Custom Bad Request"}}),
            }
        }
    }

    result = patch_422_responses(schema, "400")

    response_400 = result["paths"]["/items"]["post"]["responses"]["400"]
    assert response_400["content"]["application/json"]["schema"]["$ref"].endswith("HTTPValidationError")
    assert response_400["description"] == "Custom Bad Request / Validation Error"


def test_patch_422_creates_anyof_when_existing_response_has_schema() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(
                    **{
                        "400": {
                            "description": "Out of stock",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/OutOfStockError"},
                                }
                            },
                        }
                    }
                ),
            }
        }
    }

    result = patch_422_responses(schema, "400")

    content_schema = result["paths"]["/items"]["post"]["responses"]["400"]["content"]["application/json"]["schema"]
    assert "anyOf" in content_schema
    assert len(content_schema["anyOf"]) == 2


def test_patch_422_appends_to_existing_anyof() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(
                    **{
                        "400": {
                            "description": "Error",
                            "content": {
                                "application/json": {
                                    "schema": {"anyOf": [{"$ref": "#/components/schemas/OutOfStockError"}]},
                                }
                            },
                        }
                    }
                ),
            }
        }
    }

    result = patch_422_responses(schema, "400")

    content_schema = result["paths"]["/items"]["post"]["responses"]["400"]["content"]["application/json"]["schema"]
    assert len(content_schema["anyOf"]) == 2


def test_patch_422_ignores_response_not_referencing_http_validation_error() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": {
                    "responses": {
                        "422": {
                            "description": "Custom",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SomethingElse"},
                                }
                            },
                        }
                    }
                }
            }
        }
    }

    result = patch_422_responses(schema, "400")

    responses = result["paths"]["/items"]["post"]["responses"]
    assert "422" in responses
    assert "400" not in responses


def test_patch_422_ignores_non_http_method_keys_in_path_item() -> None:
    schema = {
        "paths": {
            "/items": {
                "parameters": [{"name": "shared", "in": "query"}],
                "post": _operation_with_422(),
            }
        }
    }

    result = patch_422_responses(schema, "400")

    path_item = result["paths"]["/items"]
    assert path_item["parameters"] == [{"name": "shared", "in": "query"}]
    assert "400" in path_item["post"]["responses"]


def test_patch_422_noop_when_no_422_present() -> None:
    schema = {"paths": {"/items": {"get": {"responses": {"200": {"description": "OK"}}}}}}

    result = patch_422_responses(schema, "400")

    assert result["paths"]["/items"]["get"]["responses"] == {"200": {"description": "OK"}}


def test_patch_422_noop_when_no_paths() -> None:
    schema: dict[str, Any] = {"info": {"title": "Test"}}

    result = patch_422_responses(schema, "400")

    assert result == {"info": {"title": "Test"}}


def test_patch_422_returns_same_object_mutated_in_place() -> None:
    schema = {"paths": {"/items": {"post": _operation_with_422()}}}

    result = patch_422_responses(schema, "400")

    assert result is schema


# ── patch_422_responses: 422 e target_code sono indipendenti ────────────────


def test_patch_422_synthesizes_target_when_no_422_present_but_validation_needed() -> None:
    schema = {"paths": {"/items": {"post": {"responses": {}, "requestBody": _REQUEST_BODY}}}}

    result = patch_422_responses(schema, "400")

    responses = result["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert responses["400"]["content"]["application/json"]["schema"]["$ref"].endswith("HTTPValidationError")


def test_patch_422_synthesis_registers_components() -> None:
    schema = {"paths": {"/items": {"post": {"responses": {}, "requestBody": _REQUEST_BODY}}}}

    result = patch_422_responses(schema, "400")

    schemas = result["components"]["schemas"]
    assert "HTTPValidationError" in schemas
    assert "ValidationError" in schemas


def test_patch_422_no_synthesis_when_operation_does_not_need_validation() -> None:
    schema = {"paths": {"/items": {"get": {"responses": {}}}}}

    result = patch_422_responses(schema, "400")

    assert "components" not in result
    assert result["paths"]["/items"]["get"]["responses"] == {}


def test_patch_422_detects_validation_via_removed_422_even_without_params_in_schema() -> None:
    schema = {
        "paths": {
            "/items": {
                "get": {
                    "responses": {
                        "422": {
                            "description": "Validation Error",
                            "content": {
                                "application/json": {"schema": {"$ref": f"{REF_PREFIX}HTTPValidationError"}},
                            },
                        }
                    }
                }
            }
        }
    }

    result = patch_422_responses(schema, "400")

    responses = result["paths"]["/items"]["get"]["responses"]
    assert "422" not in responses
    assert "400" in responses


def test_patch_422_custom_422_left_untouched_and_target_still_synthesized() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": {
                    "responses": {
                        "422": {
                            "description": "Domain-specific error, unrelated to validation",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MyCustom422"}}},
                        }
                    },
                    "requestBody": _REQUEST_BODY,
                }
            }
        }
    }

    result = patch_422_responses(schema, "400")

    responses = result["paths"]["/items"]["post"]["responses"]
    assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith("MyCustom422")
    assert responses["400"]["content"]["application/json"]["schema"]["$ref"].endswith("HTTPValidationError")


def test_patch_422_model_named_like_http_validation_error_is_not_mistaken_for_it() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": {
                    "responses": {
                        "422": {
                            "description": "Domain-specific error, unrelated to validation",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/MyHTTPValidationError"}}
                            },
                        }
                    },
                    "requestBody": _REQUEST_BODY,
                }
            }
        }
    }

    result = patch_422_responses(schema, "400")

    responses = result["paths"]["/items"]["post"]["responses"]
    assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith("MyHTTPValidationError")
    assert responses["400"]["content"]["application/json"]["schema"]["$ref"] == f"{REF_PREFIX}HTTPValidationError"


def test_resolve_validation_ref_no_collision_uses_standard_names() -> None:
    schema: dict[str, Any] = {}

    ref, name = overrider_module._resolve_validation_ref(schema)

    assert name == "HTTPValidationError"
    assert ref == {"$ref": f"{REF_PREFIX}HTTPValidationError"}
    schemas = schema["components"]["schemas"]
    assert schemas["ValidationError"] == fastapi_openapi_utils.validation_error_definition
    assert schemas["HTTPValidationError"] == fastapi_openapi_utils.validation_error_response_definition


def test_resolve_validation_ref_reuses_existing_matching_components() -> None:
    schema = {
        "components": {
            "schemas": {
                "ValidationError": deepcopy(fastapi_openapi_utils.validation_error_definition),
                "HTTPValidationError": deepcopy(fastapi_openapi_utils.validation_error_response_definition),
            }
        }
    }

    ref, name = overrider_module._resolve_validation_ref(schema)

    assert name == "HTTPValidationError"
    assert ref == {"$ref": f"{REF_PREFIX}HTTPValidationError"}


def test_resolve_validation_ref_rewrites_nested_ref_on_validation_error_collision() -> None:
    schema = {"components": {"schemas": {"ValidationError": {"type": "string"}}}}

    ref, name = overrider_module._resolve_validation_ref(schema)

    # HTTPValidationError itself has no collision here, so it keeps the standard name...
    assert name == "HTTPValidationError"
    assert ref == {"$ref": f"{REF_PREFIX}HTTPValidationError"}
    schemas = schema["components"]["schemas"]
    assert schemas["ValidationError"] == {"type": "string"}
    assert schemas["FastAPIValidationOverride_ValidationError"] == fastapi_openapi_utils.validation_error_definition
    # ...but its nested $ref to ValidationError must point at the renamed component instead.
    nested_ref = schemas["HTTPValidationError"]["properties"]["detail"]["items"]["$ref"]
    assert nested_ref == f"{REF_PREFIX}FastAPIValidationOverride_ValidationError"


def test_replace_ref_rewrites_ref_nested_inside_a_list() -> None:
    value = {"anyOf": [{"$ref": f"{REF_PREFIX}ValidationError"}, {"type": "string"}]}

    overrider_module._replace_ref(value, f"{REF_PREFIX}ValidationError", f"{REF_PREFIX}Renamed")

    assert value == {"anyOf": [{"$ref": f"{REF_PREFIX}Renamed"}, {"type": "string"}]}


def test_replace_ref_ignores_non_matching_refs() -> None:
    value = {"$ref": f"{REF_PREFIX}SomethingElse"}

    overrider_module._replace_ref(value, f"{REF_PREFIX}ValidationError", f"{REF_PREFIX}Renamed")

    assert value == {"$ref": f"{REF_PREFIX}SomethingElse"}


def test_resolve_validation_ref_rewrites_nested_ref_regardless_of_field_name() -> None:
    """Reported bug: a custom definition using `dettagli` instead of `detail` raised KeyError
    because the old code assumed the standard FastAPI envelope shape."""
    original_http_validation_error = fastapi_openapi_utils.validation_error_response_definition
    fastapi_openapi_utils.validation_error_response_definition = {
        "title": "HTTPValidationError",
        "type": "object",
        "properties": {"dettagli": {"type": "array", "items": {"$ref": f"{REF_PREFIX}ValidationError"}}},
    }
    try:
        schema = {"components": {"schemas": {"ValidationError": {"type": "string"}}}}
        ref, name = overrider_module._resolve_validation_ref(schema)
    finally:
        fastapi_openapi_utils.validation_error_response_definition = original_http_validation_error

    assert name == "HTTPValidationError"
    nested_ref = schema["components"]["schemas"]["HTTPValidationError"]["properties"]["dettagli"]["items"]["$ref"]
    assert nested_ref == f"{REF_PREFIX}FastAPIValidationOverride_ValidationError"
    assert ref == {"$ref": f"{REF_PREFIX}HTTPValidationError"}


def test_resolve_validation_ref_renames_only_http_validation_error_on_its_own_collision() -> None:
    schema = {"components": {"schemas": {"HTTPValidationError": {"type": "string"}}}}

    ref, name = overrider_module._resolve_validation_ref(schema)

    assert name == "FastAPIValidationOverride_HTTPValidationError"
    assert ref == {"$ref": f"{REF_PREFIX}FastAPIValidationOverride_HTTPValidationError"}
    schemas = schema["components"]["schemas"]
    assert schemas["HTTPValidationError"] == {"type": "string"}
    assert schemas["ValidationError"] == fastapi_openapi_utils.validation_error_definition


def test_resolve_validation_ref_reads_definitions_dynamically() -> None:
    """A caller may reassign these globals (e.g. for i18n) before calling override_validation_error;
    a frozen import would keep using the original English definitions instead."""
    custom_validation_error = {"title": "ErroreValidazione", "type": "object", "properties": {"codice": {}}}
    custom_http_validation_error = {
        "title": "ErroreHTTPValidazione",
        "type": "object",
        "properties": {"dettagli": {"type": "array", "items": {"$ref": f"{REF_PREFIX}ValidationError"}}},
    }
    original_validation_error = fastapi_openapi_utils.validation_error_definition
    original_http_validation_error = fastapi_openapi_utils.validation_error_response_definition
    try:
        fastapi_openapi_utils.validation_error_definition = custom_validation_error
        fastapi_openapi_utils.validation_error_response_definition = custom_http_validation_error

        schema: dict[str, Any] = {}
        ref, name = overrider_module._resolve_validation_ref(schema)
    finally:
        fastapi_openapi_utils.validation_error_definition = original_validation_error
        fastapi_openapi_utils.validation_error_response_definition = original_http_validation_error

    assert name == "HTTPValidationError"
    assert ref == {"$ref": f"{REF_PREFIX}HTTPValidationError"}
    schemas = schema["components"]["schemas"]
    assert schemas["ValidationError"] == custom_validation_error
    assert schemas["HTTPValidationError"] == custom_http_validation_error


async def test_override_validation_error_honors_definitions_monkeypatched_before_call() -> None:
    custom_validation_error = {"title": "ErroreValidazione", "type": "object", "properties": {"codice": {}}}
    custom_http_validation_error = {
        "title": "ErroreHTTPValidazione",
        "type": "object",
        "properties": {"dettagli": {"type": "array", "items": {"$ref": f"{REF_PREFIX}ValidationError"}}},
    }
    original_validation_error = fastapi_openapi_utils.validation_error_definition
    original_http_validation_error = fastapi_openapi_utils.validation_error_response_definition
    fastapi_openapi_utils.validation_error_definition = custom_validation_error
    fastapi_openapi_utils.validation_error_response_definition = custom_http_validation_error
    try:
        app = FastAPI()

        @app.post("/items")
        async def create_item(item: Item) -> dict[str, Any]: ...

        override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

        async with _client(app) as client:
            schema = (await client.get("/openapi.json")).json()
    finally:
        fastapi_openapi_utils.validation_error_definition = original_validation_error
        fastapi_openapi_utils.validation_error_response_definition = original_http_validation_error

    schemas = schema["components"]["schemas"]
    assert schemas["ValidationError"] == custom_validation_error
    assert schemas["HTTPValidationError"] == custom_http_validation_error


# ── patch_422_responses: merge_target_response=False ─────────────────────────


def test_patch_422_merge_target_response_false_leaves_existing_target_untouched() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(
                    **{
                        "400": {
                            "description": "Out of stock",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/OutOfStockError"},
                                }
                            },
                        }
                    }
                ),
            }
        }
    }

    result = patch_422_responses(schema, "400", merge_target_response=False)

    response_400 = result["paths"]["/items"]["post"]["responses"]["400"]
    assert response_400["content"]["application/json"]["schema"]["$ref"].endswith("OutOfStockError")
    assert response_400["description"] == "Out of stock"
    # no $ref to ValidationError/HTTPValidationError was ever written, so they must not be inserted
    assert "components" not in result


def test_patch_422_merge_target_response_false_still_removes_native_422() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(**{"400": {"description": "Out of stock"}}),
            }
        }
    }

    result = patch_422_responses(schema, "400", merge_target_response=False)

    assert "422" not in result["paths"]["/items"]["post"]["responses"]


def test_patch_422_merge_target_response_false_still_synthesizes_when_target_absent() -> None:
    schema = {"paths": {"/items": {"post": _operation_with_422()}}}

    result = patch_422_responses(schema, "400", merge_target_response=False)

    responses = result["paths"]["/items"]["post"]["responses"]
    assert responses["400"]["content"]["application/json"]["schema"]["$ref"].endswith("HTTPValidationError")


def test_patch_422_target_as_local_response_ref_merges_on_inlined_copy() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(**{"400": {"$ref": "#/components/responses/Foo"}}),
            }
        },
        "components": {
            "responses": {
                "Foo": {
                    "description": "Out of stock",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/OutOfStockError"}},
                    },
                }
            }
        },
    }

    result = patch_422_responses(schema, "400")

    response_400 = result["paths"]["/items"]["post"]["responses"]["400"]
    assert "$ref" not in response_400
    content_schema = response_400["content"]["application/json"]["schema"]
    assert "anyOf" in content_schema
    assert len(content_schema["anyOf"]) == 2
    # the shared component itself must stay untouched by the merge
    shared_foo = result["components"]["responses"]["Foo"]
    assert shared_foo["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/OutOfStockError"}


def test_patch_422_target_as_external_response_ref_is_left_untouched() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(**{"400": {"$ref": "external.yaml#/components/responses/Foo"}}),
            }
        }
    }

    result = patch_422_responses(schema, "400")

    response_400 = result["paths"]["/items"]["post"]["responses"]["400"]
    assert response_400 == {"$ref": "external.yaml#/components/responses/Foo"}
    # no $ref to ValidationError/HTTPValidationError was ever written, so they must not be inserted
    assert "components" not in result


def test_patch_422_target_as_unresolvable_local_response_ref_is_left_untouched() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(**{"400": {"$ref": "#/components/responses/Missing"}}),
            }
        }
    }

    result = patch_422_responses(schema, "400")

    response_400 = result["paths"]["/items"]["post"]["responses"]["400"]
    assert response_400 == {"$ref": "#/components/responses/Missing"}
    # no $ref to ValidationError/HTTPValidationError was ever written, so they must not be inserted
    assert "components" not in result


def test_patch_422_target_as_chained_local_response_ref_merges_on_inlined_copy() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(**{"400": {"$ref": "#/components/responses/Foo"}}),
            }
        },
        "components": {
            "responses": {
                "Foo": {"$ref": "#/components/responses/Bar"},
                "Bar": {
                    "description": "Out of stock",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/OutOfStockError"}},
                    },
                },
            }
        },
    }

    result = patch_422_responses(schema, "400")

    response_400 = result["paths"]["/items"]["post"]["responses"]["400"]
    assert "$ref" not in response_400
    content_schema = response_400["content"]["application/json"]["schema"]
    assert "anyOf" in content_schema
    assert len(content_schema["anyOf"]) == 2
    # the shared components must stay untouched by the merge
    assert result["components"]["responses"]["Foo"] == {"$ref": "#/components/responses/Bar"}
    shared_bar = result["components"]["responses"]["Bar"]
    assert shared_bar["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/OutOfStockError"}


def test_patch_422_target_as_cyclic_local_response_ref_is_left_untouched() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(**{"400": {"$ref": "#/components/responses/Foo"}}),
            }
        },
        "components": {
            "responses": {
                "Foo": {"$ref": "#/components/responses/Bar"},
                "Bar": {"$ref": "#/components/responses/Foo"},
            }
        },
    }

    result = patch_422_responses(schema, "400")

    response_400 = result["paths"]["/items"]["post"]["responses"]["400"]
    assert response_400 == {"$ref": "#/components/responses/Foo"}


def test_patch_422_target_as_local_response_ref_chained_to_external_is_left_untouched() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(**{"400": {"$ref": "#/components/responses/Foo"}}),
            }
        },
        "components": {
            "responses": {
                "Foo": {"$ref": "external.yaml#/components/responses/Bar"},
            }
        },
    }

    result = patch_422_responses(schema, "400")

    response_400 = result["paths"]["/items"]["post"]["responses"]["400"]
    assert response_400 == {"$ref": "#/components/responses/Foo"}


# ── patch_422_responses: idempotenza su schema già patchato ─────────────────


def test_patch_422_running_twice_on_already_patched_schema_does_not_duplicate() -> None:
    schema = {"paths": {"/items": {"post": _operation_with_422()}}}

    patch_422_responses(schema, "400")
    patch_422_responses(schema, "400")

    response_400 = schema["paths"]["/items"]["post"]["responses"]["400"]
    assert "anyOf" not in response_400["content"]["application/json"]["schema"]
    assert response_400["description"].count("Validation Error") == 1


def test_patch_422_running_twice_on_already_merged_anyof_does_not_duplicate() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": _operation_with_422(
                    **{
                        "400": {
                            "description": "Out of stock",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/OutOfStockError"},
                                }
                            },
                        }
                    }
                ),
            }
        }
    }

    patch_422_responses(schema, "400")
    patch_422_responses(schema, "400")

    content_schema = schema["paths"]["/items"]["post"]["responses"]["400"]["content"]["application/json"]["schema"]
    assert len(content_schema["anyOf"]) == 2


# ── override_validation_error: 422 custom + target sintetizzato (end-to-end) ─


async def test_custom_422_left_untouched_and_target_synthesized_end_to_end() -> None:
    app = FastAPI()

    class MyCustom422(BaseModel):  # pragma: no cover
        error_code: str

    @app.post("/items", responses={422: {"model": MyCustom422, "description": "My custom 422"}})
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith("MyCustom422")
    assert responses["400"]["content"]["application/json"]["schema"]["$ref"].endswith("HTTPValidationError")
    assert "HTTPValidationError" in schema["components"]["schemas"]
    assert "ValidationError" in schema["components"]["schemas"]


async def test_model_named_like_http_validation_error_is_not_mistaken_for_it_end_to_end() -> None:
    app = FastAPI()

    class MyHTTPValidationError(BaseModel):  # pragma: no cover
        error_code: str

    @app.post("/items", responses={422: {"model": MyHTTPValidationError, "description": "My own 422"}})
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith("MyHTTPValidationError")
    assert responses["400"]["content"]["application/json"]["schema"]["$ref"] == f"{REF_PREFIX}HTTPValidationError"


async def test_unrelated_model_literally_named_http_validation_error_survives_end_to_end() -> None:
    """
    Regression scenario: a model with the exact same name as FastAPI's own component is used
    elsewhere in the app, on a route that never triggers validation itself. Since no other route
    triggers FastAPI's own native HTTPValidationError either (this route occupies its own 422),
    the unrelated model keeps that component name until we need it — and must not be clobbered.
    """
    app = FastAPI()

    class HTTPValidationError(BaseModel):  # pragma: no cover
        my_own_field: str

    class MyDomainError(BaseModel):  # pragma: no cover
        error_code: str

    @app.get("/unrelated", response_model=HTTPValidationError)
    async def unrelated() -> HTTPValidationError: ...

    @app.post("/items", responses={422: {"model": MyDomainError, "description": "My own 422"}})
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    schemas = schema["components"]["schemas"]
    assert schemas["HTTPValidationError"]["properties"] == {"my_own_field": {"type": "string", "title": "My Own Field"}}
    assert "FastAPIValidationOverride_HTTPValidationError" in schemas

    response_400 = schema["paths"]["/items"]["post"]["responses"]["400"]
    assert response_400["content"]["application/json"]["schema"]["$ref"] == (
        f"{REF_PREFIX}FastAPIValidationOverride_HTTPValidationError"
    )


async def test_custom_422_left_untouched_runtime_still_returns_target_code() -> None:
    app = FastAPI()

    class MyCustom422(BaseModel):  # pragma: no cover
        error_code: str

    @app.post("/items", responses={422: {"model": MyCustom422, "description": "My custom 422"}})
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        response = await client.post("/items", json={"name": "test"})  # missing price -> real validation error

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "detail" in response.json()


# ── override_validation_error: merge_target_response=False (end-to-end) ─────


async def test_merge_target_response_false_leaves_declared_response_untouched() -> None:
    app = FastAPI()

    @app.post("/items", responses={400: {"description": "Custom Bad Request"}})
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST, merge_target_response=False)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    response_400 = schema["paths"]["/items"]["post"]["responses"]["400"]
    assert response_400["description"] == "Custom Bad Request"
    assert "content" not in response_400


async def test_merge_target_response_false_still_synthesizes_when_target_undeclared() -> None:
    app = FastAPI()

    @app.post("/items")
    async def create_item(item: Item) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST, merge_target_response=False)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "422" not in responses
    assert responses["400"]["content"]["application/json"]["schema"]["$ref"].endswith("HTTPValidationError")


def test_patch_422_webhooks_are_patched() -> None:
    schema = {
        "paths": {},
        "webhooks": {
            "new-item": {"post": _operation_with_422()},
        },
    }

    result = patch_422_responses(schema, "400")

    responses = result["webhooks"]["new-item"]["post"]["responses"]
    assert "422" not in responses
    assert "400" in responses


def test_patch_422_callbacks_are_patched() -> None:
    main_operation = _operation_with_422()
    main_operation["callbacks"] = {
        "myCallback": {
            "{$callback_url}": {"post": _operation_with_422()},
        }
    }
    schema = {"paths": {"/items": {"post": main_operation}}}

    result = patch_422_responses(schema, "400")

    callback_responses = result["paths"]["/items"]["post"]["callbacks"]["myCallback"]["{$callback_url}"]["post"][
        "responses"
    ]
    assert "422" not in callback_responses
    assert "400" in callback_responses
    # the main path is patched independently of the callback, not as a side effect of patching it
    assert "400" in result["paths"]["/items"]["post"]["responses"]


def test_patch_422_ref_callback_is_resolved_and_patched() -> None:
    main_operation = _operation_with_422()
    main_operation["callbacks"] = {"myCallback": {"$ref": "#/components/callbacks/EventCallback"}}
    schema = {
        "paths": {"/items": {"post": main_operation}},
        "components": {
            "callbacks": {
                "EventCallback": {
                    "{$callback_url}": {"post": _operation_with_422()},
                }
            }
        },
    }

    result = patch_422_responses(schema, "400")

    callback_responses = result["paths"]["/items"]["post"]["callbacks"]["myCallback"]["$ref"]
    # the $ref itself is left untouched; the referenced component is patched in place
    assert callback_responses == "#/components/callbacks/EventCallback"
    patched_component = result["components"]["callbacks"]["EventCallback"]["{$callback_url}"]["post"]["responses"]
    assert "422" not in patched_component
    assert "400" in patched_component


def test_patch_422_chained_ref_callback_is_resolved_and_patched() -> None:
    main_operation = _operation_with_422()
    main_operation["callbacks"] = {"myCallback": {"$ref": "#/components/callbacks/Foo"}}
    schema = {
        "paths": {"/items": {"post": main_operation}},
        "components": {
            "callbacks": {
                "Foo": {"$ref": "#/components/callbacks/Bar"},
                "Bar": {
                    "{$callback_url}": {"post": _operation_with_422()},
                },
            }
        },
    }

    result = patch_422_responses(schema, "400")

    patched_component = result["components"]["callbacks"]["Bar"]["{$callback_url}"]["post"]["responses"]
    assert "422" not in patched_component
    assert "400" in patched_component


def test_patch_422_cyclic_ref_callback_is_skipped() -> None:
    main_operation = _operation_with_422()
    main_operation["callbacks"] = {"myCallback": {"$ref": "#/components/callbacks/Foo"}}
    schema = {
        "paths": {"/items": {"post": main_operation}},
        "components": {
            "callbacks": {
                "Foo": {"$ref": "#/components/callbacks/Bar"},
                "Bar": {"$ref": "#/components/callbacks/Foo"},
            }
        },
    }

    result = patch_422_responses(schema, "400")

    # the cycle is skipped entirely, but the main path is still patched
    assert "400" in result["paths"]["/items"]["post"]["responses"]


def test_patch_422_structurally_self_referential_callback_does_not_recurse_forever() -> None:
    main_operation = _operation_with_422()
    main_operation["callbacks"] = {"onEvent": {"$ref": "#/components/callbacks/EventCallback"}}
    nested_operation = _operation_with_422()
    # the callback's own nested operation refers back to the same component it lives inside of
    nested_operation["callbacks"] = {"onAck": {"$ref": "#/components/callbacks/EventCallback"}}
    schema = {
        "paths": {"/items": {"post": main_operation}},
        "components": {
            "callbacks": {
                "EventCallback": {
                    "{$callback_url}": {"post": nested_operation},
                }
            }
        },
    }

    result = patch_422_responses(schema, "400")

    assert "400" in result["paths"]["/items"]["post"]["responses"]
    patched_nested = result["components"]["callbacks"]["EventCallback"]["{$callback_url}"]["post"]["responses"]
    assert "400" in patched_nested


def test_patch_422_same_callback_reused_by_two_unrelated_operations_is_patched_for_both() -> None:
    operation_a = _operation_with_422()
    operation_a["callbacks"] = {"e": {"$ref": "#/components/callbacks/Shared"}}
    operation_b = _operation_with_422()
    operation_b["callbacks"] = {"e": {"$ref": "#/components/callbacks/Shared"}}
    schema = {
        "paths": {
            "/subscribe-a": {"post": operation_a},
            "/subscribe-b": {"post": operation_b},
        },
        "components": {
            "callbacks": {
                "Shared": {"{$callback_url}": {"post": _operation_with_422()}},
            }
        },
    }

    result = patch_422_responses(schema, "400")

    assert "400" in result["paths"]["/subscribe-a"]["post"]["responses"]
    assert "400" in result["paths"]["/subscribe-b"]["post"]["responses"]
    shared_responses = result["components"]["callbacks"]["Shared"]["{$callback_url}"]["post"]["responses"]
    assert "400" in shared_responses


def test_patch_422_external_ref_callback_is_skipped() -> None:
    main_operation = _operation_with_422()
    main_operation["callbacks"] = {"myCallback": {"$ref": "external.yaml#/components/callbacks/EventCallback"}}
    schema = {"paths": {"/items": {"post": main_operation}}}

    result = patch_422_responses(schema, "400")

    assert "400" in result["paths"]["/items"]["post"]["responses"]


def test_patch_422_skips_non_dict_entries_in_webhooks_and_callbacks() -> None:
    schema = {
        "paths": {
            "/items": {
                "post": {
                    "responses": {},
                    "requestBody": _REQUEST_BODY,
                    "callbacks": {
                        "broken": "not-a-dict",
                        "ok": {"{$callback_url}": {"post": _operation_with_422()}},
                    },
                }
            }
        },
        "webhooks": {
            "broken": "not-a-dict",
            "new-item": {"post": _operation_with_422()},
        },
    }

    result = patch_422_responses(schema, "400")

    assert "400" in result["webhooks"]["new-item"]["post"]["responses"]
    assert "400" in result["paths"]["/items"]["post"]["callbacks"]["ok"]["{$callback_url}"]["post"]["responses"]


async def test_webhooks_and_callbacks_patched_end_to_end() -> None:
    from fastapi import APIRouter

    callback_router: APIRouter = APIRouter()

    @callback_router.post("{$callback_url}/done")
    async def done(item: Item) -> None: ...

    app = FastAPI()

    @app.post("/items", callbacks=callback_router.routes)
    async def create_item(item: Item) -> dict[str, Any]: ...

    @app.webhooks.post("new-item")
    async def new_item(item: Item) -> None:
        """Webhook notification."""

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        schema = (await client.get("/openapi.json")).json()

    webhook_responses = schema["webhooks"]["new-item"]["post"]["responses"]
    assert "422" not in webhook_responses
    assert "400" in webhook_responses

    callback_paths = schema["paths"]["/items"]["post"]["callbacks"]["done"]
    callback_operation = next(iter(callback_paths.values()))["post"]
    assert "422" not in callback_operation["responses"]
    assert "400" in callback_operation["responses"]


def test_target_schema_not_shared_across_routes() -> None:
    app = FastAPI()

    @app.post("/a")
    async def a(item: Item) -> dict[str, Any]: ...

    @app.post("/b")
    async def b(item: Item) -> dict[str, Any]: ...

    override_validation_error(app)
    schema = app.openapi()

    schema_a = schema["paths"]["/a"]["post"]["responses"]["400"]["content"]["application/json"]["schema"]
    schema_b = schema["paths"]["/b"]["post"]["responses"]["400"]["content"]["application/json"]["schema"]
    assert schema_a is not schema_b


def test_mutating_generated_schema_does_not_alter_module_constant() -> None:
    schema = {"paths": {"/items": {"post": _operation_with_422()}}}
    result = patch_422_responses(schema, "400")

    result["paths"]["/items"]["post"]["responses"]["400"]["content"]["application/json"]["schema"]["x-note"] = "touched"

    assert "x-note" not in overrider_module._VALIDATION_ERROR_REF


def test_independent_apps_do_not_share_component_schemas() -> None:
    def build_app() -> FastAPI:
        app = FastAPI()

        @app.post("/items")
        async def create_item(item: Item) -> dict[str, Any]: ...

        override_validation_error(app)
        return app

    app1 = build_app()
    app2 = build_app()

    schema1 = app1.openapi()
    schema1["components"]["schemas"]["ValidationError"]["x-note"] = "touched by app1"

    schema2 = app2.openapi()

    assert "x-note" not in schema2["components"]["schemas"]["ValidationError"]
    assert "x-note" not in fastapi_openapi_utils.validation_error_definition
