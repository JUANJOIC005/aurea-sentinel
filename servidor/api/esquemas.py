"""Forma de los datos que entran en la API."""
from typing import Literal

from pydantic import BaseModel, Field

CORREO = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class PeticionLogin(BaseModel):
    correo: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class PeticionRegistro(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    correo: str = Field(pattern=CORREO, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    rol: Literal["supervisor", "tecnico", "auditor"]
    area: str | None = Field(default=None, pattern=r"^A[1-9]$")
    supervisor_id: int | None = Field(default=None, gt=0)
    motivo: str | None = Field(default=None, max_length=500)
