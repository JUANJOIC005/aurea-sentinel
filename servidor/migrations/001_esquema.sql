-- AUREA Sentinel · esquema inicial en SQLite (Sprint 1, T03)

-- ── Usuarios y roles ────────────────────────────────────────────────
-- Las fechas se guardan como texto UTC «AAAA-MM-DD HH:MM:SS» (datetime('now')), que se ordena bien.
CREATE TABLE rol (
    id      INTEGER PRIMARY KEY,
    codigo  TEXT NOT NULL UNIQUE CHECK (codigo IN ('supervisor', 'tecnico', 'auditor', 'administrador')),
    nombre  TEXT NOT NULL
);

CREATE TABLE area (
    id      INTEGER PRIMARY KEY,
    codigo  TEXT NOT NULL UNIQUE CHECK (codigo GLOB 'A[1-9]'),
    nombre  TEXT NOT NULL
);

CREATE TABLE usuario (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre             TEXT NOT NULL CHECK (length(trim(nombre)) >= 3),
    correo             TEXT NOT NULL CHECK (correo LIKE '_%@_%._%' AND correo NOT LIKE '% %' AND correo NOT LIKE '%@%@%'),
    password_hash      TEXT NOT NULL,
    rol_id             INTEGER NOT NULL REFERENCES rol (id),
    area_id            INTEGER REFERENCES area (id),
    -- vínculo Supervisor → Técnico
    supervisor_id      INTEGER REFERENCES usuario (id),
    estado             TEXT NOT NULL DEFAULT 'pendiente'
                       CHECK (estado IN ('pendiente', 'activo', 'bloqueado', 'rechazado')),
    motivo             TEXT,
    intentos_fallidos  INTEGER NOT NULL DEFAULT 0 CHECK (intentos_fallidos >= 0),
    bloqueado_hasta    TEXT,
    creado_en          TEXT NOT NULL DEFAULT (datetime('now')),
    ultimo_acceso      TEXT,
    CONSTRAINT usuario_no_es_su_supervisor CHECK (supervisor_id IS NULL OR supervisor_id <> id)
);

CREATE UNIQUE INDEX usuario_correo_unico ON usuario (lower(correo));
CREATE INDEX usuario_supervisor_idx ON usuario (supervisor_id);

-- Reglas que dependen de otras tablas:
--   · un técnico tiene supervisor, y ese supervisor es un supervisor de verdad;
--   · el técnico hereda el área de su supervisor;
--   · solo los técnicos tienen supervisor;
--   · un supervisor tiene área.
-- SQLite no deja modificar NEW en un trigger: el área heredada se rellena en un trigger AFTER INSERT.
CREATE TRIGGER usuario_validar_alta BEFORE INSERT ON usuario
BEGIN
    SELECT RAISE(ABORT, 'Un técnico necesita un supervisor')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) = 'tecnico' AND NEW.supervisor_id IS NULL;
    SELECT RAISE(ABORT, 'El supervisor indicado no es un supervisor')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) = 'tecnico' AND NEW.supervisor_id IS NOT NULL
       AND (SELECT r.codigo FROM usuario u JOIN rol r ON r.id = u.rol_id WHERE u.id = NEW.supervisor_id)
           IS NOT 'supervisor';
    SELECT RAISE(ABORT, 'El técnico debe estar en el área de su supervisor')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) = 'tecnico' AND NEW.area_id IS NOT NULL
       AND NEW.area_id IS NOT (SELECT area_id FROM usuario WHERE id = NEW.supervisor_id);
    SELECT RAISE(ABORT, 'Solo los técnicos tienen supervisor')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) <> 'tecnico' AND NEW.supervisor_id IS NOT NULL;
    SELECT RAISE(ABORT, 'Un supervisor necesita un área')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) = 'supervisor' AND NEW.area_id IS NULL;
END;

