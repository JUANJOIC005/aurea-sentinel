"""Comunicación con el servidor. El cliente nunca habla con la base de datos."""
import os

import httpx

URL_POR_DEFECTO = "http://127.0.0.1:8000"


class ErrorApi(Exception):
    """El servidor ha contestado con un error (credenciales malas, datos inválidos…)."""

    def __init__(self, estado: int, mensaje: str):
        super().__init__(mensaje)
        self.estado = estado
        self.mensaje = mensaje


class ErrorConexion(Exception):
    """No se ha podido hablar con el servidor."""


class ClienteApi:
    def __init__(self, url: str | None = None, http: httpx.Client | None = None):
        self.url = (url or os.environ.get("AUREA_API_URL", URL_POR_DEFECTO)).rstrip("/")
        self._http = http or httpx.Client(base_url=self.url, timeout=5.0)
        self._token: str | None = None

    @property
    def servidor(self) -> str:
        """host:puerto, para enseñarlo en la barra de estado."""
        return self.url.split("://", 1)[-1]

    def usar_token(self, token: str | None) -> None:
        self._token = token

    def _llamar(self, metodo: str, ruta: str, **kwargs):
        cabeceras = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            respuesta = self._http.request(metodo, ruta, headers=cabeceras, **kwargs)
        except httpx.HTTPError as error:
            raise ErrorConexion(str(error)) from error
        if respuesta.status_code >= 400:
            try:
                mensaje = respuesta.json().get("detalle", "Error del servidor.")
            except ValueError:
                mensaje = "Error del servidor."
            raise ErrorApi(respuesta.status_code, mensaje)
        return respuesta.json() if respuesta.content else None

    # ── Acceso ──
    def login(self, correo: str, password: str) -> dict:
        return self._llamar("POST", "/auth/login", json={"correo": correo, "password": password})

    def registro(self, datos: dict) -> dict:
        return self._llamar("POST", "/auth/registro", json=datos)

    def yo(self) -> dict:
        return self._llamar("GET", "/auth/yo")

    def logout(self) -> None:
        self._llamar("POST", "/auth/logout")

    # ── Datos públicos para el formulario de registro ──
    def areas(self) -> list[dict]:
        return self._llamar("GET", "/publico/areas")

    def supervisores(self, area: str) -> list[dict]:
        return self._llamar("GET", "/publico/supervisores", params={"area": area})

    def salud(self) -> bool:
        try:
            self._llamar("GET", "/salud")
            return True
        except (ErrorApi, ErrorConexion):
            return False
