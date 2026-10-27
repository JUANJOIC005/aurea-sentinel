"""Datos de la persona conectada. Viven solo en memoria: no se guardan en disco."""
from dataclasses import dataclass
from datetime import datetime, timezone

ROLES = {
    "supervisor": "Supervisor",
    "tecnico": "Técnico",
    "auditor": "Auditor",
    "administrador": "Administrador",
}


@dataclass(frozen=True)
class Area:
    codigo: str
    nombre: str


@dataclass(frozen=True)
class Usuario:
    id: int
    nombre: str
    correo: str
    rol: str                      # supervisor | tecnico | auditor | administrador
    area: Area | None = None
    supervisor: str | None = None  # nombre de su supervisor (solo técnicos)

    @property
    def rol_visible(self) -> str:
        return ROLES[self.rol]

    @property
    def iniciales(self) -> str:
        palabras = self.nombre.split()
        return "".join(p[0] for p in palabras[:2]).upper()

    @property
    def area_visible(self) -> str:
        return f"{self.area.codigo} · {self.area.nombre}" if self.area else "Todas las áreas"


@dataclass(frozen=True)
class Sesion:
    token: str
    usuario: Usuario
    expira_en: datetime

    def segundos_restantes(self, ahora: datetime | None = None) -> int:
        ahora = ahora or datetime.now(timezone.utc)
        return max(0, int((self.expira_en - ahora).total_seconds()))

    def minutos_restantes(self, ahora: datetime | None = None) -> int:
        """Minutos que faltan, redondeando hacia arriba (si quedan 30 s, «1 min»)."""
        return -(-self.segundos_restantes(ahora) // 60)

    @classmethod
    def desde_respuesta(cls, datos: dict) -> "Sesion":
        u = datos["usuario"]
        area = Area(u["area"]["codigo"], u["area"]["nombre"]) if u.get("area") else None
        supervisor = u["supervisor"]["nombre"] if u.get("supervisor") else None
        usuario = Usuario(u["id"], u["nombre"], u["correo"], u["rol"], area, supervisor)
        return cls(datos["token"], usuario, datetime.fromisoformat(datos["expira_en"]))
