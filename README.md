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
- **anyOf merge**: when a route already declares a response at the target code, the validation error schema is merged rather than overwritten
- **Custom openapi preserved**: wraps any `app.openapi` function already installed and applies the patch on top of its output
- **Bring your own handler**: `handle_exceptions=False` skips the built-in handler while still patching the schema
- **Idempotent**: safe to call multiple times on the same app instance
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
override_validation_error(app, status_code=400, handle_exceptions=True)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `app` | `FastAPI` | required | The FastAPI application instance to patch |
| `status_code` | `int` | `400` | HTTP status code to use instead of 422. Calling with `422` is a no-op |
| `handle_exceptions` | `bool` | `True` | When `True`, registers an exception handler that returns the custom status code at runtime. Set to `False` to patch only the OpenAPI schema and handle the exception yourself |

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
# schema at 400: anyOf: [OutOfStockError, HTTPValidationError]
```

## Examples

Runnable examples are in the [`examples/`](https://github.com/mat81black/fastapi-validation-override/tree/main/examples) directory:

| File | Description |
|---|---|
| [`basic.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/basic.py) | Minimal setup with the default 400 status code |
| [`custom_status_code.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/custom_status_code.py) | Using a custom status code (409) |
| [`handle_exceptions_false.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/handle_exceptions_false.py) | Custom exception handler with schema-only patch |
| [`custom_openapi.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/custom_openapi.py) | Preserving a custom `app.openapi` function |
| [`existing_response_at_target_code.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/existing_response_at_target_code.py) | `anyOf` merge when the target code is already declared |
| [`with_apirouter.py`](https://github.com/mat81black/fastapi-validation-override/blob/main/examples/with_apirouter.py) | Usage with multiple `APIRouter` instances |

## Release Notes

[RELEASE_NOTES](https://github.com/mat81black/fastapi-validation-override/blob/main/RELEASE_NOTES.md)

## License

[MIT](https://github.com/mat81black/fastapi-validation-override/blob/main/LICENSE)
