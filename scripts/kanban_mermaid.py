"""Tablero Kanban del Sprint 1 como diagrama Mermaid (para el .md), leído de GitHub Projects.

    python3 scripts/kanban_mermaid.py [AAAA-MM-DDTHH:MM:SSZ] > kanban.md

Con la fecha (UTC) reconstruye el tablero en ese momento a partir del historial de GitHub.
"""
import sys

from kanban_captura import COLUMNAS, REPO_NOMBRE, REPO_PROPIETARIO, leer_tablero


def mermaid(tablero: dict) -> str:
    url = f"https://github.com/{REPO_PROPIETARIO}/{REPO_NOMBRE}/issues/#TICKET#"
    gris = [f"    cScale{k}: '#C3CCD6'" for k in range(12)] + [f"    cScaleLabel{k}: '#1F2933'" for k in range(12)]
    lineas = ["```mermaid", "---", "config:", "  theme: base", "  themeVariables:", "    fontFamily: 'Noto Sans'",
              "    primaryBorderColor: '#CBD2D9'", "    lineColor: '#CBD2D9'", "    mainBkg: '#FFFFFF'", "    textColor: '#1F2933'",
              "    nodeBorder: '#CBD2D9'", *gris, "  kanban:", f"    ticketBaseUrl: '{url}'", "---", "kanban"]
    prioridad = {"Imprescindible": "Very High", "Importante": "High", "Interesante": "Low"}
    for columna in COLUMNAS:
        lineas.append(f"  {columna}")
        for codigo, titulo, responsable, p, horas in tablero[columna]:
            lineas.append(f"    id{codigo}[\"{codigo} {titulo} · {horas} h\"]@{{ ticket: {int(codigo[1:])}, "
                          f"assigned: '{responsable}', priority: '{prioridad.get(p, 'Low')}' }}")
    lineas.append("```")
    return "\n".join(lineas)


if __name__ == "__main__":
    print(mermaid(leer_tablero(sys.argv[1] if len(sys.argv) > 1 else None)))
