# Release Notes

## Latest Changes

## 0.1.0 (2026-06-24)

🚀 First official public release of **fastapi-validation-override**.

This library provides a simple, one-call solution to override FastAPI's default 422 validation error response with any HTTP status code. It patches both the runtime exception handler and the OpenAPI schema simultaneously, preserving any custom `app.openapi` function already defined by the developer.

### Features

* ✨ Override the default 422 validation error with any HTTP status code at runtime and in the OpenAPI schema with a single call.
* ✨ Automatic OpenAPI schema patch: the 422 entry is replaced by the target status code across all routes that produce a `HTTPValidationError`.
* ✨ Smart schema merge: if a route already declares a response at the target status code, the validation error schema is merged using `anyOf` without losing the existing definition.
* ✨ Custom `app.openapi` preserved: any custom OpenAPI function set by the developer is called first; the patch is applied on top of its output.
* ✨ Bring your own handler: `handle_exceptions=False` patches only the schema, leaving full control of the exception handling to the developer.
* ✨ Idempotent: safe to call multiple times on the same app instance.
