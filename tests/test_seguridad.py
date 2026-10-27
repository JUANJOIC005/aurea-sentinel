from servidor import seguridad


def test_hash_argon2id_y_verificacion():
    h = seguridad.hashear("una-contraseña-larga")
    assert h.startswith("$argon2id$")
    assert seguridad.verificar(h, "una-contraseña-larga")
    assert not seguridad.verificar(h, "otra-contraseña-larga")


def test_hash_corrupto_no_verifica_ni_rompe():
    assert not seguridad.verificar("esto-no-es-un-hash", "x")


def test_mismo_texto_dos_hashes_distintos():
    assert seguridad.hashear("abcdefghijkl1") != seguridad.hashear("abcdefghijkl1")


def test_tokens_unicos_y_hash_estable():
    a, b = seguridad.nuevo_token(), seguridad.nuevo_token()
    assert a != b and len(a) >= 40
    assert seguridad.hash_token(a) == seguridad.hash_token(a) != seguridad.hash_token(b)


def test_politica_de_contrasenas():
    assert seguridad.comprobar_politica("Valdecierzo-2026-ok!") == []
    assert seguridad.comprobar_politica("corta")
    assert seguridad.comprobar_politica("Administrador1")          # lista de filtradas (sin distinguir mayúsculas)
    assert seguridad.comprobar_politica("aaaaaaaaaaaaaaaa")


def test_verificar_ficticio_no_falla():
    seguridad.verificar_ficticio("lo-que-sea")
