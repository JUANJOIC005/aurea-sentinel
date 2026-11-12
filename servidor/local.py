"""Servidor local: la aplicación lo arranca dentro de su propio proceso, sin instalar nada aparte.

Prepara la base de datos (la crea si no existe) y levanta la API en 127.0.0.1 con un puerto libre.
La primera vez, si no hay ninguna cuenta, crea las de demostración de la central ficticia y, si no hay lecturas,
carga 30 días de histórico de los 36 sensores (unos 3 segundos). Mientras está abierta anota su dirección en
`servidor.json` para que el simulador, que es otro proceso, sepa dónde enviar las lecturas.
"""
import os
import socket
import threading
import time

import uvicorn

from . import datos_demo, db, descubrimiento, historico, migrate
from .api.main import app


class ServidorLocal:
    def __init__(self):
        self._socket = socket.socket()
        self._socket.bind(("127.0.0.1", 0))          # puerto 0: el sistema elige uno libre
        self.puerto = self._socket.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.puerto}"
        # Sin registro en consola ni formato propio: la aplicación empaquetada no tiene consola.
        configuracion = uvicorn.Config(app, log_config=None, loop="asyncio", http="h11", lifespan="off")
        self._servidor = uvicorn.Server(configuracion)
        self._hilo = threading.Thread(target=self._servidor.run, kwargs={"sockets": [self._socket]}, daemon=True)

    def arrancar(self, espera: float = 10.0) -> None:
        self._hilo.start()
        limite = time.monotonic() + espera
        while not self._servidor.started:
            if not self._hilo.is_alive() or time.monotonic() > limite:
                raise RuntimeError("El servidor local no ha podido arrancar.")
            time.sleep(0.02)
        descubrimiento.publicar(self.url)

    def parar(self) -> None:
        descubrimiento.retirar()
        self._servidor.should_exit = True
        self._hilo.join(timeout=5)
        self._socket.close()


def preparar_base_de_datos() -> bool:
    """Crea o actualiza la base de datos y, si está vacía, las cuentas de demostración y 30 días de lecturas
    (la variable AUREA_SIN_HISTORICO desactiva la carga de lecturas, para las pruebas).
    Devuelve True si ha creado las cuentas de demostración."""
    migrate.preparar()
    creadas = False
    with db.conexion() as conn:
        if not conn.execute("SELECT 1 FROM usuario LIMIT 1").fetchone():
            datos_demo.crear_cuentas(conn, datos_demo.password_demo())
            creadas = True
        if not os.environ.get("AUREA_SIN_HISTORICO") and not historico.hay_lecturas(conn):
            historico.cargar(conn)
    return creadas


def iniciar() -> ServidorLocal:
    preparar_base_de_datos()
    servidor = ServidorLocal()
    servidor.arrancar()
    return servidor
