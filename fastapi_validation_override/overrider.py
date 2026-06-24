from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def override_validation_error(app: FastAPI, status_code: int = status.HTTP_400_BAD_REQUEST, handle_exceptions: bool = True) -> None:
    """
    Sovrascrive la gestione degli errori di validazione di FastAPI (di default 422).

    Rispetta e preserva al 100% qualsiasi funzione `app.openapi` custom già definita
    dallo sviluppatore, applicando la patch in coda ad essa.
    """
    if status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        return

    # Controllo di sicurezza: se abbiamo già applicato l'override su questa app,
    # usciamo immediatamente per prevenire handler duplicati e loop di ricorsione.
    if getattr(app.state, "_validation_overridden", False):
        return

    if handle_exceptions:
        @app.exception_handler(RequestValidationError)
        async def custom_validation_exception_handler(
                _request: Request, exc: RequestValidationError
        ) -> JSONResponse:
            return JSONResponse(
                status_code=status_code,
                content={"detail": jsonable_encoder(exc.errors())},
            )

    target_code = str(status_code)

    # Salviamo il riferimento alla funzione openapi corrente dell'app.
    # Può essere il metodo nativo di FastAPI o una funzione custom già iniettata dal dev.
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any] | None:
        # Deleghiamo interamente la gestione della cache a original_openapi().
        # Se il dev segue il pattern documentato da FastAPI, qui la cache viene
        # gestita correttamente. Noi patchiamo in-place il risultato.
        schema = original_openapi()

        # Applichiamo la nostra patch direttamente sul dizionario generato
        for _path, path_item in schema.get("paths", {}).items():
            for _method, operation in path_item.items():
                if _method not in _HTTP_METHODS:
                    # Salta chiavi non-operation (summary, description, servers, parameters…)
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
                                "application/json", {})
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

    app.openapi = custom_openapi
    app.state._validation_overridden = True