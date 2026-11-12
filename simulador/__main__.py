"""Simulador de sensores de la central Valdecierzo.

Con la aplicación abierta, envía las lecturas firmadas a su servidor local:

    AUREA Sentinel.exe --simulador                  # una lectura de los 36 sensores cada 5 s, hasta Ctrl+C
    AUREA Sentinel.exe --simulador --ciclos 10 --intervalo 1
    AUREA Sentinel.exe --simulador --destino bd     # sin la aplicación: escribe en la base de datos, sin firma
"""
import argparse
import os
import random
import sys
import time
from datetime import datetime, timezone

import httpx

from servidor import claves, config, descubrimiento, migrate

from .destinos import DestinoApi, DestinoBaseDeDatos, ErrorDestino
from .modelo import Lectura, SensorSimulado

MAX_FALLOS_SEGUIDOS = 5


def generar(simulados: list[SensorSimulado], instante: datetime, dt: float,
            con_excursiones: bool = True) -> list[Lectura]:
    return [
        Lectura(s.sensor.id, s.sensor.tag, instante, s.siguiente(dt, con_excursiones))
        for s in simulados
    ]


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def ejecutar(destino, sensores, intervalo: float, ciclos: int | None, semilla: int | None,
             con_excursiones: bool = True, dormir=time.sleep, reloj=ahora_utc,
             max_fallos: int = MAX_FALLOS_SEGUIDOS) -> int:
    """Genera lecturas y las manda al destino. Devuelve cuántos ciclos ha hecho.

    Si el destino falla (servidor cerrado un momento…) avisa y sigue; tras `max_fallos` fallos seguidos se rinde."""
    azar = random.Random(semilla)
    simulados = [SensorSimulado(s, random.Random(azar.random())) for s in sensores]
    hechos, fallos = 0, 0
    try:
        while ciclos is None or hechos < ciclos:
            instante = reloj()
            lecturas = generar(simulados, instante, intervalo, con_excursiones)
            try:
                destino.enviar(lecturas)
                fallos = 0
            except ErrorDestino as error:
                fallos += 1
                print(f"Aviso: {error}", file=sys.stderr)
                if fallos >= max_fallos:
                    raise
            hechos += 1
            if ciclos is None or hechos < ciclos:
                dormir(intervalo)
    except KeyboardInterrupt:
        pass
    return hechos


def buscar_servidor(url: str | None) -> str:
    """La dirección del servidor: la indicada, la de AUREA_API_URL o la que anota la aplicación al abrirse."""
    url = url or os.environ.get("AUREA_API_URL") or descubrimiento.leer()
    if not url:
        raise ErrorDestino("No hay ninguna aplicación AUREA Sentinel abierta. Ábrela primero, o usa --destino bd.")
    try:
        httpx.get(url.rstrip("/") + "/salud", timeout=3.0).raise_for_status()
    except httpx.HTTPError as error:
        raise ErrorDestino(f"El servidor {url} no responde. Abre la aplicación, o usa --destino bd.") from error
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de sensores de AUREA Sentinel")
    parser.add_argument("--intervalo", type=float, default=5.0, help="segundos entre lecturas (5)")
    parser.add_argument("--ciclos", type=int, default=None, help="número de lecturas por sensor (sin fin)")
    parser.add_argument("--semilla", type=int, default=None, help="para repetir exactamente la misma simulación")
    parser.add_argument("--sin-excursiones", action="store_true", help="solo valores normales, sin avisos")
    parser.add_argument("--destino", choices=("api", "bd"), default="api",
                        help="api: lecturas firmadas al servidor de la aplicación (por defecto); "
                             "bd: directo a la base de datos, sin firma")
    parser.add_argument("--url", default=None, help="dirección del servidor (por defecto, la de la aplicación abierta)")
    args = parser.parse_args()

    migrate.preparar()
    try:
        if args.destino == "bd":
            destino = DestinoBaseDeDatos(config.RUTA_BD)
        else:
            destino = DestinoApi(config.RUTA_BD, buscar_servidor(args.url), claves.clave_ingesta())
    except ErrorDestino as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    sensores = destino.sensores()
    print(f"Simulando {len(sensores)} sensores cada {args.intervalo:g} s ({'firmado' if args.destino == 'api' else 'directo a la base de datos'}). "
          f"Ctrl+C para parar.")
    try:
        hechos = ejecutar(destino, sensores, args.intervalo, args.ciclos, args.semilla,
                          not args.sin_excursiones)
    except ErrorDestino as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    finally:
        destino.cerrar()
    print(f"Hecho: {hechos} ciclos de lecturas.")


if __name__ == "__main__":
    main()
