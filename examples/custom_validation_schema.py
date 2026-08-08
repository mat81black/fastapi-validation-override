"""
Replace the validation error schema with a custom error envelope.

Run:

    uvicorn examples.custom_validation_schema:app --reload
"""

from typing import Any

import fastapi.openapi.utils as fastapi_openapi_utils

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

# Match an existing company-wide error envelope instead of FastAPI's default {"detail": [...]}.
# Must be reassigned before override_validation_error runs, since it reads these at call time.
fastapi_openapi_utils.validation_error_definition = {  # ty: ignore[invalid-assignment]
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

app = FastAPI(
    title="Custom Validation Schema Example",
    description="Documents and returns validation errors using a custom error envelope "
    "instead of FastAPI's default shape.",
)


class Item(BaseModel):
    name: str
    price: float


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "One or more fields failed validation",
            "fields": [
                {"field": [str(part) for part in error["loc"]], "message": error["msg"], "issue_type": error["type"]}
                for error in exc.errors()
            ],
        },
    )


@app.post("/items")
async def create_item(item: Item) -> dict[str, Any]:
    return item.model_dump()


override_validation_error(app, status_code=400, handle_exceptions=False)
# handle_exceptions=False: the handler above is already responsible for matching the schema above.
