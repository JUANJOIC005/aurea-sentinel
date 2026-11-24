"""Servidor API de AUREA Sentinel.

    ./run.sh servidor        (o: python -m uvicorn servidor.api.main:app)
"""
from fastapi import FastAPI

from . import auth, datos, errores, ingesta, publico, segundo_factor

app = FastAPI(title="AUREA Sentinel", version="0.2.0")
errores.instalar(app)
app.include_router(auth.router)
app.include_router(segundo_factor.router)
app.include_router(publico.router)
app.include_router(datos.router)
app.include_router(ingesta.router)


@app.get("/salud")
def salud():
    return {"estado": "ok"}