CREATE TRIGGER usuario_validar_cambio BEFORE UPDATE OF rol_id, supervisor_id, area_id ON usuario
BEGIN
    SELECT RAISE(ABORT, 'Un técnico necesita un supervisor')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) = 'tecnico' AND NEW.supervisor_id IS NULL;
    SELECT RAISE(ABORT, 'El supervisor indicado no es un supervisor')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) = 'tecnico' AND NEW.supervisor_id IS NOT NULL
       AND (SELECT r.codigo FROM usuario u JOIN rol r ON r.id = u.rol_id WHERE u.id = NEW.supervisor_id)
           IS NOT 'supervisor';
    SELECT RAISE(ABORT, 'El técnico debe estar en el área de su supervisor')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) = 'tecnico' AND NEW.area_id IS NOT NULL
       AND NEW.area_id IS NOT (SELECT area_id FROM usuario WHERE id = NEW.supervisor_id);
    SELECT RAISE(ABORT, 'Solo los técnicos tienen supervisor')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) <> 'tecnico' AND NEW.supervisor_id IS NOT NULL;
    SELECT RAISE(ABORT, 'Un supervisor necesita un área')
     WHERE (SELECT codigo FROM rol WHERE id = NEW.rol_id) = 'supervisor' AND NEW.area_id IS NULL;
END;

CREATE TRIGGER usuario_area_heredada AFTER INSERT ON usuario
WHEN NEW.supervisor_id IS NOT NULL AND NEW.area_id IS NULL
BEGIN
    UPDATE usuario SET area_id = (SELECT area_id FROM usuario WHERE id = NEW.supervisor_id) WHERE id = NEW.id;
END;

-- Sesiones: solo se guarda el hash del token, nunca el token.
CREATE TABLE sesion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL REFERENCES usuario (id),
    token_hash  TEXT NOT NULL UNIQUE,
    creada_en   TEXT NOT NULL DEFAULT (datetime('now')),
    expira_en   TEXT NOT NULL,
    cerrada_en  TEXT,
    CHECK (expira_en > creada_en)
);
CREATE INDEX sesion_usuario_idx ON sesion (usuario_id);

-- ── Sensores y lecturas ─────────────────────────────────────────────
CREATE TABLE sensor (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tag             TEXT NOT NULL UNIQUE CHECK (tag GLOB '[A-Z][A-Z]-[0-9][0-9][0-9]'),
    nombre          TEXT NOT NULL,
    magnitud        TEXT NOT NULL,
    unidad          TEXT NOT NULL,
    area_id         INTEGER NOT NULL REFERENCES area (id),
    valor_nominal   REAL NOT NULL,
    min_fisico      REAL NOT NULL,
    max_fisico      REAL NOT NULL,
    aviso_bajo      REAL,
    alarma_bajo     REAL,
    aviso_alto      REAL,
    alarma_alto     REAL,
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    CONSTRAINT sensor_rango_fisico CHECK (min_fisico < max_fisico),
    CONSTRAINT sensor_nominal_en_rango CHECK (valor_nominal BETWEEN min_fisico AND max_fisico),
    CONSTRAINT sensor_umbrales_en_orden CHECK (
        (aviso_alto  IS NULL OR alarma_alto IS NULL OR aviso_alto < alarma_alto)
        AND (aviso_bajo IS NULL OR alarma_bajo IS NULL OR alarma_bajo < aviso_bajo)
        AND (aviso_bajo IS NULL OR aviso_alto  IS NULL OR aviso_bajo < aviso_alto)
    ),
    CONSTRAINT sensor_umbrales_en_rango CHECK (
        coalesce(alarma_bajo, aviso_bajo, min_fisico) >= min_fisico
        AND coalesce(alarma_alto, aviso_alto, max_fisico) <= max_fisico
    )
);
CREATE INDEX sensor_area_idx ON sensor (area_id);

CREATE TABLE lectura (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id  INTEGER NOT NULL REFERENCES sensor (id),
    instante   TEXT NOT NULL,
    valor      REAL NOT NULL,
    valida     INTEGER NOT NULL DEFAULT 1 CHECK (valida IN (0, 1)),
    UNIQUE (sensor_id, instante)
);
CREATE INDEX lectura_instante_idx ON lectura (instante);

