"""Errores de la API: todas las respuestas de error llevan {"detalle": "mensaje"}."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorNegocio(Exception):
    def __init__(self, estado: int, mensaje: str):
        super().__init__(mensaje)
        self.estado = estado
        self.mensaje = mensaje


def instalar(app: FastAPI) -> None:
    @app.exception_handler(ErrorNegocio)
    async def _negocio(_: Request, error: ErrorNegocio):
        return JSONResponse({"detalle": error.mensaje}, status_code=error.estado)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, error: RequestValidationError):
        campos = sorted({str(e["loc"][-1]) for e in error.errors() if e.get("loc")})
        return JSONResponse(
            {"detalle": "Los datos enviados no son válidos: " + ", ".join(campos) + "."},
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, error: StarletteHTTPException):
        return JSONResponse({"detalle": str(error.detail)}, status_code=error.status_code)
