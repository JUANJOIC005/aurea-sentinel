# AUREA Sentinel · Documentación del Sprint 1

Qué se ha hecho, cómo se ha instalado, cómo se usa y qué falta. Está escrito para poder repetirlo en otro equipo.

---

## 1. Estado del Sprint 1

Las tareas T01 a T10 del backlog están hechas, probadas y fusionadas en `main` (PR #32, etiqueta `v0.1.0`). Las 10 están en «Hecho» en el tablero de GitHub Projects.

| Tarea | Qué es | Estado |
|---|---|---|
| T01 | Repositorio, ramas y Kanban | Repositorio en GitHub con `main`, `develop` y `production`, plantillas de issues y de pull request, 4 hitos (sprints), etiquetas, las 20 tareas del backlog como issues (#1 a #20) y el tablero Kanban en GitHub Projects |
| T02 | Esqueleto MVC | Hecho. Ventanas (modelo, vista, controlador), módulo de datos, simulador, configuración por variables de entorno |
| T03 | Base de datos y migraciones | Hecho. 10 tablas (más la de control de migraciones), 9 áreas, 4 roles y 36 sensores. Se crea desde cero con un comando |
| T04 | Login con Argon2id y sesión | Hecho, con bloqueo a los 5 intentos |
| T05 | Registro pendiente | Hecho |
| T06 | Simulador de sensores v1 | Hecho. Guarda las lecturas en la base de datos SQLite local |
| T07 | Ventana base AUREA | Hecho, igual que el mockup 04 (probada a 1280, 1440, 1920 y 2560 px de ancho) |
| T08 | Login y registro (ventanas) | Hecho, iguales que los mockups 01 y 02 |
| T09 | Análisis de amenazas y tabla de permisos | Hecho (capítulo 6 de este documento) |
| T10 | Pruebas de login y registro | Hecho: 144 pruebas, todas en verde, 92 % de cobertura |

**Pendiente del equipo:** firmar las actas 02 y 03 (están redactadas, con las horas y el lugar en blanco), la autoevaluación por pares (cada persona rellena la suya) y las horas reales del backlog. No se pueden inventar: son del equipo.

---

## 2. Cómo se instala

AUREA Sentinel es una **aplicación totalmente local**: un único programa que funciona en el propio equipo, con su base de datos SQLite en un archivo. No usa servicios externos, ni la nube, ni conexión a internet, y no hay que instalar, contratar ni configurar ningún servidor. La parte que atiende las peticiones (`servidor/`) es un módulo interno del programa: solo responde al propio equipo (`127.0.0.1`) y se para al cerrar la aplicación.

**Para usarla (Windows):** descargar `AUREA.Sentinel.exe` de la sección *Releases* del repositorio (versión `v0.1.0`) y abrirlo con doble clic. La primera vez crea su base de datos en `%APPDATA%\AUREA Sentinel\` y las 18 cuentas de demostración. El `.exe` no está firmado digitalmente: Windows (SmartScreen o Defender) puede avisar la primera vez; hay que elegir «Más información → Ejecutar de todas formas». Lo construye GitHub Actions (`.github/workflows/exe.yml`) con Python 3.14.

**Para desarrollar (Debian 13):** todo viene de `apt`, sin pip (Debian trae Python 3.13; el `.exe` se construye con 3.14, y el código funciona con ambas).

| Pieza | Paquete | Versión |
|---|---|---|
| Interfaz | `python3-pyside6.qtwidgets`, `python3-pyside6.qtsvg` | 6.8.2.1 |
| Módulo de datos interno | `python3-fastapi`, `python3-uvicorn` | 0.115.11 · 0.32.0 |
| Base de datos | `sqlite3` de Python (incluido) | 3.46 |
| Contraseñas | `python3-argon2` | 21.1.0 |
| Comunicación interna y pruebas | `python3-httpx`, `python3-pytest-cov` | 0.28.1 · 5.0.0 |
| Empaquetado (solo para el `.exe`) | `pyinstaller` (pip) | 6.x |

```
pkexec apt install -y python3-pyside6.qtwidgets python3-pyside6.qtsvg python3-fastapi \
  python3-uvicorn python3-argon2 python3-httpx python3-pytest-cov
```

### Base de datos

Un único archivo SQLite: `~/.local/share/AUREA Sentinel/aurea sentinel.db` en Linux y `%APPDATA%\AUREA Sentinel\aurea sentinel.db` en Windows (se cambia con la variable `AUREA_BD`). Se crea y se actualiza sola al abrir la aplicación con las migraciones de `servidor/migrations/`. Para empezar de cero basta con borrar el archivo.

### Cómo se construye el `.exe`

PyInstaller no genera ejecutables de Windows desde Linux, por eso lo hace GitHub Actions en un Windows de GitHub (a mano desde *Actions → Ejecutable de Windows → Run workflow*, o automáticamente al subir a `main`). En un Windows propio: `pip install -r requirements.txt pillow` y `pyinstaller aurea_sentinel.spec`; sale `dist/AUREA Sentinel.exe`. La misma receta se comprobó en Linux: el ejecutable arranca, crea la base y las cuentas, y `--simulador` escribe lecturas. En GitHub Actions (Windows) se pasan las 144 pruebas antes de construir el `.exe`, y el `.exe` se ha abierto en un Windows y muestra la pantalla de acceso. Falta una prueba completa de uso (login, registro y simulador) en Windows.

---

## 3. Cómo se usa

**Abrir la aplicación.** Doble clic en `AUREA Sentinel.exe`. No hay nada que instalar ni configurar y no necesita internet ni red. La primera vez crea su base de datos en el equipo y las 18 cuentas de demostración.

**Entrar.** En la pantalla de acceso se escribe el correo y la contraseña (el icono del ojo la muestra). «Equipo compartido» evita que se recuerde el correo. Si algo falla, el mensaje es siempre el mismo y tras 5 fallos seguidos la cuenta se bloquea 15 minutos. Al entrar se abre la ventana principal, con el nombre, el rol y el área de la persona y el menú que corresponde a su rol. La sesión caduca sola (15 minutos Supervisor y Auditor, 30 Técnico, 10 Administrador) y vuelve a la pantalla de acceso; también se cierra con «Cerrar sesión».

**Pedir una cuenta.** En la pantalla de acceso, «Registrarse»: se rellenan los datos y la cuenta queda **pendiente**, sin poder entrar. La ventana del Administrador que las aprueba llega en el Sprint 4; mientras tanto se aprueba a mano con `sqlite3 "<archivo.db>" "UPDATE usuario SET estado='activo' WHERE correo='…'"`.

**Qué hay en el Sprint 1.** Acceso, registro y la ventana principal con su menú por rol. Las secciones que aún no existen (panel, histórico, alarmas, tareas…) muestran un marcador que dice en qué sprint llegan.

**Cuentas de demostración** (correo `nombre.apellido@cn-valdecierzo.es`, sin tildes; contraseña de todas: `Valdecierzo-2026!`):

| Rol | Ejemplo |
|---|---|
| Supervisor (9, uno por área) | `laura.mendez@cn-valdecierzo.es` |
| Técnico (6, dependen de un supervisor) | `diego.paredes@cn-valdecierzo.es` |
| Auditor (2) | `beatriz.lara@cn-valdecierzo.es` |
| Administrador (1) | `alvaro.campos@cn-valdecierzo.es` |

La contraseña de demostración es pública a propósito (la aplicación se entrega para que el profesor la abra sin preparar nada). Una instalación real no debe sembrar cuentas con una contraseña conocida.

**Generar lecturas de sensores.** El simulador es el mismo programa con una opción: `AUREA Sentinel.exe --simulador` (acepta `--intervalo`, `--ciclos`, `--semilla` y `--sin-excursiones`). Escribe una lectura de los 36 sensores cada 5 s en la misma base de datos y termina cuando se cierra. No es un servicio: solo funciona mientras se ejecuta.

---

## 4. Claves y secretos

**En el repositorio no hay ninguna clave ni contraseña.** Esto es lo que existe y dónde vive cada cosa:

| Qué | Dónde está | Notas |
|---|---|---|
| Acceso a la base de datos | Es un archivo local de la carpeta de datos del usuario; no hay usuario ni contraseña de base de datos | Lo protegen los permisos del sistema operativo sobre esa carpeta |
| Configuración | Variables de entorno o fichero `.env` | `.env` está en `.gitignore` y no se sube. La plantilla es `.env.example` (sin valores secretos) |
| Contraseña de las cuentas de demo | `Valdecierzo-2026!` (constante `PASSWORD_DEMO`), o la variable `AUREA_DEMO_PASSWORD` si se define | Es una contraseña de demostración conocida, solo para las cuentas ficticias de la central; no protege ningún dato real |
| Contraseñas de usuarios | En la base de datos solo como hash **Argon2id** | No se pueden recuperar, solo restablecer |
| Tokens de sesión | El cliente guarda el token **solo en memoria**. La base guarda su hash SHA-256 | Caducan según el rol (15 min Supervisor y Auditor, 30 Técnico, 10 Administrador) |
| Último correo usado | Ajustes locales de Qt (`~/.config/AUREA AUDIT/`) | Solo el correo, nunca la contraseña. Se omite con «Equipo compartido» |
| Claves de firma de lecturas | **Todavía no existen**: llegan en el Sprint 2 (T12) | Irán fuera del repositorio, en variable de entorno |

Pendiente de seguridad, ya previsto en el backlog: doble factor (Sprint 2, T11) y cifrado (TLS) solo si algún día los datos salen del equipo. Hoy todo es local: las ventanas y el módulo de datos están en el mismo programa y se hablan dentro del equipo (`127.0.0.1`, puerto libre elegido al arrancar), sin abrirse a la red.

---

## 5. Cómo está hecho

```
aurea-sentinel/
├── aurea_sentinel.py       punto de entrada del .exe (aplicación o --simulador)
├── aurea_sentinel.spec     receta de PyInstaller
├── requirements.txt · pytest.ini · .env.example   dependencias, configuración de las pruebas y plantilla de ajustes
├── servidor/               módulo de datos interno (el nombre de la carpeta es histórico)
│   ├── local.py            prepara la base de datos y activa el módulo dentro de la aplicación
│   ├── db.py · migrate.py · config.py   conexión SQLite, migraciones y rutas
│   ├── api/                operaciones: login, registro, sesión, datos públicos
│   ├── migrations/         001_esquema.sql · 002_catalogo.sql (áreas, roles y 36 sensores)
│   ├── seguridad.py        Argon2id, tokens, política de contraseñas
│   ├── usuarios.py · sesiones.py · auditoria.py   consultas a la base de datos
│   └── datos_demo.py       las 18 cuentas de demostración
├── simulador/              modelo del sensor, destinos de las lecturas, línea de comandos
├── cliente/                ventanas de la aplicación de escritorio (PySide6)
│   ├── modelo/             sesión, comunicación con el módulo de datos, menús por rol
│   ├── vista/              ventanas: acceso, login, registro, VentanaBase, estilos
│   └── controlador/        acceso, sesión abierta y arranque
├── scripts/                generan los PDF de las actas, los diagramas UML, las capturas del Kanban y copian este documento a la memoria
├── equipo/                 ficha de cada miembro (tarea asignada y usuario de GitHub)
├── tests/                  144 pruebas
├── DOCUMENTACION.md        este documento
└── .github/                plantillas de issue y de pull request, y el flujo que construye el .exe
```

**MVC.** El *modelo* guarda los datos y habla con el módulo de datos, la *vista* son las ventanas y el *controlador* las conecta. Ninguna ventana toca la base de datos: todo pasa por ese módulo.

**Login.** El módulo de datos responde siempre con el mismo mensaje (no revela si el correo existe, si la contraseña falló o si la cuenta está bloqueada) y tarda lo mismo en cada caso. Tras 5 fallos seguidos la cuenta se bloquea 15 minutos. Cada acceso, fallo, bloqueo y registro queda anotado en `evento_auditoria` (la cadena de hashes llega en el Sprint 3).

**Registro.** La cuenta se guarda como «pendiente». Los técnicos eligen su supervisor y heredan su área (lo comprueba la propia base de datos). Si el correo ya existe, la respuesta es igual que si no existiera.

**Simulador.** Cada sensor es su valor nominal más una deriva lenta y un poco de ruido. De vez en cuando (de media cada 48 h) hace una excursión que sobrepasa el umbral de aviso, para que haya alarmas que ver. Las lecturas van a un «destino»: hoy la base de datos SQLite local; en el Sprint 2 se añadirá otro que las envíe firmadas al módulo de datos, sin tocar el simulador.

**Ventanas.** Copian los mockups: azul `#0B2D5B`, tarjetas blancas, menú lateral con pie de usuario, avatar con insignia de rol, barra de estado azul. Por debajo de 1366 px el menú queda de iconos (68 px) y se oculta el indicador de estado de la cabecera. Cada sección que aún no existe muestra un marcador que dice en qué sprint llega.

**Diferencias con los mockups** (a propósito, para no mostrar cosas que aún no existen):
- La cabecera dice «Servidor conectado» en vez de «Datos en vivo»: todavía no hay datos en directo.
- El pie del menú no dice «MFA verificado»: el doble factor llega en el Sprint 2.
- La barra de estado no muestra «TLS 1.3»: todo es local y no sale del equipo.
- El logo es el oficial de AUREA AUDIT, sacado del PDF de imagen corporativa entregado en Canvas (`cliente/recursos/aurea_isotipo.png`, solo la «A»). Es una imagen de 590×475 px: se ve nítida en los paneles de acceso, pero convendría tener el original en vector.
- La fuente es Aptos si está instalada y, si no, Segoe UI o Noto Sans.
- El formulario de registro lista los supervisores del área antes de iniciar sesión, como en el mockup. Eso enseña nombres de personal a quien aún no se ha identificado; si el CTO lo considera un riesgo, se cambia por escribir el correo del supervisor.

---

## 6. T09 · Análisis de amenazas y tabla de permisos

### 6.1 Qué puede salir mal y qué hacemos

| Parte | Qué podría pasar | Qué hacemos | Estado |
|---|---|---|---|
| **Cliente** | Alguien roba la contraseña mirando la pantalla o con un programa que registra teclas | Contraseña oculta, con botón para verla; no se guarda en disco | Hecho |
| | Alguien usa un equipo que otra persona dejó abierto | Sesión con caducidad por rol y botón «Cerrar sesión»; al caducar vuelve al login | Hecho |
| | Alguien manipula el cliente para ver otra área | El cliente solo esconde menús; **el módulo de datos decide** qué se devuelve | Parcial: permisos por área en el Sprint 2 (T11) |
| **Módulo de datos** | Adivinar contraseñas probando muchas | Bloqueo de 15 min tras 5 fallos; contraseña mínima de 12 caracteres y lista de contraseñas filtradas | Hecho |
| | Descubrir qué correos existen | Mismo mensaje y mismo tiempo de respuesta con cualquier fallo; el registro responde igual si el correo ya existe | Hecho |
| | Robar un token de sesión | Token aleatorio de 256 bits, solo su hash en la base de datos, caducidad, se invalida al cerrar sesión o al bloquear la cuenta | Hecho |
| | Enviar datos mal formados o enormes | Validación de todos los campos con límites de longitud; las contraseñas largas se limitan a 256 caracteres | Hecho |
| | Espiar la comunicación entre las ventanas y el módulo de datos | Es interna del equipo (`127.0.0.1`), sin red; TLS solo si algún día sale | No aplica hoy |
| | Saltarse el segundo factor | Código de 6 dígitos obligatorio para Supervisor, Auditor y Administrador | Pendiente (Sprint 2, T11) |
| **Base de datos** | Que alguien con acceso edite o borre el rastro de lo que hizo | El registro de auditoría no admite `UPDATE` ni `DELETE` (lo impide la propia base) | Hecho. La cadena de hashes llega en el Sprint 3 (T16) |
| | Datos incoherentes (técnico sin supervisor, umbrales al revés, lecturas duplicadas) | Claves, restricciones y disparadores en las tablas | Hecho |
| | Robo de contraseñas si se filtra la base | Solo hashes Argon2id | Hecho |
| **Simulador** | Que alguien envíe lecturas falsas haciéndose pasar por él | Firma de cada lectura (HMAC) y rango físico válido | Pendiente (Sprint 2, T12). Hoy escribe directamente en la base de datos, en la misma máquina |

### 6.2 Qué puede hacer cada rol (lo que implementa el Sprint 2)

«Su área» = el área del supervisor. «Sus sensores» = los que le asigna su supervisor. Todo lo que no está aquí está prohibido.

| Recurso | Acción | Supervisor | Técnico | Auditor | Administrador |
|---|---|---|---|---|---|
| Lecturas en directo | Ver | Su área | Sus sensores | Solo agregados | — |
| Histórico de sensores | Ver | 30 días, su área | 7 días, sus sensores | Agregados | — |
| | Exportar CSV | Sí (queda en el registro) | — | — | — |
| Alarmas | Ver | Su área | De sus sensores | Solo en informes | — |
| | Reconocer | Sí | — | — | — |
| Tareas | Crear y asignar | A sus técnicos | — | — | — |
| | Ver | Las de su equipo | Las suyas | — | — |
| | Cambiar estado | — | Las suyas | — | — |
| Incidencias | Crear | — | Sobre sus sensores | — | — |
| | Ver | Las de su equipo | Las suyas | Solo lectura | — |
| Cuentas | Solicitar | Cualquiera, sin sesión | | | |
| | Aprobar, bloquear, editar | — | — | — | Sí |
| Vínculos supervisor → técnico | Asignar | — | — | — | Sí |
| Sensores y umbrales | Ver inventario | — | — | Solo lectura | Sí |
| | Editar umbral | — | — | — | Sí, con motivo y segundo factor |
| Registro de auditoría | Ver | — | — | Todo, con nombres ocultos | Solo sus propios eventos |
| | Verificar y exportar | — | — | Sí | — |

Regla general para implementarlo: en cada petición el módulo de datos comprueba **rol**, luego **área o vínculo**, y solo entonces consulta datos. Si algo no coincide responde «prohibido» y lo anota en el registro.

---

## 7. Pruebas (T10)

**144 pruebas en verde, 92 % de cobertura**. Los modelos y controladores del cliente y del módulo de datos están entre el 85 % y el 100 %. Lo que queda sin probar son los arranques por línea de comandos (`migrate`, `simulador`, `datos_demo`, `config`), que se han ejecutado a mano.

| Archivo | Qué comprueba |
|---|---|
| `test_bd.py` | 9 áreas, 4 roles, 36 sensores; claves y restricciones; el registro de auditoría no se edita |
| `test_auth.py` | Login correcto e incorrecto, mensaje idéntico con correo inexistente, bloqueo a los 5 intentos y fin del bloqueo, cuentas pendientes, caducidad por rol, cierre de sesión, token no guardado en claro |
| `test_registro.py` | Cuenta pendiente, reglas por rol, contraseñas débiles, correo repetido, datos públicos del formulario |
| `test_seguridad.py` | Argon2id, tokens, política de contraseñas |
| `test_simulador.py` | Rangos físicos, valores en torno al nominal, excursiones, repetibilidad con semilla, 36 sensores en la base |
| `test_datos_demo.py` | Las cuentas de demo cumplen lo que pide el enunciado (9 principales, 6 relacionados, alguno con varios) |
| `test_cliente_modelo.py` | Datos de sesión y comunicación con el módulo de datos real y con uno caído |
| `test_cliente_controlador.py` | Login, registro y caducidad, con un módulo de datos simulado; flujo completo de la aplicación |
| `test_vistas.py` | Nombre y rol visibles en las 4 vistas, menú por rol, cambio de tamaño, tamaño mínimo 1024×640 |

Las pruebas **nunca tocan los datos del usuario**: usan una base SQLite temporal (`AUREA_BD` apunta a una carpeta temporal) que se recrea desde cero antes de cada prueba. `test_local.py` comprueba el módulo interno, el puerto libre y la siembra de cuentas de la primera vez.

---

## 8. Prueba hecha a mano

Con el módulo de datos y la base de datos reales (y, tras el cambio a aplicación local, con el ejecutable empaquetado en Linux, que arranca, crea su base con las 18 cuentas y escribe lecturas con `--simulador`): login de un técnico (devuelve nombre, rol, área y supervisor), login con contraseña mala (mensaje neutro), 3 ciclos del simulador (108 lecturas de 36 sensores) y capturas de las ventanas generadas con la aplicación real para compararlas con los mockups. Las capturas se hicieron en modo sin pantalla; la aplicación sí se ha abierto en pantalla real, en Debian y en Windows con el `.exe` (pantalla de acceso).

---

## 9. Qué falta para cerrar el sprint

1. Firmar las actas nº 02 y nº 03 y rellenar horas y lugar de cada reunión, y la retrospectiva del acta nº 03.
2. Autoevaluación por pares (cada persona sube su Excel a Canvas).
3. Actualizar las horas reales en el backlog.
4. Que cada miembro suba su enlace del árbol de GitHub a Canvas («Arbol de GitHub»).
5. Mockups en PDF (los aporta Juan José).

---

## 10. GitHub, tablero y acta

**Repositorio:** público, `JUANJOIC005/aurea-sentinel`. Ramas: `main` (versión entregada), `develop` (integración), `production` y una rama `tarea/Txx` por tarea. Cada tarea entró en `develop` con una pull request (#22 a #31) y todo el sprint pasó a `main` con la pull request #32; la etiqueta `v0.1.0` marca la entrega.

**Scrum Master y entrega:** Juan José Ibáñez es el Scrum Master, lleva el repositorio, es el encargado de fusionar en `main` y entrega el proyecto al profesor.

**Issues #1 a #20:** una por tarea del backlog (T01 a T20), con su hito (Sprint 1 a 4, con fecha de fin), prioridad y responsable como etiquetas, y el texto de la tarea con su criterio de «hecho».

**Protección de `main`:** GitHub no la permite en repositorios privados con cuenta gratuita; el repositorio es público y la norma es que solo Juan José Ibáñez fusiona en `main`.

**Captura del Kanban:** `python3 scripts/kanban_captura.py <salida.png> "Captura de final de sprint"` dibuja el tablero real de GitHub Projects (código, título, responsable, horas y prioridad de cada tarea, totales por columna y fecha y hora de la captura). Siempre sale con la fecha real.

**Tablero Kanban:** https://github.com/users/JUANJOIC005/projects/1 (columnas Por hacer · En curso · En revisión · Hecho), con las 20 issues. Las tareas T01 a T10 están en «Hecho». Las capturas del tablero se generan con `python3 scripts/kanban_captura.py <salida.png> "texto"`; la **del final del sprint** se hizo el 29/10/2026 (`Kanban final Sprint 1.png`); la de inicio no se hizo a tiempo y no se entrega como si lo estuviera.

**Actas:** `scripts/actas_pdf.py <carpeta>` genera el acta nº 02 (planificación, fechada el 20/10/2026) y el acta nº 03 (revisión y retrospectiva, fechada el 30/10/2026) con la plantilla de actas de AUREA AUDIT. Redacta Juan José Ibáñez y constan los cuatro asistentes. Las horas, el lugar, la retrospectiva y las firmas se dejan en blanco: solo el equipo las sabe.

**Entregables del Sprint 1 en Canvas** («SPRINT 1 - DESARROLLO», hasta el 1 de noviembre a las 23:59):
1. Actas de reunión del sprint en PDF.
2. Dos capturas del tablero Kanban, al inicio y al final del sprint.
3. Enlace a GitHub con la rama principal actualizada.
4. Copia del proyecto en `.zip` de la última versión funcional.
5. Documentación actualizada al final del sprint.
6. Además, cada miembro sube su Excel de autoevaluación a «SPRINT 1 - Autoevaluación del equipo»; si falta uno, el equipo entero tiene un 0 en esa parte.
