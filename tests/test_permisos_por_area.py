"""T14 · Intentos de ver datos de otra área o de otro rol: 40 casos numerados (P01 a P40).

Cada caso dice quién pregunta, qué pide y qué debe contestar el servidor. Los intentos prohibidos deben dar 403 sin
enseñar ningún dato, y quedar anotados en el registro de auditoría.
"""
from dataclasses import dataclass
from typing import Callable

import pytest

from tests.conftest import CORREOS

OTRAS_AREAS = ["PT-201", "ST-301", "PT-401", "TE-501", "TE-601", "ET-701", "RT-801", "NT-901"]   # un sensor de A2 a A9


@dataclass(frozen=True)
class Caso:
    id: str
    texto: str
    actor: str | None           # nombre en la fixture `central`, o None si no hay sesión
    ruta: str
    esperado: int
    comprueba: Callable | None = None
    cabecera: str | None = None  # para probar sesiones falsas


def etiquetas(r):
    return [s["tag"] for s in r.json()["sensores"]]


def ids(prefijo):
    return iter(f"{prefijo}{i:02d}" for i in range(1, 100))


_id = ids("P")
CASOS: list[Caso] = []


def caso(*args, **kwargs):
    CASOS.append(Caso(next(_id), *args, **kwargs))


# ── Un supervisor intenta ver otra área (P01 a P16) ──
for etiqueta in OTRAS_AREAS:
    caso(f"Laura (A1) pide el histórico de {etiqueta}, de otra área", "laura", f"/lecturas/historico?tag={etiqueta}", 403)
for etiqueta in OTRAS_AREAS:
    caso(f"Laura (A1) intenta exportar a CSV el histórico de {etiqueta}", "laura",
         f"/lecturas/historico/csv?tag={etiqueta}", 403)

# ── Lo que sí ve cada supervisor (P17 y P18) ──
caso("Laura (A1) pide las lecturas en directo: solo llegan sensores de A1", "laura", "/lecturas/ultimas", 200,
     lambda r, c: etiquetas(r) == ["TE-101", "PT-102", "FT-103", "LT-104"]
     and {s["area"]["codigo"] for s in r.json()["sensores"]} == {"A1"})
caso("Javier (A2) pide las lecturas en directo: solo llegan sensores de A2", "javier", "/lecturas/ultimas", 200,
     lambda r, c: etiquetas(r) == ["PT-201", "LT-202", "TE-203", "FT-204"])

# ── Un técnico intenta salirse de sus sensores (P19 a P26) ──
caso("Diego pide el histórico de FT-103: es de su área pero de Nuria", "diego", "/lecturas/historico?tag=FT-103", 403)
caso("Diego pide el histórico de LT-104: es de su área pero de Nuria", "diego", "/lecturas/historico?tag=LT-104", 403)
caso("Diego pide el histórico de PT-201, de otra área", "diego", "/lecturas/historico?tag=PT-201", 403)
caso("Diego pide el histórico de NT-901, de la red OT", "diego", "/lecturas/historico?tag=NT-901", 403)
caso("Diego intenta exportar CSV de TE-101, que sí es suyo: los técnicos no exportan", "diego",
     "/lecturas/historico/csv?tag=TE-101", 403)
caso("Diego intenta ver el equipo de su supervisor", "diego", "/equipo", 403)
caso("Diego intenta ver el inventario de sensores", "diego", "/sensores", 403)
caso("Diego pide las lecturas en directo: solo sus 2 sensores", "diego", "/lecturas/ultimas", 200,
     lambda r, c: etiquetas(r) == ["TE-101", "PT-102"])

# ── Límite de 7 días del técnico (P27 y P28) ──
caso("Diego pide 8 días de histórico de TE-101: el máximo del técnico son 7", "diego",
     "/lecturas/historico?tag=TE-101&horas=192", 422)
caso("Diego pide 7 días de histórico de TE-101", "diego", "/lecturas/historico?tag=TE-101&horas=168", 200)

