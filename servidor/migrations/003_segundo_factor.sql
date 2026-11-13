-- AUREA Sentinel · doble factor (TOTP) y sensores de cada técnico (Sprint 2, T11)

-- Secreto del segundo factor de cada persona. `activo` pasa a 1 cuando confirma su primer código.
-- `ultimo_paso` guarda el último intervalo de 30 s usado: el mismo código no vale dos veces.
CREATE TABLE segundo_factor (
    usuario_id   INTEGER PRIMARY KEY REFERENCES usuario (id),
    secreto      TEXT NOT NULL CHECK (length(secreto) >= 16),
    activo       INTEGER NOT NULL DEFAULT 0 CHECK (activo IN (0, 1)),
    ultimo_paso  INTEGER NOT NULL DEFAULT 0,
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    activado_en  TEXT
);

-- Entre la contraseña y el código la persona aún no tiene sesión: tiene un «desafío» de pocos minutos y,
-- como mucho, 3 intentos. Solo se guarda el hash del token, igual que con las sesiones.
CREATE TABLE desafio_2fa (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL REFERENCES usuario (id),
    token_hash  TEXT NOT NULL UNIQUE,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    expira_en   TEXT NOT NULL,
    intentos    INTEGER NOT NULL DEFAULT 0 CHECK (intentos >= 0),
    usado       INTEGER NOT NULL DEFAULT 0 CHECK (usado IN (0, 1))
);
CREATE INDEX desafio_usuario_idx ON desafio_2fa (usuario_id);

-- «Sus sensores» de un técnico: los que le asigna su supervisor.
CREATE TABLE asignacion_sensor (
    tecnico_id    INTEGER NOT NULL REFERENCES usuario (id),
    sensor_id     INTEGER NOT NULL REFERENCES sensor (id),
    asignado_por  INTEGER REFERENCES usuario (id),
    asignado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tecnico_id, sensor_id)
);
CREATE INDEX asignacion_sensor_idx ON asignacion_sensor (sensor_id);

-- Solo se asignan sensores a técnicos, y de su misma área: lo comprueba la propia base de datos.
CREATE TRIGGER asignacion_valida BEFORE INSERT ON asignacion_sensor
BEGIN
    SELECT RAISE(ABORT, 'Solo se asignan sensores a técnicos')
     WHERE (SELECT r.codigo FROM usuario u JOIN rol r ON r.id = u.rol_id WHERE u.id = NEW.tecnico_id)
           IS NOT 'tecnico';
    SELECT RAISE(ABORT, 'El sensor es de otra área')
     WHERE (SELECT area_id FROM sensor WHERE id = NEW.sensor_id)
           IS NOT (SELECT area_id FROM usuario WHERE id = NEW.tecnico_id);
END;
