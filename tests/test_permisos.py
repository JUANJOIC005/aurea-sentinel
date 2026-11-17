"""T11 · Permisos por rol (tabla de T09): cada ruta deja pasar solo a los roles que la tabla permite."""
import pytest

from servidor.api import permisos
from tests.conftest import CORREOS

ROLES = {"supervisor": "laura", "tecnico": "diego", "auditor": "beatriz", "administrador": "alvaro"}
RUTAS = [
    ("/lecturas/ultimas", "lecturas", "ver"),
    ("/lecturas/historico?tag=TE-101", "historico", "ver"),
    ("/lecturas/historico/csv?tag=TE-101", "historico", "exportar"),
    ("/alarmas", "alarmas", "ver"),
    ("/equipo", "equipo", "ver"),
    ("/sensores", "sensores", "ver"),
]


def cabecera(entrar, nombre):
    token, _ = entrar(CORREOS[nombre])
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("rol", list(ROLES))
@pytest.mark.parametrize("ruta, recurso, accion", RUTAS)
def test_cada_rol_solo_entra_donde_la_tabla_lo_permite(api, central, entrar, rol, ruta, recurso, accion):
    esperado = 200 if rol in permisos.PERMISOS[(recurso, accion)] else 403
    r = api.get(ruta, headers=cabecera(entrar, ROLES[rol]))
    assert r.status_code == esperado, f"{rol} → {ruta}: {r.status_code} {r.text[:120]}"
    if esperado == 403:
        assert r.json() == {"detalle": permisos.MENSAJE_PROHIBIDO}


@pytest.mark.parametrize("ruta, recurso, accion", RUTAS)
def test_sin_sesion_o_con_una_sesion_falsa_no_se_entra(api, central, ruta, recurso, accion):
    assert api.get(ruta).status_code == 401
    assert api.get(ruta, headers={"Authorization": "Bearer inventado"}).status_code == 401
    assert api.get(ruta, headers={"Authorization": "Basic abc"}).status_code == 401


def test_una_sesion_cerrada_ya_no_da_acceso(api, central, entrar):
    cab = cabecera(entrar, "laura")
    assert api.get("/lecturas/ultimas", headers=cab).status_code == 200
    api.post("/auth/logout", headers=cab)
    assert api.get("/lecturas/ultimas", headers=cab).status_code == 401


def test_una_cuenta_bloqueada_pierde_el_acceso_aunque_conserve_el_token(api, central, entrar, conexion):
    cab = cabecera(entrar, "laura")
    conexion.execute("UPDATE usuario SET estado = 'bloqueado' WHERE id = ?", (central["laura"],))
    conexion.commit()
    assert api.get("/lecturas/ultimas", headers=cab).status_code == 401


def test_cada_denegacion_queda_en_el_registro_con_quien_lo_intento(api, central, entrar, conexion):
    api.get("/equipo", headers=cabecera(entrar, "diego"))
    api.get("/sensores", headers=cabecera(entrar, "laura"))
    filas = conexion.execute("SELECT actor_id, recurso, resultado FROM evento_auditoria"
                             " WHERE accion = 'acceso_denegado' ORDER BY id").fetchall()
    assert [(f["actor_id"], f["recurso"], f["resultado"]) for f in filas] == [
        (central["diego"], "equipo:ver", "denegado"), (central["laura"], "sensores:ver", "denegado")]


def test_la_tabla_de_permisos_no_da_nada_al_rol_que_no_figura():
    for permitidos in permisos.PERMISOS.values():
        assert set(permitidos) <= set(ROLES)
    # Nadie salvo el Supervisor exporta CSV, y el Administrador no ve datos de sensores en directo ni histórico.
    assert set(permisos.PERMISOS[("historico", "exportar")]) == {"supervisor"}
    assert "administrador" not in permisos.PERMISOS[("lecturas", "ver")]
    assert "administrador" not in permisos.PERMISOS[("historico", "ver")]