# ── El auditor solo ve agregados (P29 a P33) ──
caso("Beatriz (auditora) pide las lecturas en directo: solo agregados por área, sin valores", "beatriz",
     "/lecturas/ultimas", 200,
     lambda r, c: r.json()["agregado"] is True and '"valor"' not in r.text and '"tag"' not in r.text)
caso("Beatriz intenta exportar CSV del histórico", "beatriz", "/lecturas/historico/csv?tag=TE-101", 403)
caso("Beatriz intenta ver el equipo de un supervisor", "beatriz", "/equipo", 403)
caso("Beatriz intenta ver las alarmas (el auditor las ve solo en informes)", "beatriz", "/alarmas", 403)
caso("Beatriz pide el histórico de PT-201: lo recibe agregado", "beatriz", "/lecturas/historico?tag=PT-201", 200,
     lambda r, c: r.json()["agregado"] is True)

# ── El administrador no ve datos de sensores (P34 a P37) ──
caso("Álvaro (administrador) pide las lecturas en directo", "alvaro", "/lecturas/ultimas", 403)
caso("Álvaro pide el histórico de TE-101", "alvaro", "/lecturas/historico?tag=TE-101", 403)
caso("Álvaro pide las alarmas", "alvaro", "/alarmas", 403)
caso("Álvaro pide el equipo de un supervisor", "alvaro", "/equipo", 403)

# ── Sin sesión o con sesión falsa (P38 y P39) ──
caso("Sin ninguna sesión se piden las lecturas en directo", None, "/lecturas/ultimas", 401)
caso("Con un token inventado se pide un histórico", None, "/lecturas/historico?tag=TE-101", 401,
     cabecera="Bearer token-inventado-que-no-existe")

# ── Un supervisor ve solo a su equipo (P40) ──
caso("Javier (A2) pide su equipo: aparece Iván y no los técnicos de Laura", "javier", "/equipo", 200,
     lambda r, c: [t["nombre"] for t in r.json()["tecnicos"]] == ["Iván Cano Rubio"]
     and "Diego" not in r.text and "Nuria" not in r.text)


def pedir(api, entrar, c: Caso):
    cabecera = {"Authorization": c.cabecera} if c.cabecera else {}
    if c.actor:
        token, _ = entrar(CORREOS[c.actor])
        cabecera = {"Authorization": f"Bearer {token}"}
    return api.get(c.ruta, headers=cabecera)


def test_hay_exactamente_40_casos_con_su_numero():
    assert len(CASOS) == 40
    assert [c.id for c in CASOS] == [f"P{i:02d}" for i in range(1, 41)]


@pytest.mark.parametrize("c", CASOS, ids=[c.id for c in CASOS])
def test_caso(api, central, entrar, c):
    r = pedir(api, entrar, c)
    assert r.status_code == c.esperado, f"{c.id} · {c.texto}: {r.status_code} {r.text[:150]}"
    if c.comprueba:
        assert c.comprueba(r, central), f"{c.id} · {c.texto}: {r.text[:200]}"


def test_las_respuestas_prohibidas_no_enseñan_ningun_dato(api, central, entrar):
    prohibidos = [c for c in CASOS if c.esperado == 403]
    assert len(prohibidos) == 30
    for c in prohibidos:
        r = pedir(api, entrar, c)
        assert r.json() == {"detalle": "No tienes permiso para esta operación."}, c.id
        assert "valor" not in r.text and "PT-" not in r.text and "TE-" not in r.text, c.id


def test_cada_intento_prohibido_queda_en_el_registro_de_auditoria(api, central, entrar, conexion):
    prohibidos = [c for c in CASOS if c.esperado == 403]
    for c in prohibidos:
        pedir(api, entrar, c)
    filas = conexion.execute("SELECT actor_id, recurso FROM evento_auditoria WHERE accion = 'acceso_denegado'"
                             ).fetchall()
    assert len(filas) == len(prohibidos)
    assert {f["actor_id"] for f in filas} == {central[n] for n in ("laura", "diego", "beatriz", "alvaro")}
    # Los intentos de exportar que se denegaron no cuentan como exportaciones.
    assert conexion.execute("SELECT count(*) AS n FROM evento_auditoria WHERE accion = 'exportacion_csv'"
                            ).fetchone()["n"] == 0
