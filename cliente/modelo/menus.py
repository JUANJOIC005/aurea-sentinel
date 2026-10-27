"""Qué secciones ve cada rol en el menú lateral y en qué sprint se construye cada ventana."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Seccion:
    clave: str
    texto: str
    icono: str
    grupo: str
    ventana: str     # nº de ventana en los mockups
    sprint: str      # cuándo se construye (tarea del backlog)


MENUS: dict[str, list[Seccion]] = {
    "supervisor": [
        Seccion("panel", "Panel del área", "panel", "OPERACIÓN", "04", "Sprint 2 · T13"),
        Seccion("historico", "Histórico de sensores", "grafica", "OPERACIÓN", "05", "Sprint 2 · T13"),
        Seccion("equipo", "Equipo y tareas", "equipo", "OPERACIÓN", "06", "Sprint 3 · T17"),
        Seccion("alarmas", "Alarmas", "campana", "OPERACIÓN", "04", "Sprint 3 · T15"),
        Seccion("informes", "Informes del área", "informe", "INFORMES", "05", "Sprint 4"),
    ],
    "tecnico": [
        Seccion("turno", "Mi turno", "panel", "OPERACIÓN", "07", "Sprint 3 · T17"),
        Seccion("sensores", "Mis sensores", "sensor", "OPERACIÓN", "07", "Sprint 3 · T17"),
        Seccion("incidencias", "Incidencias", "informe", "OPERACIÓN", "08", "Sprint 3 · T17"),
    ],
    "auditor": [
        Seccion("cumplimiento", "Cumplimiento", "escudo", "AUDITORÍA", "10", "Sprint 4 · T19"),
        Seccion("registro", "Registro de auditoría", "informe", "AUDITORÍA", "11", "Sprint 4 · T19"),
        Seccion("sensores", "Histórico de sensores", "grafica", "AUDITORÍA", "05", "Sprint 4 · T19"),
    ],
    "administrador": [
        Seccion("usuarios", "Usuarios y roles", "equipo", "ADMINISTRACIÓN", "12", "Sprint 4 · T19"),
        Seccion("sensores", "Sensores y umbrales", "sensor", "ADMINISTRACIÓN", "13", "Sprint 4 · T19"),
        Seccion("registro", "Mi actividad", "informe", "ADMINISTRACIÓN", "11", "Sprint 4 · T19"),
    ],
}
