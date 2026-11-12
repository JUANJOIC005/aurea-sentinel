# AUREA Sentinel · Documentación del Sprint 2

Qué se ha hecho, cómo se ha instalado, cómo se usa y qué falta. Está escrito para poder repetirlo en otro equipo. Recoge el Sprint 1 (la base) y el Sprint 2 (seguridad de acceso, lecturas firmadas, 30 días de datos y panel del Supervisor).

---

## 1. Estado del proyecto

**Sprint 1 · T01 a T10.** Hechas, probadas y fusionadas en `main` (PR #32, etiqueta `v0.1.0`): repositorio y ramas, esqueleto MVC, base de datos y migraciones, login con Argon2id, registro pendiente, simulador v1, ventana base, ventanas de login y registro, análisis de amenazas con tabla de permisos y pruebas de login.

**Sprint 2 · T11 a T14.** Hechas, probadas y fusionadas en `develop` el 12/11/2026: T11 (pull request #52), T12 (#53), T13 (#54) y T14 (#55).

| Tarea | Responsable | Qué es | Estado |
|---|---|---|---|
| T11 | Sergio | Permisos por rol y área + doble factor | Hecho. Código de 6 dígitos (TOTP) con QR para Supervisor, Auditor y Administrador; el servidor aplica la tabla de permisos de T09 en cada petición y anota lo denegado; 128 pruebas |
| T12 | Gonzalo | Lecturas firmadas y 30 días de datos | Hecho. API de ingesta con firma HMAC-SHA256, rechazo de firmas falsas, valores imposibles y fechas falsas, alarmas que se abren, escalan y cierran solas, y 30 días de histórico; 49 pruebas |
| T13 | Juan José | Doble factor, panel del Supervisor e histórico | Hecho. Ventana 03 (código y QR), ventana 04 (panel con tarjetas, indicadores, alarmas y equipo) y ventana 05 (histórico con gráfica, tabla y CSV); 91 pruebas |
| T14 | Itzel | Pruebas de permisos y de lecturas falsas | Hecho. 40 intentos de ver datos de otra área o de otro rol y 30 de colar lecturas falsas, con el resultado anotado en `docs/Resultados T14.md`; 74 pruebas |

**Pruebas:** 486 en verde (144 del Sprint 1 y 342 del Sprint 2).

**Lo que ya se ve en la aplicación:** acceso con segundo paso, panel en directo y histórico del **Supervisor**. El Técnico, el Auditor y el Administrador entran, pero sus ventanas propias llegan en los Sprints 3 y 4; mientras tanto el servidor ya les limita lo que pueden pedir.

**Pendiente del equipo:** firmar las actas, las horas reales del backlog y la autoevaluación por pares. No se pueden inventar: son del equipo.

---

## 2. Cómo se instala

AUREA Sentinel es una **aplicación totalmente local**: un único programa que funciona en el propio equipo, con su base de datos SQLite en un archivo. No usa servicios externos, ni la nube, ni conexión a internet, y no hay que instalar, contratar ni configurar ningún servidor. La parte que atiende las peticiones (`servidor/`) es un módulo interno del programa: solo responde al propio equipo (`127.0.0.1`) y se para al cerrar la aplicación.

**Para usarla (Windows):** descargar `AUREA Sentinel.exe` de la rama `production` del repositorio y abrirlo con doble clic. La primera vez crea su base de datos en `%APPDATA%\AUREA Sentinel\`, las 18 cuentas de demostración y **30 días de lecturas** de los 36 sensores (tarda unos 4 segundos y la base ocupa unos 33 MB). El `.exe` no está firmado digitalmente: Windows (SmartScreen o Defender) puede avisar la primera vez; hay que elegir «Más información → Ejecutar de todas formas». Lo construye GitHub Actions (`.github/workflows/exe.yml`) con Python 3.14. El `.exe` de `production` contiene el código del Sprint 1 hasta que se reconstruya con el del Sprint 2.

**Para desarrollar (Debian 13):** todo viene de `apt`, sin pip (Debian trae Python 3.13; el `.exe` se construye con 3.14, y el código funciona con ambas).

| Pieza | Paquete | Versión |
|---|---|---|
| Interfaz | `python3-pyside6.qtwidgets`, `python3-pyside6.qtsvg` | 6.8.2.1 |
| Módulo de datos interno | `python3-fastapi`, `python3-uvicorn` | 0.115.11 · 0.32.0 |
| Base de datos | `sqlite3` de Python (incluido) | 3.46 |
| Contraseñas | `python3-argon2` | 21.1.0 |
| Código QR del segundo factor | `python3-segno` | 1.6 o superior |
| Comunicación interna y pruebas | `python3-httpx`, `python3-pytest-cov` | 0.28.1 · 5.0.0 |
| Empaquetado (solo para el `.exe`) | `pyinstaller` (pip) | 6.x |

```
pkexec apt install -y python3-pyside6.qtwidgets python3-pyside6.qtsvg python3-fastapi \
  python3-uvicorn python3-argon2 python3-httpx python3-segno python3-pytest-cov
```

Con pip, en un entorno virtual: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

### Base de datos

Un único archivo SQLite: `~/.local/share/AUREA Sentinel/aurea sentinel.db` en Linux y `%APPDATA%\AUREA Sentinel\aurea sentinel.db` en Windows (se cambia con la variable `AUREA_BD`). Se crea y se actualiza sola al abrir la aplicación con las migraciones de `servidor/migrations/` (001 esquema, 002 catálogo, 003 segundo factor y sensores de cada técnico). Para empezar de cero basta con borrar el archivo.

### Cómo se construye el `.exe`

PyInstaller no genera ejecutables de Windows desde Linux, por eso lo hace GitHub Actions en un Windows de GitHub (a mano desde *Actions → Ejecutable de Windows → Run workflow*, o automáticamente al subir a `main`). En un Windows propio: `pip install -r requirements.txt pillow` y `pyinstaller aurea_sentinel.spec`; sale `dist/AUREA Sentinel.exe`. Antes de construir, GitHub Actions pasa las pruebas. Falta una prueba completa de uso del `.exe` del Sprint 2 en Windows.

---

## 3. Cómo se usa

**Abrir la aplicación.** Doble clic en `AUREA Sentinel.exe`. No hay nada que instalar ni configurar y no necesita internet ni red.

**Entrar.** En la pantalla de acceso se escribe el correo y la contraseña (el icono del ojo la muestra). «Equipo compartido» evita que se recuerde el correo. Si algo falla, el mensaje es siempre el mismo y tras 5 fallos seguidos la cuenta se bloquea 15 minutos.

**Segundo paso (Supervisor, Auditor y Administrador).** Tras acertar la contraseña aparece la ventana de verificación, con el nombre, el rol y el área de quien entra:
- **La primera vez** enseña un código QR (y la clave escrita en grupos de cuatro). Se escanea con una aplicación autenticadora del móvil (por ejemplo Google Authenticator, Microsoft Authenticator o Aegis), se escribe el primer código de 6 dígitos y se entra.
- **Los días siguientes** solo se escribe el código que enseña la aplicación. Se puede pegar entero.
- Hay 5 minutos para escribirlo y 3 intentos; con el tercer error se vuelve a pedir la contraseña. Un código ya usado no vale otra vez.
- El **Técnico** entra solo con la contraseña.

**Panel del Supervisor.** Al entrar, las tarjetas de los sensores de su área con valor, estado, tendencia y umbrales; cuatro indicadores; las alarmas (activas, de hoy o de 7 días) y su equipo de técnicos. Se actualiza solo cada 5 segundos. Pulsar una tarjeta abre el histórico de ese sensor.

**Histórico.** Se elige sensor y periodo (24 horas, 7 días, 30 días o fechas propias) y se puede comparar con otro sensor de la misma unidad. Muestra mínimo, máximo y media, la gráfica con los umbrales y la tabla paginada. «Exportar CSV» guarda los datos en un archivo que abre Excel y queda anotado en el registro de auditoría.

**Sesión.** Caduca sola (15 minutos Supervisor y Auditor, 30 Técnico, 10 Administrador) y vuelve a la pantalla de acceso; también se cierra con «Cerrar sesión».

**Pedir una cuenta.** En la pantalla de acceso, «Registrarse»: la cuenta queda **pendiente**, sin poder entrar. La ventana del Administrador que las aprueba llega en el Sprint 4; mientras tanto se aprueba a mano con `sqlite3 "<archivo.db>" "UPDATE usuario SET estado='activo' WHERE correo='…'"`.

**Cuentas de demostración** (correo `nombre.apellido@cn-valdecierzo.es`, sin tildes; contraseña de todas: `Valdecierzo-2026!`):

| Rol | Ejemplo |
|---|---|
| Supervisor (9, uno por área) | `laura.mendez@cn-valdecierzo.es` |
| Técnico (6, dependen de un supervisor) | `diego.paredes@cn-valdecierzo.es` |
| Auditor (2) | `beatriz.lara@cn-valdecierzo.es` |
| Administrador (1) | `alvaro.campos@cn-valdecierzo.es` |

Cada técnico tiene asignados sensores de su área: los cuatro de su supervisor si es el único, dos y dos si hay dos. La contraseña de demostración es pública a propósito (la aplicación se entrega para que el profesor la abra sin preparar nada). Una instalación real no debe sembrar cuentas con una contraseña conocida.

**Generar lecturas de sensores.** Con la aplicación abierta: `AUREA Sentinel.exe --simulador` (acepta `--intervalo`, `--ciclos`, `--semilla` y `--sin-excursiones`). El simulador busca la aplicación en `servidor.json` (que ella escribe al abrirse y borra al cerrarse), firma cada envío y lo manda al servidor, que valida la firma, el rango físico y la fecha antes de guardar. Escribe una lectura de los 36 sensores cada 5 s. Dos lecturas del mismo sensor en el mismo segundo cuentan como repetidas, así que no tiene sentido un intervalo menor de 1 s. Con `--destino bd` escribe directamente en la base de datos, sin firma y sin necesitar la aplicación.

**Para desarrollar sin móvil.** `AUREA_DOBLE_FACTOR=no` desactiva el segundo factor y `AUREA_SIN_HISTORICO=1` evita cargar los 30 días. Por defecto, el segundo factor está **activado**. No se usan en la entrega.

---

## 4. Claves y secretos

**En el repositorio no hay ninguna clave ni contraseña.** Esto es lo que existe y dónde vive cada cosa:

| Qué | Dónde está | Notas |
|---|---|---|
| Acceso a la base de datos | Es un archivo local de la carpeta de datos del usuario; no hay usuario ni contraseña de base de datos | Lo protegen los permisos del sistema operativo sobre esa carpeta |
| Configuración | Variables de entorno o fichero `.env` | `.env` está en `.gitignore` y no se sube. La plantilla es `.env.example` (sin valores secretos) |
| Contraseña de las cuentas de demo | `Valdecierzo-2026!` (constante `PASSWORD_DEMO`), o la variable `AUREA_DEMO_PASSWORD` si se define | Es una contraseña de demostración conocida, solo para las cuentas ficticias de la central; no protege ningún dato real |
| Contraseñas de usuarios | En la base de datos solo como hash **Argon2id** | No se pueden recuperar, solo restablecer |
| Tokens de sesión | El cliente guarda el token **solo en memoria**. La base guarda su hash SHA-256 | Caducan según el rol |
| Secreto del segundo factor | Tabla `segundo_factor` de la base de datos local | Hace falta en claro para calcular el código, así que lo protege el sistema operativo igual que el resto de la base. Es un límite conocido: en una instalación con varios equipos se guardaría cifrado |
| Desafío entre contraseña y código | Tabla `desafio_2fa`: solo el hash del token, 5 minutos, 3 intentos | Mismo tratamiento que las sesiones |
| Clave de firma de lecturas | Variable `AUREA_CLAVE_INGESTA` o, si no existe, un archivo `clave_ingesta.key` que se crea al azar junto a la base de datos | Nunca está en el repositorio. El servidor y el simulador son del mismo equipo y comparten la carpeta, así que no hay nada que copiar |
| Último correo usado | Ajustes locales de Qt (`~/.config/AUREA AUDIT/`) | Solo el correo, nunca la contraseña. Se omite con «Equipo compartido» |

Cifrado (TLS) solo haría falta si algún día los datos salen del equipo. Hoy todo es local: las ventanas y el módulo de datos están en el mismo programa y se hablan dentro del equipo (`127.0.0.1`, puerto libre elegido al arrancar), sin abrirse a la red.

---

## 5. Cómo está hecho

```
aurea-sentinel/
├── aurea_sentinel.py       punto de entrada del .exe (aplicación o --simulador)
├── aurea_sentinel.spec     receta de PyInstaller
├── requirements.txt · pytest.ini · .env.example   dependencias, configuración de las pruebas y plantilla de ajustes
├── servidor/               módulo de datos interno (el nombre de la carpeta es histórico)
│   ├── local.py            prepara la base de datos, carga el histórico, activa el módulo y anota su dirección
│   ├── db.py · migrate.py · config.py   conexión SQLite, migraciones y rutas
│   ├── api/                operaciones: login, segundo factor, registro, datos públicos, lecturas e histórico, alarmas,
│   │                       equipo, ingesta y permisos
│   ├── migrations/         001_esquema · 002_catalogo (áreas, roles, 36 sensores) · 003_segundo_factor
│   ├── seguridad.py        Argon2id, tokens, política de contraseñas
│   ├── totp.py · qr.py · doble_factor.py   códigos de 6 dígitos, código QR y desafío
│   ├── ingesta.py · claves.py   firma, validación de lecturas, alarmas y clave de firma
│   ├── historico.py · descubrimiento.py     30 días de lecturas y el archivo servidor.json
│   ├── usuarios.py · sesiones.py · auditoria.py   consultas a la base de datos
│   └── datos_demo.py       las 18 cuentas de demostración y el reparto de sensores a los técnicos
├── simulador/              modelo del sensor, destinos de las lecturas (base de datos o API firmada), línea de comandos
├── cliente/                ventanas de la aplicación de escritorio (PySide6)
│   ├── modelo/             sesión, comunicación con el módulo de datos, formato de cifras y fechas, menús por rol
│   ├── vista/              acceso, login, registro, verificación, panel, histórico, gráficas, tarjetas y estilos
│   └── controlador/        acceso (con segundo paso), sesión abierta, panel del Supervisor y arranque
├── scripts/                PDF de las actas, diagramas UML, capturas del Kanban, resultados de T14 y copia de este documento
├── equipo/                 ficha de cada miembro (tarea asignada y usuario de GitHub)
├── tests/                  486 pruebas
├── docs/                   resultados de las pruebas de T14
├── DOCUMENTACION.md        este documento
└── .github/                plantillas de issue y de pull request, y el flujo que construye el .exe
```

**MVC.** El *modelo* guarda los datos y habla con el módulo de datos, la *vista* son las ventanas y el *controlador* las conecta. Ninguna ventana toca la base de datos: todo pasa por ese módulo. Las gráficas se dibujan con `QPainter`, sin librerías nuevas.

**Login y segundo factor.** El módulo de datos responde siempre con el mismo mensaje (no revela si el correo existe, si la contraseña falló o si la cuenta está bloqueada) y tarda lo mismo en cada caso. Para Supervisor, Auditor y Administrador, acertar la contraseña no abre sesión: abre un *desafío* de 5 minutos. El código TOTP (RFC 6238, implementación propia con HMAC-SHA1, 30 s, 6 dígitos y tolerancia de un intervalo) se comprueba en `/auth/2fa/activar` (la primera vez) o `/auth/2fa/verificar`. Cada error cuenta también para el bloqueo de la cuenta. Todo queda en `evento_auditoria`.

**Permisos.** `servidor/api/permisos.py` contiene la tabla del apartado 6.2 como datos y una dependencia `requiere(recurso, acción)`. En cada petición se comprueba primero el rol, después el área o el vínculo, y solo entonces se consultan datos. Los ámbitos son: `area` (Supervisor), `asignados` (Técnico), `agregados` (Auditor) y `todo` (inventario). Lo que no está en la tabla está prohibido, y la respuesta es siempre el mismo 403 y un evento `acceso_denegado`.

**Ingesta firmada.** `POST /ingesta/lecturas` recibe hasta 500 lecturas con dos cabeceras: `X-Aurea-Marca` (la hora del envío, a ±300 s de la del servidor) y `X-Aurea-Firma` (`HMAC-SHA256(clave, marca + "." + cuerpo)`). Cada lectura se valida por separado: sensor conocido y activo, valor dentro del rango físico del sensor (y finito), fecha ni del futuro ni de hace más de 31 días. Se guarda lo válido y se anota lo rechazado. Una lectura repetida no pisa a la original. Al guardar se calcula el estado de cada sensor y se abre, escala o cierra su alarma.

**Datos de prueba.** `servidor/historico.py` genera 30 días de lecturas (una cada 5 minutos, unas 311.000 filas) con el mismo modelo que el simulador y una semilla fija, así que sale siempre igual.

**Registro.** La cuenta se guarda como «pendiente». Los técnicos eligen su supervisor y heredan su área (lo comprueba la propia base de datos). Si el correo ya existe, la respuesta es igual que si no existiera.

**Ventanas.** Copian los mockups: azul `#0B2D5B`, tarjetas blancas, menú lateral con pie de usuario, avatar con insignia de rol, barra de estado azul. Por debajo de 1366 px el menú queda de iconos (68 px) y se oculta el indicador de estado de la cabecera. Las secciones que aún no existen muestran un marcador que dice en qué sprint llegan.

**Diferencias con los mockups** (a propósito, para no mostrar cosas que no corresponden):
- La cabecera dice «Servidor conectado» en vez de «Datos en vivo». Los datos en vivo ya existen en el panel del Supervisor; el rótulo de la cabecera se cambia en un sprint posterior.
- El pie del menú no dice «MFA verificado»: la verificación ya existe, pero el pie todavía no lo muestra.
- La barra de estado no muestra «TLS 1.3»: todo es local y no sale del equipo.
- El indicador «Tareas abiertas del equipo» del panel enseña «—» hasta el Sprint 3 (T15), y el botón de asignar tarea queda a la espera.
- El logo es el oficial de AUREA AUDIT, sacado del PDF de imagen corporativa entregado en Canvas (`cliente/recursos/aurea_isotipo.png`, solo la «A»). Es una imagen de 590×475 px: se ve nítida en los paneles de acceso, pero convendría tener el original en vector.
- La fuente es Aptos si está instalada y, si no, Segoe UI o Noto Sans.
- El formulario de registro lista los supervisores del área antes de iniciar sesión, como en el mockup. Eso enseña nombres de personal a quien aún no se ha identificado; si el CTO lo considera un riesgo, se cambia por escribir el correo del supervisor.

---

## 6. T09 · Análisis de amenazas y tabla de permisos

### 6.1 Qué puede salir mal y qué hacemos

| Parte | Qué podría pasar | Qué hacemos | Estado |
|---|---|---|---|
| **Cliente** | Alguien roba la contraseña mirando la pantalla o con un programa que registra teclas | Contraseña oculta, con botón para verla; no se guarda en disco. Aun con la contraseña, hace falta el código del móvil | Hecho |
| | Alguien usa un equipo que otra persona dejó abierto | Sesión con caducidad por rol y botón «Cerrar sesión»; al caducar vuelve al login | Hecho |
| | Alguien manipula el cliente para ver otra área | El cliente solo esconde menús; **el módulo de datos decide** qué se devuelve (40 intentos probados en T14) | Hecho para lecturas, histórico, alarmas, equipo e inventario. Tareas e incidencias, en el Sprint 3 |
| **Módulo de datos** | Adivinar contraseñas probando muchas | Bloqueo de 15 min tras 5 fallos; contraseña mínima de 12 caracteres y lista de contraseñas filtradas | Hecho |
| | Descubrir qué correos existen | Mismo mensaje y mismo tiempo de respuesta con cualquier fallo; el registro responde igual si el correo ya existe | Hecho |
| | Robar un token de sesión | Token aleatorio de 256 bits, solo su hash en la base de datos, caducidad, se invalida al cerrar sesión o al bloquear la cuenta | Hecho |
| | Enviar datos mal formados o enormes | Validación de todos los campos con límites de longitud; las contraseñas largas se limitan a 256 caracteres; un envío de lecturas admite como máximo 500 | Hecho |
| | Espiar la comunicación entre las ventanas y el módulo de datos | Es interna del equipo (`127.0.0.1`), sin red; TLS solo si algún día sale | No aplica hoy |
| | Saltarse el segundo factor | Código de 6 dígitos obligatorio para Supervisor, Auditor y Administrador; el desafío caduca a los 5 minutos y se cierra con 3 errores; un código no vale dos veces | Hecho (Sprint 2, T11) |
| **Base de datos** | Que alguien con acceso edite o borre el rastro de lo que hizo | El registro de auditoría no admite `UPDATE` ni `DELETE` (lo impide la propia base) | Hecho. La cadena de hashes llega en el Sprint 3 (T16) |
| | Datos incoherentes (técnico sin supervisor, umbrales al revés, lecturas duplicadas, sensores de otra área asignados a un técnico) | Claves, restricciones y disparadores en las tablas | Hecho |
| | Robo de contraseñas si se filtra la base | Solo hashes Argon2id | Hecho |
| **Simulador** | Que alguien envíe lecturas falsas haciéndose pasar por él | Firma HMAC de cada envío con marca de tiempo, rango físico válido y fecha razonable; 30 intentos probados en T14 | Hecho (Sprint 2, T12) |

### 6.2 Qué puede hacer cada rol (implementado en el Sprint 2 hasta donde dice la última columna)

«Su área» = el área del supervisor. «Sus sensores» = los que le asigna su supervisor. Todo lo que no está aquí está prohibido.

| Recurso | Acción | Supervisor | Técnico | Auditor | Administrador | Estado |
|---|---|---|---|---|---|---|
| Lecturas en directo | Ver | Su área | Sus sensores | Solo agregados | — | Hecho (T11) |
| Histórico de sensores | Ver | 30 días, su área | 7 días, sus sensores | Agregados | — | Hecho (T11) |
| | Exportar CSV | Sí (queda en el registro) | — | — | — | Hecho (T11) |
| Alarmas | Ver | Su área | De sus sensores | Solo en informes | — | Hecho (T11) |
| | Reconocer | Sí | — | — | — | Sprint 3 |
| Tareas | Crear y asignar | A sus técnicos | — | — | — | Sprint 3 |
| | Ver | Las de su equipo | Las suyas | — | — | Sprint 3 |
| | Cambiar estado | — | Las suyas | — | — | Sprint 3 |
| Incidencias | Crear | — | Sobre sus sensores | — | — | Sprint 3 |
| | Ver | Las de su equipo | Las suyas | Solo lectura | — | Sprint 3 |
| Cuentas | Solicitar | Cualquiera, sin sesión | | | | Hecho (Sprint 1) |
| | Aprobar, bloquear, editar | — | — | — | Sí | Sprint 4 |
| Vínculos supervisor → técnico | Asignar | — | — | — | Sí | Sprint 4 (hoy los fija la demo) |
| Sensores y umbrales | Ver inventario | — | — | Solo lectura | Sí | Hecho (T11) |
| | Editar umbral | — | — | — | Sí, con motivo y segundo factor | Sprint 4 |
| Equipo | Ver técnicos del supervisor | Su equipo | — | — | — | Hecho (T11) |
| Registro de auditoría | Ver | — | — | Todo, con nombres ocultos | Solo sus propios eventos | Sprint 3 |
| | Verificar y exportar | — | — | Sí | — | Sprint 3 |

Regla general: en cada petición el módulo de datos comprueba **rol**, luego **área o vínculo**, y solo entonces consulta datos. Si algo no coincide responde «prohibido» y lo anota en el registro.

---

## 7. Pruebas

**486 pruebas en verde**, repetidas varias veces seguidas sin fallos intermitentes. La cobertura se medirá al cierre del proyecto (T20).

| Archivo | Pruebas | Qué comprueba |
|---|---|---|
| `test_bd.py` | 18 | 9 áreas, 4 roles, 36 sensores; claves y restricciones; el registro de auditoría no se edita |
| `test_auth.py` | 22 | Login correcto e incorrecto, mensaje idéntico con correo inexistente, bloqueo a los 5 intentos y fin del bloqueo, cuentas pendientes, caducidad por rol, cierre de sesión, token no guardado en claro |
| `test_registro.py` | 12 | Cuenta pendiente, reglas por rol, contraseñas débiles, correo repetido, datos públicos del formulario |
| `test_seguridad.py` | 6 | Argon2id, tokens, política de contraseñas |
| `test_simulador.py` | 15 | Rangos físicos, valores en torno al nominal, excursiones, repetibilidad con semilla, 36 sensores en la base |
| `test_datos_demo.py` | 6 | Las cuentas de demo cumplen lo que pide el enunciado (9 principales, 6 relacionados, alguno con varios) |
| `test_local.py` | 5 | El módulo interno, el puerto libre y la siembra de cuentas de la primera vez |
| `test_cliente_modelo.py` | 10 | Datos de sesión y comunicación con el módulo de datos real y con uno caído |
| `test_cliente_controlador.py` | 27 | Login, registro y caducidad, con un módulo de datos simulado; flujo completo de la aplicación |
| `test_vistas.py` | 23 | Nombre y rol visibles en las 4 vistas del Sprint 1, menú por rol, cambio de tamaño, tamaño mínimo 1024×640 |
| **T11** `test_totp.py` | 25 | Códigos con los vectores oficiales de la RFC 4226, ventana de tiempo, secretos y QR |
| `test_segundo_factor.py` | 25 | Desafío, primera configuración, código bueno y malo, reutilización, bloqueo, caducidad, auditoría |
| `test_permisos.py` | 34 | La tabla de permisos rol por rol y que lo denegado se anota |
| `test_datos_api.py` | 39 | Endpoints de datos, filtrado por área y técnico, CSV, límites de días |
| `test_asignacion_sensores.py` | 5 | Tabla de sensores por técnico, su disparador y el reparto de la demo |
| **T12** `test_ingesta.py` | 27 | Firma, marca de tiempo, rangos, fechas, duplicados, alarmas, auditoría |
| `test_historico.py` | 10 | 30 días de datos, repetibilidad, carga la primera vez, `servidor.json` |
| `test_simulador_firmado.py` | 12 | El simulador firma, encuentra la aplicación, sigue si cae y se rinde tras 5 fallos |
| **T13** `test_vistas_sprint2.py` | 57 | Casillas del código, ventana 03, gráficas, tarjetas, panel, histórico, paginación |
| `test_acceso_2fa.py` | 13 | Acceso completo con segundo factor contra el servidor real |
| `test_controlador_supervisor.py` | 21 | Refresco del panel, errores, exportación a CSV |
| **T14** `test_permisos_por_area.py` | 43 | 40 intentos de ver datos de otra área o de otro rol y 3 comprobaciones generales |
| `test_lecturas_falsas.py` | 31 | 30 intentos de colar lecturas falsas y el recuento |

Las pruebas **nunca tocan los datos del usuario**: usan una base SQLite temporal (`AUREA_BD` apunta a una carpeta temporal) que se recrea desde cero antes de cada prueba, y no cargan los 30 días de histórico (`AUREA_SIN_HISTORICO`). El resultado de cada caso de T14 está en `docs/Resultados T14.md`.

---

## 8. Prueba de extremo a extremo

Con el módulo de datos real, una base de datos nueva y el simulador firmado como proceso aparte:
- Primer arranque: crea las cuentas y carga 30 días de lecturas en unos 4,3 s (311.076 lecturas, 372 alarmas, 16 sensores asignados a técnicos) y publica `servidor.json`; al parar, lo retira.
- 3 ciclos del simulador firmado (36 sensores, 1 s de intervalo): 108 lecturas nuevas.
- Técnico (Diego): entra solo con la contraseña. Histórico de 7 días de un sensor suyo: 0,03 s.
- Supervisor (Laura): el login responde que falta el código; se configura el segundo factor, un código malo da 401 («Te quedan 2 intentos»), uno bueno abre la sesión; ve los 4 sensores de su área; pedir un sensor de otra área da 403; exporta un CSV.

**Sin hacer todavía:** abrir las ventanas 03, 04 y 05 en una pantalla real y escanear el QR con una aplicación autenticadora de verdad (lo comprueban Juan José, con las ventanas de T13, y Sergio, con el QR de T11); y abrir el `.exe` del Sprint 2 en Windows. Las capturas de las ventanas con datos reales se hicieron en modo sin pantalla.

---

## 9. Qué falta

**Ya hecho (12/11):** T11 a T14 fusionadas en `develop` y 486 pruebas en verde; columnas del tablero cambiadas a Sprint Backlog, To Do, Doing y Done.

**Para cerrar el Sprint 2:**
1. Actas del Sprint 2 (planificación, seguimiento, revisión y retrospectiva), con fecha, lugar, asistentes, orden del día y acuerdos reales. Las redacta el equipo con lo que ocurrió.
2. Autoevaluación por pares (cada persona rellena la suya).
3. Horas reales de cada tarea en el backlog.
4. Capturas del tablero Kanban al inicio y al final del sprint, con las mismas tareas que el Product Backlog. La de inicio se reconstruyó del historial del tablero.
5. Fusionar `develop` en `main` **antes de entregar** (solo el Scrum Master, Gonzalo Revuelta, con revisión de otra persona): el enunciado pide la rama principal actualizada y funcionando. Reconstruir el `.exe`.

**Sprint 3 (16/11 al 29/11):** tareas, incidencias y alarmas (T15), registro de auditoría encadenado y exportación (T16), ventanas de equipo, Mi turno e incidencia (T17), pruebas de integración y manual (T18).

**Sprint 4 (30/11 al 13/12):** Auditor y Administrador (T19) y pruebas finales, instalación portable y memoria (T20).

---

## 10. GitHub, tablero y acta

**Repositorio:** público, `JUANJOIC005/aurea-sentinel`. Ramas: `main` (versión entregada), `develop` (integración), `production` y una rama `tarea/Txx` por tarea. Cada tarea entra en `develop` con una pull request que cierra su issue; el Sprint 1 pasó a `main` con la pull request #32 (etiqueta `v0.1.0`). Las tareas del Sprint 2 entraron en `develop` el 12/11 en este orden: T11 (pull request #52), T12 (#53), T13 (#54) y T14 (#55).

**Rama `production`:** contiene el código y el ejecutable ya compilado, `AUREA Sentinel.exe`, para abrirlo sin compilar. La rama `main` es la de pruebas y compilación: al subir a `main`, GitHub Actions pasa las pruebas y construye el `.exe`.

**Scrum Master y entrega:** Juan José Ibáñez fue el Scrum Master del Sprint 1. En el Sprint 2 lo es Gonzalo Revuelta, que lleva el repositorio, fusiona las pull request en `develop` y en `main` y entrega el proyecto al profesor. Sergio García es el Product Owner.

**Issues #1 a #20:** una por tarea del backlog (T01 a T20), con su hito (Sprint 1 a 4, con fecha de fin), prioridad y responsable como etiquetas, y el texto de la tarea con su criterio de «hecho».

**Protección de `main`:** GitHub no la permite en repositorios privados con cuenta gratuita; el repositorio es público y la norma es que solo el Scrum Master del sprint fusiona en `main`.

**Tablero Kanban:** https://github.com/users/JUANJOIC005/projects/1, con las 20 issues. Desde el 12/11/2026 sus columnas son las que pide la rúbrica: *Sprint Backlog · To Do · Doing · Done* (antes eran Por hacer · En curso · En revisión · Hecho). La captura de inicio del Sprint 2 se reconstruyó ese día con el historial de cambios de estado del tablero, porque no se hizo el 02/11, y la propia imagen lo indica. Las capturas se generan con `python3 scripts/kanban_captura.py <salida.png> "texto"`: dibuja el tablero real (código, título, responsable, horas y prioridad de cada tarea, totales por columna y fecha y hora de la captura). Siempre sale con la fecha real y no se retoca.

**Actas:** `scripts/actas_pdf.py <carpeta>` genera las actas con la plantilla de actas de AUREA AUDIT. Las horas, el lugar, la retrospectiva y las firmas se dejan en blanco: solo el equipo las sabe.

**Product Backlog y lista de requisitos:** el Product Backlog (Excel, con la plantilla del profesor) y la lista de requisitos (PDF) se actualizan al cierre de cada sprint y se entregan junto con el resto. Los del Sprint 2 están en la carpeta de cierre del sprint.

**Entregables del Sprint 2 en Canvas** («SPRINT 2 - DESARROLLO», hasta el 15 de noviembre a las 23:59): todas las actas de reunión del sprint en PDF; dos capturas del tablero Kanban (estado de todas las tareas al inicio y al final del sprint); enlace a GitHub con la rama principal actualizada y funcionando; copia del proyecto en `.zip` de la última versión funcional; y esta documentación actualizada al final del sprint. Además, cada miembro sube su Excel a la tarea de evaluación entre pares (si falta uno, el equipo entero tiene un 0 en esa parte). La rúbrica puntúa también que el Product Backlog y la lista de requisitos estén actualizados y concuerden con el proyecto, por eso se entregan con el resto.
