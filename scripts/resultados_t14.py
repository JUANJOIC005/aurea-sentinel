"""Pasa las pruebas de T14 (40 intentos de ver datos de otra área y 30 de colar lecturas falsas) y anota el resultado
de cada caso en un archivo markdown, con la fecha y la hora reales de la ejecución.

    python3 scripts/resultados_t14.py [salida.md]        # por defecto: Resultados T14.md

No inventa nada: cada fila sale de lo que ha hecho `pytest` en este momento. Si un caso falla, aparece como FALLA.
"""
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARCHIVOS = ["tests/test_permisos_por_area.py", "tests/test_lecturas_falsas.py"]


def humanizar(nombre: str) -> str:
    """test_f03_valor_alterado_despues_de_firmar → «Valor alterado despues de firmar»."""
    texto = re.sub(r"^test_f\d+_", "", nombre).replace("_", " ")
    return texto[:1].upper() + texto[1:]


def ejecutar() -> dict[str, str]:
    """Devuelve {nombre_de_la_prueba: 'pasa'|'FALLA'} según el informe de pytest."""
    with tempfile.TemporaryDirectory() as carpeta:
        informe = Path(carpeta) / "informe.xml"
        subprocess.run([sys.executable, "-m", "pytest", *ARCHIVOS, "-o", "addopts=", "-q", "-p", "no:cacheprovider",
                        f"--junitxml={informe}"], cwd=RAIZ, capture_output=True, text=True)
        resultados = {}
        for caso in ET.parse(informe).getroot().iter("testcase"):
            malo = caso.find("failure") is not None or caso.find("error") is not None
            resultados[caso.get("name")] = "FALLA" if malo else "pasa"
    return resultados


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "sin git"


def main() -> None:
    from tests import test_permisos_por_area as permisos
    resultados = ejecutar()
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Resultados T14.md")
    ahora = datetime.now().astimezone()

    filas_p = []
    for c in permisos.CASOS:
        estado = resultados.get(f"test_caso[{c.id}]", "sin resultado")
        esperado = {200: "200 · lo recibe", 401: "401 · sin sesión", 403: "403 · prohibido",
                    422: "422 · petición no válida"}.get(c.esperado, str(c.esperado))
        filas_p.append(f"| {c.id} | {c.texto} | `{c.ruta}` | {esperado} | {estado} |")

    nombres_f = sorted(n for n in resultados if re.match(r"test_f\d\d_", n))
    filas_f = [f"| F{n[6:8]} | {humanizar(n)} | {resultados[n]} |" for n in nombres_f]

    malos_p = sum(1 for c in permisos.CASOS if resultados.get(f"test_caso[{c.id}]") != "pasa")
    malos_f = sum(1 for n in nombres_f if resultados[n] != "pasa")
    extra = {n: e for n, e in resultados.items()
             if not n.startswith("test_caso[") and not re.match(r"test_f\d\d_", n)}
    malos_extra = sum(1 for e in extra.values() if e != "pasa")

    texto = f"""# Resultados de T14 · Pruebas de permisos y de lecturas falsas

Ejecución del {ahora:%d/%m/%Y} a las {ahora:%H:%M} (versión `{commit()}`). Archivos: `tests/test_permisos_por_area.py` y `tests/test_lecturas_falsas.py`.

| | Casos | Pasan | Fallan |
|---|---|---|---|
| Intentos de ver datos de otra área o de otro rol (P01 a P40) | {len(filas_p)} | {len(filas_p) - malos_p} | {malos_p} |
| Intentos de colar lecturas falsas (F01 a F30) | {len(filas_f)} | {len(filas_f) - malos_f} | {malos_f} |
| Comprobaciones generales (recuento, mensajes sin datos, auditoría) | {len(extra)} | {len(extra) - malos_extra} | {malos_extra} |

«Pasa» significa que el servidor respondió **lo que la tabla de permisos (T09, apartado 6.2 de la documentación) exige**. Los intentos prohibidos devuelven siempre el mismo 403, sin enseñar ningún dato, y cada uno queda anotado como `acceso_denegado` en el registro de auditoría.

## Permisos: quién pregunta, qué pide y qué debe contestar el servidor

| Caso | Intento | Petición | Debe responder | Resultado |
|---|---|---|---|---|
{chr(10).join(filas_p)}

## Lecturas falsas: todo lo que debe rechazarse

En todos los casos, el servidor responde 401 (la firma no vale) o 422 (los datos no valen), **no guarda nada** y, si lo que falla son los datos, deja anotado el rechazo en la auditoría. Salvo F22 y F27, que comprueban que lo repetido no se pisa y que en un envío mezclado solo se guarda lo válido.

| Caso | Intento | Resultado |
|---|---|---|
{chr(10).join(filas_f)}

## Comprobaciones generales

| Prueba | Resultado |
|---|---|
{chr(10).join(f"| {n} | {e} |" for n, e in sorted(extra.items()))}
"""
    salida.write_text(texto, encoding="utf-8", newline="\n")
    print(f"{salida}: {len(filas_p)} casos de permisos ({malos_p} fallan) y {len(filas_f)} de lecturas falsas ({malos_f} fallan)")


if __name__ == "__main__":
    main()
