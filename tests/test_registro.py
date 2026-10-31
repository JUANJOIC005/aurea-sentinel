from servidor.api.auth import MENSAJE_REGISTRO
from tests.conftest import CLAVE

NUEVA = {"nombre": "Marcos Gil Arroyo", "correo": "marcos.gil@cn-valdecierzo.es", "password": CLAVE,
         "rol": "auditor"}


def registrar(api, **cambios):
    return api.post("/auth/registro", json={**NUEVA, **cambios})


def test_registro_correcto_deja_la_cuenta_pendiente(api, conexion):
    r = registrar(api)
    assert r.status_code == 201 and r.json()["mensaje"] == MENSAJE_REGISTRO
    fila = conexion.execute("SELECT estado, password_hash FROM usuario").fetchone()
    assert fila["estado"] == "pendiente"
    assert fila["password_hash"].startswith("$argon2id$") and CLAVE not in fila["password_hash"]


def test_una_cuenta_pendiente_no_puede_entrar(api):
    registrar(api)
    assert api.post("/auth/login", json={"correo": NUEVA["correo"], "password": CLAVE}).status_code == 401


def test_un_supervisor_registrado_necesita_area(api):
    assert registrar(api, rol="supervisor").status_code == 422
    assert registrar(api, rol="supervisor", area="A3").status_code == 201


def test_un_tecnico_necesita_supervisor(api, crear_usuario, conexion):
    sup = crear_usuario()
    assert registrar(api, rol="tecnico").status_code == 422
    assert registrar(api, rol="tecnico", supervisor_id=9999).status_code == 422
    assert registrar(api, rol="tecnico", supervisor_id=sup).status_code == 201
    fila = conexion.execute("SELECT a.codigo, u.supervisor_id FROM usuario u JOIN area a ON a.id = u.area_id"
                            " WHERE u.correo = ?", (NUEVA["correo"],)).fetchone()
    assert fila["codigo"] == "A1" and fila["supervisor_id"] == sup


def test_el_supervisor_de_un_tecnico_debe_estar_activo(api, crear_usuario):
    pendiente = crear_usuario(estado="pendiente")
    assert registrar(api, rol="tecnico", supervisor_id=pendiente).status_code == 422


def test_no_se_puede_pedir_ser_administrador(api):
    assert registrar(api, rol="administrador").status_code == 422


def test_contrasenas_debiles_rechazadas(api, conexion):
    assert "12 caracteres" in registrar(api, password="corta").json()["detalle"]
    assert "filtradas" in registrar(api, password="administrador1").json()["detalle"]
    assert "repetidos" in registrar(api, password="aaaaaaaaaaaaaa").json()["detalle"]
    assert conexion.execute("SELECT count(*) AS n FROM usuario").fetchone()["n"] == 0


def test_datos_invalidos_rechazados(api):
    assert registrar(api, correo="sin-arroba").status_code == 422
    assert registrar(api, nombre="ab").status_code == 422
    assert registrar(api, area="Z9", rol="supervisor").status_code == 422


def test_un_correo_repetido_recibe_la_misma_respuesta_y_no_crea_otra_cuenta(api, conexion):
    primera = registrar(api)
    segunda = registrar(api, nombre="Otra Persona")
    assert primera.status_code == segunda.status_code == 201
    assert primera.json() == segunda.json()
    assert conexion.execute("SELECT count(*) AS n FROM usuario").fetchone()["n"] == 1


def test_el_registro_queda_en_la_auditoria(api, conexion):
    registrar(api)
    registrar(api)
    acciones = [e["accion"] for e in conexion.execute("SELECT accion FROM evento_auditoria ORDER BY id")]
    assert acciones == ["registro_solicitado", "registro_duplicado"]


def test_datos_publicos_del_formulario(api, crear_usuario):
    crear_usuario()
    crear_usuario(nombre="Pendiente Pérez", correo="p@cn.es", estado="pendiente")
    crear_usuario(nombre="Javier Ruiz Pastor", correo="javier@cn.es", area="A2")
    areas = api.get("/publico/areas").json()
    assert len(areas) == 9 and areas[0] == {"codigo": "A1", "nombre": "Reactor y circuito primario"}
    nombres = [s["nombre"] for s in api.get("/publico/supervisores", params={"area": "A1"}).json()]
    assert nombres == ["Laura Méndez Ortiz"]
    assert api.get("/publico/supervisores", params={"area": "X1"}).status_code == 422


def test_salud(api):
    assert api.get("/salud").json() == {"estado": "ok"}
