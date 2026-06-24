from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fastapi_validation_override import override_validation_error

app = FastAPI(
    title="Custom Exception Handler Example",
    description="Patch only the OpenAPI schema and handle the exception with custom logic.",
)


class Item(BaseModel):
    name: str
    price: float


@app.exception_handler(RequestValidationError)
async def custom_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "message": "Validation failed",
            "errors": exc.errors(),
        },
    )


@app.post("/items")
async def create_item(item: Item) -> dict[str, Any]:
    return item.model_dump()


override_validation_error(app, status_code=400, handle_exceptions=False)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002)
