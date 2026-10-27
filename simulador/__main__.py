"""Simulador de sensores de la central Valdecierzo.

    ./run.sh simulador                      # una lectura de los 36 sensores cada 5 s, hasta Ctrl+C
    ./run.sh simulador --ciclos 10 --intervalo 1
"""
import argparse
import random
import time
from datetime import datetime, timezone

from servidor import config, migrate

from .destinos import DestinoBaseDeDatos
from .modelo import Lectura, SensorSimulado


def generar(simulados: list[SensorSimulado], instante: datetime, dt: float,
            con_excursiones: bool = True) -> list[Lectura]:
    return [
        Lectura(s.sensor.id, s.sensor.tag, instante, s.siguiente(dt, con_excursiones))
        for s in simulados
    ]


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def ejecutar(destino, sensores, intervalo: float, ciclos: int | None, semilla: int | None,
             con_excursiones: bool = True, dormir=time.sleep, reloj=ahora_utc) -> int:
    """Genera lecturas y las manda al destino. Devuelve cuántos ciclos ha hecho."""
    azar = random.Random(semilla)
    simulados = [SensorSimulado(s, random.Random(azar.random())) for s in sensores]
    hechos = 0
    try:
        while ciclos is None or hechos < ciclos:
            instante = reloj()
            destino.enviar(generar(simulados, instante, intervalo, con_excursiones))
            hechos += 1
            if ciclos is None or hechos < ciclos:
                dormir(intervalo)
    except KeyboardInterrupt:
        pass
    return hechos


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de sensores de AUREA Sentinel")
    parser.add_argument("--intervalo", type=float, default=5.0, help="segundos entre lecturas (5)")
    parser.add_argument("--ciclos", type=int, default=None, help="número de lecturas por sensor (sin fin)")
    parser.add_argument("--semilla", type=int, default=None, help="para repetir exactamente la misma simulación")
    parser.add_argument("--sin-excursiones", action="store_true", help="solo valores normales, sin avisos")
    args = parser.parse_args()

    migrate.preparar()
    destino = DestinoBaseDeDatos(config.RUTA_BD)
    sensores = destino.sensores()
    print(f"Simulando {len(sensores)} sensores cada {args.intervalo:g} s. Ctrl+C para parar.")
    try:
        hechos = ejecutar(destino, sensores, args.intervalo, args.ciclos, args.semilla,
                          not args.sin_excursiones)
    finally:
        destino.cerrar()
    print(f"Hecho: {hechos} ciclos de lecturas.")


if __name__ == "__main__":
    main()
