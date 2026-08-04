# Release Notes

## Latest Changes

### Internal

* ✅ Prove PR test changes actually catch a regression before merging. PR [#53](https://github.com/mat81black/fastapi-validation-override/pull/53) by [@mat81black](https://github.com/mat81black).
* ⬆ Bump fastapi from 0.139.2 to 0.140.0. PR [#52](https://github.com/mat81black/fastapi-validation-override/pull/52) by [@dependabot[bot]](https://github.com/apps/dependabot).
* ⬆ Bump the python-packages group with 5 updates. PR [#51](https://github.com/mat81black/fastapi-validation-override/pull/51) by [@dependabot[bot]](https://github.com/apps/dependabot).
* ⬆ Bump the github-actions group with 2 updates. PR [#50](https://github.com/mat81black/fastapi-validation-override/pull/50) by [@dependabot[bot]](https://github.com/apps/dependabot).

## 1.1.0 (2026-08-01)

### Features

* ✨ Support custom validation error schemas with any field structure. PR [#44](https://github.com/mat81black/fastapi-validation-override/pull/44) by [@mat81black](https://github.com/mat81black).
* ✨ Extend validation error patching to webhooks and callbacks. PR [#35](https://github.com/mat81black/fastapi-validation-override/pull/35) by [@mat81black](https://github.com/mat81black).

### Fixes

* 🐛 Fix cyclic and unresolvable `$ref` handling in local response resolution. PR [#45](https://github.com/mat81black/fastapi-validation-override/pull/45) by [@mat81black](https://github.com/mat81black).
* 🐛 Fix invalid OpenAPI produced when merging into a $ref target response. PR [#40](https://github.com/mat81black/fastapi-validation-override/pull/40) by [@mat81black](https://github.com/mat81black).
* 🐛 Fix user-defined schemas being silently overwritten by validation error definitions. PR [#39](https://github.com/mat81black/fastapi-validation-override/pull/39) by [@mat81black](https://github.com/mat81black).
* 🐛 Base validation detection on FastAPI's 422 signal instead of schema shape alone. PR [#38](https://github.com/mat81black/fastapi-validation-override/pull/38) by [@mat81black](https://github.com/mat81black).
* 🐛 Fix custom 422 models with a name ending in HTTPValidationError being silently deleted. PR [#37](https://github.com/mat81black/fastapi-validation-override/pull/37) by [@mat81black](https://github.com/mat81black).
* 🐛 Fix shared mutable schema objects leaking mutations across routes and apps. PR [#36](https://github.com/mat81black/fastapi-validation-override/pull/36) by [@mat81black](https://github.com/mat81black).

### Refactors

* ♻️ Refactor local $ref resolution to support reusable components across multiple sections. PR [#46](https://github.com/mat81black/fastapi-validation-override/pull/46) by [@mat81black](https://github.com/mat81black).
* ♻️ Read FastAPI's validation error definitions dynamically instead of at import time. PR [#41](https://github.com/mat81black/fastapi-validation-override/pull/41) by [@mat81black](https://github.com/mat81black).

### Docs

* 📝 Clarify behavior for `ValidationError`/`HTTPValidationError` schema collisions in README. PR [#48](https://github.com/mat81black/fastapi-validation-override/pull/48) by [@mat81black](https://github.com/mat81black).
* 📝 Clarify idempotency behavior in README. PR [#43](https://github.com/mat81black/fastapi-validation-override/pull/43) by [@mat81black](https://github.com/mat81black).

### Internal

* ✅ Cover webhooks and callbacks with a runnable example. PR [#47](https://github.com/mat81black/fastapi-validation-override/pull/47) by [@mat81black](https://github.com/mat81black).

## 1.0.0 (2026-07-28)

🎉 First stable release of fastapi-validation-override.

## 0.2.0 (2026-07-27)

### Features

* ✨ Keep validation errors documented at the target code even with a custom 422 response. PR [#31](https://github.com/mat81black/fastapi-validation-override/pull/31) by [@mat81black](https://github.com/mat81black).
* ✨ Add public patch_422_responses for schema patching outside override_validation_error. PR [#30](https://github.com/mat81black/fastapi-validation-override/pull/30) by [@mat81black](https://github.com/mat81black).

### Refactors

* ♻️ Reorder anyOf to list the validation error before the custom response. PR [#32](https://github.com/mat81black/fastapi-validation-override/pull/32) by [@mat81black](https://github.com/mat81black).

### Internal

* ⬆ Bump pre-commit hooks. PR [#29](https://github.com/mat81black/fastapi-validation-override/pull/29) by [@mat81black](https://github.com/mat81black).
* ⬆ Bump the github-actions group with 3 updates. PR [#28](https://github.com/mat81black/fastapi-validation-override/pull/28) by [@dependabot[bot]](https://github.com/apps/dependabot).
* ⬆ Bump fastapi from 0.139.0 to 0.139.2. PR [#27](https://github.com/mat81black/fastapi-validation-override/pull/27) by [@dependabot[bot]](https://github.com/apps/dependabot).
* ⬆ Bump the python-packages group with 5 updates. PR [#26](https://github.com/mat81black/fastapi-validation-override/pull/26) by [@dependabot[bot]](https://github.com/apps/dependabot).
* 👷 Replace Dependabot pre-commit ecosystem with custom bump workflow. PR [#25](https://github.com/mat81black/fastapi-validation-override/pull/25) by [@mat81black](https://github.com/mat81black).
* ⬆ Bump the python-packages group across 1 directory with 6 updates. PR [#24](https://github.com/mat81black/fastapi-validation-override/pull/24) by [@dependabot[bot]](https://github.com/apps/dependabot).
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
