# FastAPI Validation Override

[![PyPI](https://img.shields.io/pypi/v/fastapi-validation-override)](https://pypi.org/project/fastapi-validation-override/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/fastapi-validation-override)](https://pypi.org/project/fastapi-validation-override/)

Override FastAPI's default **422 Unprocessable Entity** validation error with any HTTP status code — both at runtime and in the OpenAPI schema.

Call `override_validation_error(app)` once after defining your routes. Validation errors will return the chosen status code with the standard `{"detail": [...]}` body.

---

## Features

- **Runtime + schema** — patches both the exception handler and the OpenAPI schema in one call
- **Any status code** — use 400, 409, or any other code instead of 422
- **Schema-aware merge** — if a route already declares a response at the target code, the validation error schema is merged using `anyOf`
- **Custom OpenAPI preserved** — any `app.openapi` function already defined is called first; the patch is applied on top
- **Custom exception handler** — set `handle_exceptions=False` to patch only the schema and handle the exception independently
- **Idempotent calls** — safe to invoke multiple times on the same app instance

---

## Requirements

- Python ≥ 3.10
- FastAPI ≥ 0.120.0

---

## Installation

```bash
pip install fastapi-validation-override
# or
uv add fastapi-validation-override
```

---

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
# POST /items with missing fields -> 400 Bad Request {"detail": [...]}
```

The `422` entry in the Swagger UI is replaced by `400` automatically.

---

## `override_validation_error` reference

```python
override_validation_error(app, status_code=400, handle_exceptions=True)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `app` | `FastAPI` | required | The FastAPI application instance to patch |
| `status_code` | `int` | `400` | HTTP status code to use instead of 422 |
| `handle_exceptions` | `bool` | `True` | If `True`, registers an exception handler that returns the custom status code at runtime. Set to `False` to patch only the OpenAPI schema and handle the exception independently |

Calling with `status_code=422` is a no-op — the default FastAPI behaviour is preserved unchanged.

---

## Advanced options

### Custom status code

```python
override_validation_error(app, status_code=409)
# Validation errors -> 409 Conflict
```

### Custom exception handler

Set `handle_exceptions=False` to define a custom response body or add logic on validation errors. The OpenAPI schema is still patched to reflect the correct status code.

```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from fastapi_validation_override import override_validation_error

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def custom_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "message": "Validation failed",
            "errors": exc.errors(),
        },
    )


override_validation_error(app, status_code=400, handle_exceptions=False)
```

### Preserving a custom `app.openapi`

If `app.openapi` has been replaced with a custom function, `override_validation_error` wraps it — the custom function is called first and the patch is applied to its output.

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


app.openapi = custom_openapi  # type: ignore[method-assign]  # ty: ignore[invalid-assignment]

override_validation_error(app)
# x-logo is preserved; 422 is replaced by 400 in the schema
```

### Existing response at target code

When a route already declares a response at the target status code, the validation error schema is merged into it using `anyOf` — neither schema is lost.

```python
from fastapi import FastAPI
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI()


class OutOfStockError(BaseModel):
    message: str
    item_name: str


class Item(BaseModel):
    name: str
    price: float


@app.post("/items", responses={400: {"model": OutOfStockError, "description": "Out of stock"}})
async def create_item(item: Item) -> dict[str, object]:
    return item.model_dump()


override_validation_error(app)
# responses.400.content.application/json.schema -> anyOf: [OutOfStockError, HTTPValidationError]
```

### Usage with `APIRouter`

`override_validation_error` applies to the whole application, regardless of how routes are organized.

```python
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI()
items_router = APIRouter(prefix="/items", tags=["items"])
users_router = APIRouter(prefix="/users", tags=["users"])

# ... define routes on each router ...

app.include_router(items_router)
app.include_router(users_router)

override_validation_error(app)
```

---

## Examples

Runnable examples are available in the [`examples/`](examples/) directory:

| File | What it shows |
|---|---|
| [`basic.py`](examples/basic.py) | Minimal setup with the default 400 status code |
| [`custom_status_code.py`](examples/custom_status_code.py) | Using a custom status code (409) |
| [`handle_exceptions_false.py`](examples/handle_exceptions_false.py) | Custom exception handler with schema-only patch |
| [`custom_openapi.py`](examples/custom_openapi.py) | Preserving a custom `app.openapi` function |
| [`existing_response_at_target_code.py`](examples/existing_response_at_target_code.py) | `anyOf` merge when the target code is already declared |
| [`with_apirouter.py`](examples/with_apirouter.py) | Usage with multiple `APIRouter` instances |

---

## License

[MIT](LICENSE)
