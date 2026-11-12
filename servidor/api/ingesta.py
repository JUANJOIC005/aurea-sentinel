"""Entrada de lecturas firmadas (la usa el simulador)."""
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from .. import auditoria, claves, db, ingesta
from .errores import ErrorNegocio

router = APIRouter()

MENSAJE_FIRMA = "Firma no válida."


class LecturaEntrada(BaseModel):
    tag: str = Field(min_length=1, max_length=20)
    instante: str = Field(min_length=1, max_length=40)
    valor: float


class PeticionIngesta(BaseModel):
    lecturas: list[LecturaEntrada] = Field(min_length=1, max_length=ingesta.MAX_LECTURAS)


async def _cuerpo(request: Request) -> bytes:
    return await request.body()


@router.post("/ingesta/lecturas")
def recibir_lecturas(request: Request, cuerpo: bytes = Depends(_cuerpo),
                     marca: str | None = Header(default=None, alias="X-Aurea-Marca"),
                     firma: str | None = Header(default=None, alias="X-Aurea-Firma")):
    if not ingesta.firma_valida(claves.clave_ingesta(), marca, firma, cuerpo):
        ip = request.client.host if request.client else "desconocida"
        with db.conexion() as conn:
            auditoria.registrar(conn, "ingesta_firma_invalida", "denegado", recurso="lectura",
                                detalle={"ip": ip})
        raise ErrorNegocio(401, MENSAJE_FIRMA)

    try:
        peticion = PeticionIngesta.model_validate_json(cuerpo)
    except ValidationError:
        raise ErrorNegocio(422, f"El envío no es válido: se esperan de 1 a {ingesta.MAX_LECTURAS} lecturas "
                                f"con tag, instante y valor.") from None

    with db.conexion() as conn:
        resultado = ingesta.ingestar(conn, [lectura.model_dump() for lectura in peticion.lecturas])
    if not resultado["aceptadas"] and not resultado["duplicadas"]:
        return JSONResponse({"detalle": "Ninguna lectura es válida.", **resultado}, status_code=422)
    return resultado
