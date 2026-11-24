"""T11 · Códigos de 6 dígitos (TOTP, RFC 6238) y código QR."""
import base64

import pytest

from servidor import qr, totp

# Vectores oficiales de HOTP (RFC 4226, apéndice D): secreto «12345678901234567890» y contadores 0 a 9.
SECRETO_RFC = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
VECTORES = ["755224", "287082", "359152", "969429", "338314", "254676", "287922", "162583", "399871", "520489"]


@pytest.mark.parametrize("contador, esperado", list(enumerate(VECTORES)))
def test_los_codigos_coinciden_con_los_vectores_del_rfc(contador, esperado):
    assert totp.codigo(SECRETO_RFC, contador) == esperado


def test_el_codigo_cambia_cada_30_segundos():
    assert totp.paso_actual(59) == 1 and totp.paso_actual(60) == 2
    assert totp.segundos_restantes(60) == 30 and totp.segundos_restantes(89) == 1


def test_el_secreto_nuevo_es_base32_de_20_bytes_y_distinto_cada_vez():
    a, b = totp.nuevo_secreto(), totp.nuevo_secreto()
    assert a != b and len(a) == 32
    assert len(base64.b32decode(a)) == 20


def test_un_codigo_correcto_se_acepta_y_devuelve_su_paso():
    ahora = 30 * 100 + 5
    assert totp.verificar(SECRETO_RFC, totp.codigo(SECRETO_RFC, 100), ahora=ahora) == 100


def test_se_acepta_el_codigo_anterior_y_el_siguiente_pero_no_otros():
    ahora = 30 * 100 + 5
    for paso, valido in ((98, False), (99, True), (100, True), (101, True), (102, False)):
        assert (totp.verificar(SECRETO_RFC, totp.codigo(SECRETO_RFC, paso), ahora=ahora) is not None) is valido


def test_el_mismo_codigo_no_vale_dos_veces():
    ahora = 30 * 100 + 5
    codigo = totp.codigo(SECRETO_RFC, 100)
    assert totp.verificar(SECRETO_RFC, codigo, ultimo_paso=99, ahora=ahora) == 100
    assert totp.verificar(SECRETO_RFC, codigo, ultimo_paso=100, ahora=ahora) is None


@pytest.mark.parametrize("texto", ["", "12345", "1234567", "abcdef", "12 34 5", "12.456", None])
def test_lo_que_no_son_seis_digitos_se_rechaza(texto):
    assert totp.verificar(SECRETO_RFC, texto, ahora=100) is None


def test_se_ignoran_los_espacios_del_codigo():
    ahora = 30 * 100
    codigo = totp.codigo(SECRETO_RFC, 100)
    assert totp.verificar(SECRETO_RFC, codigo[:3] + " " + codigo[3:], ahora=ahora) == 100


def test_el_enlace_del_qr_lleva_secreto_emisor_y_correo():
    enlace = totp.uri("ABCDEFGHIJKLMNOP", "laura.mendez@cn-valdecierzo.es")
    assert enlace.startswith("otpauth://totp/AUREA%20Sentinel:laura.mendez%40cn-valdecierzo.es?")
    assert "secret=ABCDEFGHIJKLMNOP" in enlace and "digits=6" in enlace and "period=30" in enlace


def test_el_qr_es_un_svg_valido_y_distinto_para_cada_texto():
    a, b = qr.svg("otpauth://totp/uno"), qr.svg("otpauth://totp/dos")
    assert a.startswith("<svg") and a.endswith("</svg>") and 'xmlns="http://www.w3.org/2000/svg"' in a
    assert a != b
