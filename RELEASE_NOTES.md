# Release Notes

## Latest Changes

### Internal

* 🔧 Overhaul CI/CD workflows for labeling, releases, and coverage tracking. PR [#8](https://github.com/mat81black/fastapi-validation-override/pull/8) by [@mat81black](https://github.com/mat81black).

## 0.1.0 (2026-06-25)

🚀 First official public release of **fastapi-validation-override**.

Override FastAPI's default 422 validation error with any HTTP status code — patching both the runtime exception handler and the OpenAPI schema in a single call.

### Features

* ✨ Override the default 422 validation error with any HTTP status code at runtime and in the OpenAPI schema with a single call.
* ✨ Automatic OpenAPI schema patch: the 422 entry is replaced by the target status code across all routes that produce a `HTTPValidationError`.
* ✨ Smart schema merge: if a route already declares a response at the target status code, the validation error schema is merged using `anyOf`.
* ✨ Custom `app.openapi` preserved: any custom OpenAPI function set by the developer is called first; the patch is applied on top of its output.
* ✨ Custom exception handler: `handle_exceptions=False` patches only the schema, leaving full control of exception handling to the developer.
* ✨ Idempotent: safe to call multiple times on the same app instance.
