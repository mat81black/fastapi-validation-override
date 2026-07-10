from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def override_validation_error(app: FastAPI, status_code: int = 400, handle_exceptions: bool = True) -> None:
    """
    Override FastAPI's default 422 validation error response with a custom status code.

    Cache management is intentionally delegated to the original `app.openapi` so that
    any custom OpenAPI function already set by the developer is fully preserved.

    :param app: The FastAPI application instance to patch.
    :param status_code: The HTTP status code to use instead of 422. Defaults to 400.
    :param handle_exceptions: If True, registers an exception handler that returns the custom
        status code at runtime. Set to False to patch only the OpenAPI schema and
        handle the exception yourself.
    """
    if status_code == 422:
        return

    # Guard against registering duplicate handlers and patches on repeated calls.
    if getattr(app.state, "_validation_overridden", False):
        return

    if handle_exceptions:

        @app.exception_handler(RequestValidationError)
        async def custom_validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
            return JSONResponse(
                status_code=status_code,
                content={"detail": jsonable_encoder(exc.errors())},
            )

    target_code = str(status_code)
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        schema = original_openapi()

        for _path, path_item in schema.get("paths", {}).items():
            for _method, operation in path_item.items():
                if _method not in _HTTP_METHODS:
                    # path_item may contain non-operation keys: summary, description, servers, parameters
                    continue

                responses = operation.get("responses", {})

                if "422" in responses:
                    response_422 = responses["422"]
                    content_422 = response_422.get("content", {}).get("application/json", {})
                    schema_422 = content_422.get("schema", {})
                    ref = schema_422.get("$ref", "")

                    if ref.endswith("HTTPValidationError"):
                        if target_code in responses:
                            existing_response = responses[target_code]
                            existing_content = existing_response.setdefault("content", {}).setdefault(
                                "application/json", {}
                            )
                            existing_schema = existing_content.setdefault("schema", {})

                            if "anyOf" in existing_schema:
                                existing_schema["anyOf"].append(schema_422)
                            elif existing_schema:
                                existing_content["schema"] = {"anyOf": [existing_schema, schema_422]}
                            else:
                                existing_content["schema"] = schema_422

                            old_desc = existing_response.get("description", "Error")
                            existing_response["description"] = f"{old_desc} / Validation Error"

                            del responses["422"]
                        else:
                            responses[target_code] = responses.pop("422")

        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]  # ty: ignore[invalid-assignment]
    app.state._validation_overridden = True
