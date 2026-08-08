"""Smoke tests for examples/: each file should import cleanly and produce a valid OpenAPI schema."""

import importlib.util

from pathlib import Path

import fastapi.openapi.utils as fastapi_openapi_utils
import pytest

from fastapi import FastAPI

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*.py"))


@pytest.mark.parametrize("example_file", EXAMPLE_FILES, ids=lambda path: path.stem)
def test_example_imports_and_generates_openapi_schema(example_file: Path) -> None:
    # custom_validation_schema.py reassigns these at module level without restoring them; save and
    # restore around every example so import order can never leak state into other tests.
    original_validation_error = fastapi_openapi_utils.validation_error_definition
    original_http_validation_error = fastapi_openapi_utils.validation_error_response_definition

    spec = importlib.util.spec_from_file_location(example_file.stem, example_file)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    finally:
        fastapi_openapi_utils.validation_error_definition = original_validation_error
        fastapi_openapi_utils.validation_error_response_definition = original_http_validation_error

    assert isinstance(module.app, FastAPI)
    schema = module.app.openapi()
    assert isinstance(schema, dict)
    assert "paths" in schema
