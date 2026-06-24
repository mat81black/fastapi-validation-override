#!/usr/bin/env bash
set -x

ruff check fastapi_validation_override tests examples --fix
ruff format fastapi_validation_override tests examples
