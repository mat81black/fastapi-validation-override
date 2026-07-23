# Release Notes

## Latest Changes

### Internal

* ⬆ Bump the github-actions group across 1 directory with 4 updates. PR [#23](https://github.com/mat81black/fastapi-validation-override/pull/23) by [@dependabot[bot]](https://github.com/apps/dependabot).

## 0.1.3 (2026-07-10)

### Refactors

* ♻️ Clarify idempotency guard comment to reflect actual behavior. PR [#17](https://github.com/mat81black/fastapi-validation-override/pull/17) by [@mat81black](https://github.com/mat81black).

### Docs

* 📝 Fix wrong package name in installation commands. PR [#19](https://github.com/mat81black/fastapi-validation-override/pull/19) by [@mat81black](https://github.com/mat81black).

### Internal

* ✅ Add tests for query param validation and multi-method path patching. PR [#18](https://github.com/mat81black/fastapi-validation-override/pull/18) by [@mat81black](https://github.com/mat81black).

## 0.1.2 (2026-07-09)

### Internal

* 🔧 Integrate Codecov for coverage tracking and update README. PR [#15](https://github.com/mat81black/fastapi-validation-override/pull/15) by [@mat81black](https://github.com/mat81black).

## 0.1.1 (2026-07-09)

### Docs

* 📝 Rewrite README with PyPI-safe links and corrected project metadata. PR [#13](https://github.com/mat81black/fastapi-validation-override/pull/13) by [@mat81black](https://github.com/mat81black).

### Internal

* ⬆ bump the python-packages group with 5 updates. PR [#11](https://github.com/mat81black/fastapi-validation-override/pull/11) by [@dependabot[bot]](https://github.com/apps/dependabot).
* ⬆ bump https://github.com/crate-ci/typos from v1.48.0 to 5.0.7 in the pre-commit group. PR [#9](https://github.com/mat81black/fastapi-validation-override/pull/9) by [@dependabot[bot]](https://github.com/apps/dependabot).
* ⬆ bump dorny/paths-filter from 4.0.1 to 4.0.2 in the github-actions group. PR [#10](https://github.com/mat81black/fastapi-validation-override/pull/10) by [@dependabot[bot]](https://github.com/apps/dependabot).
* ⬆ bump fastapi from 0.138.0 to 0.139.0. PR [#12](https://github.com/mat81black/fastapi-validation-override/pull/12) by [@dependabot[bot]](https://github.com/apps/dependabot).
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
