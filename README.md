# FastAPI Validation Override

[![Build Status](https://github.com/mat81black/fastapi-validation-override/workflows/Test/badge.svg)](https://github.com/mat81black/fastapi-validation-override/actions)
[![codecov](https://codecov.io/github/mat81black/fastapi-validation-override/graph/badge.svg?token=SL4JPWAB0O)](https://codecov.io/github/mat81black/fastapi-validation-override)
[![pypi package](https://img.shields.io/pypi/v/fastapi-validation-override?color=%2334D058&label=pypi%20package)](https://pypi.org/project/fastapi-validation-override/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/fastapi-validation-override.svg?color=%2334D058)](https://pypi.org/project/fastapi-validation-override/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/mat81black/fastapi-validation-override/blob/main/LICENSE)

FastAPI returns 422 Unprocessable Entity for every request validation failure. Many APIs, client teams, and HTTP standards treat 400 Bad Request as the correct status code for malformed input. Fixing this in FastAPI requires wiring a custom exception handler and updating the OpenAPI schema separately. `override_validation_error` does both in a single call.

## Features

- **Single call**: patches runtime exception handling and the OpenAPI schema at once
- **Any status code**: use 400, 409, or any valid code instead of 422
- **Full schema coverage**: patches paths, webhooks, and callbacks alike, so the schema stays internally consistent
- **anyOf merge**: when a route already declares a response at the target code, the validation error schema is merged rather than overwritten
- **Independent of a custom 422**: if a route keeps its own, non-validation 422 response, it's left untouched and the validation schema is still documented at the target code
- **Custom openapi preserved**: wraps any `app.openapi` function already installed and applies the patch on top of its output
- **Bring your own handler**: `handle_exceptions=False` skips the built-in handler while still patching the schema
- **Customizable validation schema**: honors `fastapi.openapi.utils.validation_error_definition`/`validation_error_response_definition` if you reassign them before patching (e.g. to match your own error envelope), regardless of field names or structure
- **Idempotent**: safe to call multiple times on the same app instance. The first call configures the app; subsequent calls are ignored, even with different arguments — dynamic reconfiguration isn't supported
- **No-op guard**: `status_code=422` leaves FastAPI behavior unchanged

## Requirements

- Python 3.10+
- FastAPI 0.120.0+

## Installation

```bash
pip install fastapi-validation-override
# or
uv add fastapi-validation-override
```

## Quick start

```python
from fastapi import FastAPI
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float


@app.post("/items")
async def create_item(item: Item) -> dict[str, object]:
    return item.model_dump()


override_validation_error(app)
# POST /items with invalid fields -> 400 Bad Request {"detail": [...]}
```

The `{"detail": [...]}` body is identical to FastAPI's default 422 response. Only the status code changes.

To use a different code, pass `status_code`:

```python
override_validation_error(app, status_code=409)
```

## Reference

### `override_validation_error`

```python
override_validation_error(app, status_code=400, handle_exceptions=True, merge_target_response=True)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `app` | `FastAPI` | required | The FastAPI application instance to patch |
| `status_code` | `int` | `400` | HTTP status code to use instead of 422. Must be a valid HTTP status code (`100`-`599`) that supports a response body, since this library always sends one — so `1xx`, `204`, and `304` are rejected. Calling with `422` is a no-op. Raises `TypeError` if not an `int` (a `bool` is also rejected), `ValueError` for anything else invalid |
| `handle_exceptions` | `bool` | `True` | When `True`, registers an exception handler that returns the custom status code at runtime. Set to `False` to patch only the OpenAPI schema and handle the exception yourself |
| `merge_target_response` | `bool` | `True` | When `True`, a response you already declared at `status_code` is merged with the validation error schema using `anyOf`. When `False`, it's left untouched |

### `patch_422_responses`

```python
patch_422_responses(schema, target_code, merge_target_response=True)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `schema` | `dict[str, Any]` | required | An OpenAPI schema dict, such as one returned by `app.openapi()` |
| `target_code` | `str` | required | The status code to document the validation error at, e.g. `"400"` |
| `merge_target_response` | `bool` | `True` | Same as the `override_validation_error` parameter of the same name |

The schema-patching logic that `override_validation_error` uses internally, exposed as a standalone function for advanced use cases, such as patching a schema inside your own custom `app.openapi` function without going through `override_validation_error`. Mutates `schema` in place and also returns it.

```python
from fastapi_validation_override import patch_422_responses

schema = app.openapi()
patch_422_responses(schema, "400")
```

What happens to 422 and what happens to `target_code` are decided independently: a FastAPI-generated 422 validation response is removed, any other response already declared at 422 is left untouched, and routes that need validation always get it documented at `target_code`, synthesized from FastAPI's own schema components if nothing is there yet. See [Independent 422 handling](#independent-422-handling) below.

### Custom exception handler

Set `handle_exceptions=False` when you need a custom response body or additional logic. The OpenAPI schema is still patched.

```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from fastapi_validation_override import override_validation_error

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"message": "Validation failed", "errors": exc.errors()},
    )


@app.post("/items")
async def create_item(item: Item) -> dict[str, object]:
    return item.model_dump()


override_validation_error(app, status_code=400, handle_exceptions=False)
```

### Customizing the validation error schema

FastAPI itself defines the `ValidationError`/`HTTPValidationError` component schemas as two module-level dicts, `fastapi.openapi.utils.validation_error_definition` and `.validation_error_response_definition`. Reassign them **before** calling `override_validation_error` and the new shape is honored — this library reads them at call time, not at import time, and doesn't assume any particular field names or nesting. Useful, for example, to match an error envelope your other services already use:

```python
import fastapi.openapi.utils as fastapi_openapi_utils

fastapi_openapi_utils.validation_error_definition = {
    "title": "ValidationError",
    "type": "object",
    "properties": {
        "field": {"type": "array", "items": {"type": "string"}},
        "message": {"type": "string"},
        "issue_type": {"type": "string"},
    },
}
fastapi_openapi_utils.validation_error_response_definition = {
    "title": "HTTPValidationError",
    "type": "object",
    "properties": {
        "error_code": {"type": "string", "default": "VALIDATION_ERROR"},
        "message": {"type": "string", "default": "One or more fields failed validation"},
        "fields": {"type": "array", "items": {"$ref": "#/components/schemas/ValidationError"}},
    },
}

override_validation_error(app)  # must come after, same ordering rule as a custom app.openapi
```

If your schema already declares a component named `ValidationError` or `HTTPValidationError` for something else — anywhere in the app, not just on a route that needs validation — the library detects the collision and inserts its own copy under an alternate, namespaced name instead of overwriting yours. This works no matter how the definition above is shaped.

**This only changes the documented schema, not the runtime response body.** The built-in exception handler always returns `{"detail": [...]}` regardless of any reassignment above. To align the two, set `handle_exceptions=False` and provide your own handler matching the custom shape, as shown in [Custom exception handler](#custom-exception-handler).

### Preserving a custom app.openapi

Call `override_validation_error` **after** assigning your custom openapi function. The library captures `app.openapi` at call time and wraps it, so the order matters.

```python
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from fastapi_validation_override import override_validation_error

app = FastAPI()


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title="My API", version="1.0.0", routes=app.routes)
    schema["info"]["x-logo"] = {"url": "https://example.com/logo.png"}
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]
override_validation_error(app)  # must come after
```

### Merging with an existing response at the target code

When a route already declares a response at the target status code, `override_validation_error` merges the schemas using `anyOf` instead of overwriting the existing one.

```python
class OutOfStockError(BaseModel):
    message: str
    item_name: str


@app.post("/items", responses={400: {"model": OutOfStockError, "description": "Out of stock"}})
async def create_item(item: Item) -> dict[str, object]:
    return item.model_dump()


override_validation_error(app)
# schema at 400: anyOf: [HTTPValidationError, OutOfStockError]
```

The merge only touches the `schema` (the JSON Schema union). It doesn't generate an OpenAPI `example`/`examples` value for either variant, so tools like Swagger UI won't show a distinct sample payload for `OutOfStockError` versus the validation error unless you declare one yourself (e.g. via a field default, or `model_config = ConfigDict(json_schema_extra={"example": ...})`) — the library can't safely invent one for a model it knows nothing about.

If the response you already declared at the target code is a local `$ref` to `#/components/responses/...`, chained refs are followed to the terminal Response Object and the merge happens on an inlined copy, leaving the shared components untouched. An external, unresolvable, or cyclic `$ref` is left as-is.

Set `merge_target_response=False` to leave a response you already declared at the target code completely untouched instead of merging it with `anyOf`:

```python
override_validation_error(app, merge_target_response=False)
```

### Independent 422 handling

A route can keep its own, non-validation 422 response. As long as the route has a body or parameters that FastAPI validates, it's left untouched at 422, and the validation error is still documented at the target code — independently of what occupies 422.

```python
class OutOfStockError(BaseModel):
    error_code: str
    item_name: str


@app.post("/items", responses={422: {"model": OutOfStockError, "description": "Item is out of stock"}})
async def create_item(item: Item) -> dict[str, object]:
    return item.model_dump()


override_validation_error(app)
# 422 still documents OutOfStockError, untouched.
# 400 is added automatically, documenting the validation error schema.
```

**This also applies at runtime.** If this route receives a request that fails validation, the exception handler still returns `target_code` (400 by default), not the custom 422 — `responses={422: ...}` only affects documentation, it never changes which exception handler FastAPI dispatches to. Your custom 422 response is for errors you raise yourself (like `OutOfStockError` above), not for request validation failures.

> **Note:** when the validation schema is synthesized this way, `HTTPValidationError` and `ValidationError` are added to `components.schemas` if they aren't already there. If you snapshot-test your OpenAPI schema, expect these two component definitions to appear the first time this happens.

> **Known limitation:** a parameter declared with `include_in_schema=False` still triggers validation at runtime, but it's invisible in the generated schema. If such a route *also* declares its own response at 422, `4XX`, or `default`, FastAPI never emits its own 422 response for that operation — the only signal this library relies on to detect that the route needs validation in the first place. In that specific combination, `target_code` won't be documented, even though the route can still return it at runtime.

## Examples

Runnable examples are in the [`examples/`](https://github.com/mat81black/fastapi-validation-override/tree/main/examples) directory:

| File | Description |
|---|---|
| [`basic.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/basic.py) | Minimal setup with the default 400 status code |
| [`custom_status_code.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/custom_status_code.py) | Using a custom status code (409) |
| [`handle_exceptions_false.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/handle_exceptions_false.py) | Custom exception handler with schema-only patch |
| [`custom_validation_schema.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/custom_validation_schema.py) | Replacing the validation error schema with a custom error envelope |
| [`custom_openapi.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/custom_openapi.py) | Preserving a custom `app.openapi` function |
| [`existing_response_at_target_code.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/existing_response_at_target_code.py) | `anyOf` merge when the target code is already declared |
| [`custom_422_response.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/custom_422_response.py) | Keeping a custom, non-validation 422 response |
| [`with_apirouter.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/with_apirouter.py) | Usage with multiple `APIRouter` instances |
| [`webhooks_and_callbacks.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/webhooks_and_callbacks.py) | Coverage extends to webhooks and callbacks, not just regular paths |

## Release Notes

[RELEASE_NOTES](https://github.com/mat81black/fastapi-validation-override/blob/main/RELEASE_NOTES.md)

## License

[MIT](https://github.com/mat81black/fastapi-validation-override/blob/main/LICENSE)
