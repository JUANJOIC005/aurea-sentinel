"""Servidor API de AUREA Sentinel.

    ./run.sh servidor        (o: python -m uvicorn servidor.api.main:app)
"""
from fastapi import FastAPI

from . import auth, errores, publico

app = FastAPI(title="AUREA Sentinel", version="0.1.0")
errores.instalar(app)
app.include_router(auth.router)
app.include_router(publico.router)


@app.get("/salud")
def salud():
    return {"estado": "ok"}
