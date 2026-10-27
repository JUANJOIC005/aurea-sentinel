"""Datos que necesita el formulario de registro antes de iniciar sesión (sin información sensible)."""
from fastapi import APIRouter, Query

from .. import db, usuarios

router = APIRouter(prefix="/publico")


@router.get("/areas")
def areas():
    with db.conexion() as conn:
        return usuarios.areas(conn)


@router.get("/supervisores")
def supervisores(area: str = Query(pattern=r"^A[1-9]$")):
    with db.conexion() as conn:
        return usuarios.supervisores_de_area(conn, area)