-- ── Alarmas, tareas e incidencias ───────────────────────────────────
CREATE TABLE alarma (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id       INTEGER NOT NULL REFERENCES sensor (id),
    nivel           TEXT NOT NULL CHECK (nivel IN ('aviso', 'alarma')),
    valor           REAL NOT NULL,
    abierta_en      TEXT NOT NULL DEFAULT (datetime('now')),
    estado          TEXT NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'reconocida', 'cerrada')),
    reconocida_por  INTEGER REFERENCES usuario (id),
    reconocida_en   TEXT,
    cerrada_en      TEXT,
    CONSTRAINT alarma_reconocimiento CHECK (
        estado <> 'reconocida' OR (reconocida_por IS NOT NULL AND reconocida_en IS NOT NULL)
    )
);
CREATE INDEX alarma_sensor_idx ON alarma (sensor_id, abierta_en DESC);
CREATE INDEX alarma_abiertas_idx ON alarma (estado) WHERE estado <> 'cerrada';

CREATE TABLE tarea (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo        TEXT NOT NULL,
    descripcion   TEXT,
    creada_por    INTEGER NOT NULL REFERENCES usuario (id),
    asignada_a    INTEGER NOT NULL REFERENCES usuario (id),
    sensor_id     INTEGER REFERENCES sensor (id),
    alarma_id     INTEGER REFERENCES alarma (id),
    prioridad     TEXT NOT NULL DEFAULT 'media' CHECK (prioridad IN ('baja', 'media', 'alta')),
    estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'en_curso', 'hecha')),
    fecha_limite  TEXT,
    creada_en     TEXT NOT NULL DEFAULT (datetime('now')),
    cerrada_en    TEXT,
    CONSTRAINT tarea_no_a_si_mismo CHECK (creada_por <> asignada_a),
    CONSTRAINT tarea_cierre CHECK ((estado = 'hecha') = (cerrada_en IS NOT NULL))
);
CREATE INDEX tarea_asignada_idx ON tarea (asignada_a, estado);

CREATE TABLE incidencia (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tecnico_id      INTEGER NOT NULL REFERENCES usuario (id),
    tarea_id        INTEGER REFERENCES tarea (id),
    sensor_id       INTEGER NOT NULL REFERENCES sensor (id),
    tipo            TEXT NOT NULL CHECK (tipo IN ('inspeccion', 'lectura_manual', 'anomalia')),
    valor_medido    REAL,
    observaciones   TEXT,
    creada_en       TEXT NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT incidencia_lectura_con_valor CHECK (tipo <> 'lectura_manual' OR valor_medido IS NOT NULL)
);
CREATE INDEX incidencia_sensor_idx ON incidencia (sensor_id, creada_en DESC);

-- ── Registro de auditoría ───────────────────────────────────────────
-- hash_anterior y hash se rellenan en el Sprint 3 (T16, cadena de hashes).
CREATE TABLE evento_auditoria (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    instante       TEXT NOT NULL DEFAULT (datetime('now')),
    actor_id       INTEGER REFERENCES usuario (id),
    accion         TEXT NOT NULL,
    recurso        TEXT,
    resultado      TEXT NOT NULL CHECK (resultado IN ('ok', 'fallo', 'denegado')),
    detalle        TEXT NOT NULL DEFAULT '{}',
    hash_anterior  TEXT,
    hash           TEXT
);
CREATE INDEX evento_instante_idx ON evento_auditoria (instante DESC);

-- Un registro de auditoría no se edita ni se borra.
CREATE TRIGGER evento_auditoria_no_editar BEFORE UPDATE ON evento_auditoria
BEGIN
    SELECT RAISE(ABORT, 'El registro de auditoría no se puede modificar ni borrar');
END;

CREATE TRIGGER evento_auditoria_no_borrar BEFORE DELETE ON evento_auditoria
BEGIN
    SELECT RAISE(ABORT, 'El registro de auditoría no se puede modificar ni borrar');
END;
