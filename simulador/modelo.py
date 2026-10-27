"""Modelo de un sensor simulado: valor nominal + deriva lenta + ruido + alguna excursión ocasional."""
import math
import random
from dataclasses import dataclass, field

TAU_DERIVA = 3600.0          # la deriva tarda ~1 h en "olvidar" su valor
FRACCION_DERIVA = 0.25       # desviación típica de la deriva, como fracción de la distancia al aviso
FRACCION_RUIDO = 0.03        # ídem para el ruido de cada lectura
EXCURSION_CADA_HORAS = 48.0  # una excursión por sensor cada ~2 días (de media)
EXCURSION_SUBIDA, EXCURSION_MANTENIDA, EXCURSION_BAJADA = 180.0, 240.0, 180.0  # segundos


@dataclass
class Sensor:
    """Datos del sensor tal y como están en la tabla `sensor`."""
    id: int
    tag: str
    valor_nominal: float
    min_fisico: float
    max_fisico: float
    aviso_bajo: float | None = None
    alarma_bajo: float | None = None
    aviso_alto: float | None = None
    alarma_alto: float | None = None

    @property
    def distancia_al_aviso(self) -> float:
        """Cuánto puede alejarse del valor nominal antes de llegar a un aviso."""
        candidatas = []
        if self.aviso_alto is not None:
            candidatas.append(self.aviso_alto - self.valor_nominal)
        if self.aviso_bajo is not None:
            candidatas.append(self.valor_nominal - self.aviso_bajo)
        candidatas = [c for c in candidatas if c > 0]
        return min(candidatas) if candidatas else 0.05 * (self.max_fisico - self.min_fisico)


@dataclass
class Lectura:
    sensor_id: int
    tag: str
    instante: object  # datetime
    valor: float


@dataclass
class SensorSimulado:
    sensor: Sensor
    azar: random.Random
    deriva: float = 0.0
    _excursion: dict | None = field(default=None, repr=False)

    @staticmethod
    def _forma_excursion(t: float) -> float:
        """Trapecio 0 → 1 → 0 según el segundo `t` de la excursión; -1 cuando ya ha terminado."""
        if t < EXCURSION_SUBIDA:
            return t / EXCURSION_SUBIDA
        if t < EXCURSION_SUBIDA + EXCURSION_MANTENIDA:
            return 1.0
        fin = EXCURSION_SUBIDA + EXCURSION_MANTENIDA + EXCURSION_BAJADA
        if t < fin:
            return (fin - t) / EXCURSION_BAJADA
        return -1.0

    def _empezar_excursion(self) -> None:
        """Elige un umbral (casi siempre el de aviso, a veces el de alarma) y lo rebasa un 8 %."""
        s = self.sensor
        saltos = []
        if s.aviso_alto is not None:
            umbral = s.alarma_alto if s.alarma_alto is not None and self.azar.random() < 0.3 else s.aviso_alto
            saltos.append(umbral - s.valor_nominal)
        if s.aviso_bajo is not None:
            umbral = s.alarma_bajo if s.alarma_bajo is not None and self.azar.random() < 0.3 else s.aviso_bajo
            saltos.append(umbral - s.valor_nominal)
        if saltos:
            self._excursion = {"objetivo": self.azar.choice(saltos) * 1.08, "t": 0.0}

    def siguiente(self, dt: float, con_excursiones: bool = True) -> float:
        """Avanza `dt` segundos y devuelve el nuevo valor."""
        s = self.sensor
        d = s.distancia_al_aviso
        # Deriva: proceso de Ornstein-Uhlenbeck (vuelve poco a poco al valor nominal)
        self.deriva += (-self.deriva / TAU_DERIVA) * dt \
            + FRACCION_DERIVA * d * math.sqrt(2 * dt / TAU_DERIVA) * self.azar.gauss(0, 1)
        valor = s.valor_nominal + self.deriva + self.azar.gauss(0, FRACCION_RUIDO * d)

        if con_excursiones:
            if self._excursion is None and self.azar.random() < dt / (EXCURSION_CADA_HORAS * 3600):
                self._empezar_excursion()
            if self._excursion is not None:
                self._excursion["t"] += dt
                forma = self._forma_excursion(self._excursion["t"])
                if forma < 0:
                    self._excursion = None
                else:
                    valor += self._excursion["objetivo"] * forma

        return round(min(max(valor, s.min_fisico), s.max_fisico), 4)
