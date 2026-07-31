from collections.abc import Iterator
from copy import deepcopy
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.constants import REF_PREFIX
from fastapi.openapi.utils import validation_error_definition, validation_error_response_definition
from fastapi.responses import JSONResponse

_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
_VALIDATION_ERROR_REF = {"$ref": f"{REF_PREFIX}HTTPValidationError"}


def _validation_error_ref(name: str = "HTTPValidationError") -> dict[str, str]:
    """Fresh dict: never share the same object across routes or apps."""
    return {"$ref": f"{REF_PREFIX}{name}"}


def _operation_needs_validation(operation: dict[str, Any]) -> bool:
    return bool(operation.get("requestBody")) or bool(operation.get("parameters"))


def _iter_path_item_operations(path_item: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for method, operation in path_item.items():
        if method not in _HTTP_METHODS or not isinstance(operation, dict):
            # path_item may hold non-operation keys (summary, parameters, ...) or itself be a $ref
            continue
        yield operation


def _iter_operations(schema: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every Operation Object in the schema: paths, webhooks, and callbacks, recursively."""
    for container_key in ("paths", "webhooks"):
        container = schema.get(container_key)
        if not isinstance(container, dict):
            continue

        for path_item in container.values():
            if not isinstance(path_item, dict):
                continue

            for operation in _iter_path_item_operations(path_item):
                yield operation

                callbacks = operation.get("callbacks")
                if isinstance(callbacks, dict):
                    for callback_paths in callbacks.values():
                        if isinstance(callback_paths, dict):
                            yield from _iter_operations({"paths": callback_paths})


def _resolve_validation_ref(schema: dict[str, Any]) -> tuple[dict[str, str], str]:
    """
    Ensure ValidationError/HTTPValidationError components exist in `schema`, picking an alternate
    name for either one the schema already declares for something else. Returns a $ref to the
    HTTPValidationError component and the name it was inserted under.
    """
    components = schema.setdefault("components", {}).setdefault("schemas", {})

    validation_error_name = "ValidationError"
    existing_ve = components.get(validation_error_name)
    if existing_ve is not None and existing_ve != validation_error_definition:
        validation_error_name = "FastAPIValidationOverride_ValidationError"

    http_validation_error_def: dict[str, Any] = deepcopy(validation_error_response_definition)
    if validation_error_name != "ValidationError":
        http_validation_error_def["properties"]["detail"]["items"]["$ref"] = f"{REF_PREFIX}{validation_error_name}"

    http_validation_error_name = "HTTPValidationError"
    existing_http_validation_error = components.get(http_validation_error_name)
    if existing_http_validation_error is not None and existing_http_validation_error != http_validation_error_def:
        http_validation_error_name = "FastAPIValidationOverride_HTTPValidationError"

    if validation_error_name not in components:
        components[validation_error_name] = deepcopy(validation_error_definition)
    if http_validation_error_name not in components:
        components[http_validation_error_name] = http_validation_error_def

    return _validation_error_ref(http_validation_error_name), http_validation_error_name


def patch_422_responses(
    schema: dict[str, Any], target_code: str, *, merge_target_response: bool = True
) -> dict[str, Any]:
    """
    Move FastAPI's 422 validation error response to `target_code`, across paths, webhooks, and
    callbacks (recursively, for callbacks declared on any operation).

    A parameter declared with `include_in_schema=False` still triggers validation at runtime, but
    is invisible in the generated schema. If such a route also already occupies 422, `4XX`, or
    `default` with something else, FastAPI never emits its own 422 response for that operation —
    the only signal this function relies on to detect the need for validation on such a parameter.
    In that specific combination, `target_code` won't be documented.

    :param schema: An OpenAPI schema dict, such as one returned by `app.openapi()`.
    :param target_code: The status code to document the validation error at, e.g. `"400"`.
    :param merge_target_response: If True (default), a response already declared at `target_code`
        is merged with the validation error schema using `anyOf`. If False, it is left untouched.
    :return: The same `schema` dict, mutated in place.
    """
    validation: tuple[dict[str, str], str] | None = None

    for operation in _iter_operations(schema):
        responses = operation.setdefault("responses", {})

        removed_fastapi_422 = False
        response_422 = responses.get("422")
        if response_422 is not None:
            schema_422 = response_422.get("content", {}).get("application/json", {}).get("schema", {})
            if schema_422 == _VALIDATION_ERROR_REF:
                del responses["422"]
                removed_fastapi_422 = True

        if not (removed_fastapi_422 or _operation_needs_validation(operation)):
            continue

        if validation is None:
            validation = _resolve_validation_ref(schema)
        validation_ref, validation_ref_name = validation

        if target_code in responses:
            if not merge_target_response:
                continue

            existing_response = responses[target_code]
            existing_content = existing_response.setdefault("content", {}).setdefault("application/json", {})
            existing_schema = existing_content.setdefault("schema", {})

            if "anyOf" in existing_schema:
                if validation_ref not in existing_schema["anyOf"]:
                    existing_schema["anyOf"].insert(0, _validation_error_ref(validation_ref_name))
            elif existing_schema and existing_schema != validation_ref:
                existing_content["schema"] = {"anyOf": [_validation_error_ref(validation_ref_name), existing_schema]}
            elif not existing_schema:
                existing_content["schema"] = _validation_error_ref(validation_ref_name)

            old_desc = existing_response.get("description", "Error")
            if "Validation Error" not in old_desc:
                existing_response["description"] = f"{old_desc} / Validation Error"
        else:
            responses[target_code] = {
                "description": "Validation Error",
                "content": {"application/json": {"schema": _validation_error_ref(validation_ref_name)}},
            }

    return schema


def override_validation_error(
    app: FastAPI,
    status_code: int = 400,
    handle_exceptions: bool = True,
    merge_target_response: bool = True,
) -> None:
    """
    Override FastAPI's default 422 validation error response with a custom status code.

    Cache management is intentionally delegated to the original `app.openapi` so that
    any custom OpenAPI function already set by the developer is fully preserved.

    :param app: The FastAPI application instance to patch.
    :param status_code: The HTTP status code to use instead of 422. Defaults to 400.
    :param handle_exceptions: If True, registers an exception handler that returns the custom
        status code at runtime. Set to False to patch only the OpenAPI schema and
        handle the exception yourself.
    :param merge_target_response: If True (default), a response you already declared at
        `status_code` is merged with the validation error schema using `anyOf`. If False,
        it is left untouched.
    :return: None. `app` is patched in place.
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
        schema = patch_422_responses(original_openapi(), target_code, merge_target_response=merge_target_response)
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]  # ty: ignore[invalid-assignment]
    app.state._validation_overridden = True
