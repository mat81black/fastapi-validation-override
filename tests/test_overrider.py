from typing import Any

from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error, patch_422_responses


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


# ── runtime: query param ──────────────────────────────────────────────────────


async def test_invalid_query_param_returns_target_status_code() -> None:
    app = FastAPI()

    @app.get("/items")
    async def get_item(item_id: int) -> dict[str, Any]: ...

    override_validation_error(app, status_code=status.HTTP_400_BAD_REQUEST)

    async with _client(app) as client:
        response = await client.get("/items", params={"item_id": "not-a-number"})

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
