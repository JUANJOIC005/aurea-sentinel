-- AUREA Sentinel · roles, 9 áreas y 36 sensores de la central Valdecierzo (Sprint 1, T03)
-- Los valores siguen rangos típicos de un reactor de agua a presión de ~1.000 MW.

INSERT INTO rol (id, codigo, nombre) VALUES
    (1, 'supervisor',    'Supervisor de área'),
    (2, 'tecnico',       'Técnico de campo'),
    (3, 'auditor',       'Auditor AUREA'),
    (4, 'administrador', 'Administrador');

INSERT INTO area (id, codigo, nombre) VALUES
    (1, 'A1', 'Reactor y circuito primario'),
    (2, 'A2', 'Generadores de vapor'),
    (3, 'A3', 'Turbina y alternador'),
    (4, 'A4', 'Edificio de contención'),
    (5, 'A5', 'Piscina de combustible gastado'),
    (6, 'A6', 'Refrigeración y agua de circulación'),
    (7, 'A7', 'Sistema eléctrico y diésel de emergencia'),
    (8, 'A8', 'Protección radiológica y entorno'),
    (9, 'A9', 'Red OT y ciberseguridad');

INSERT INTO sensor
    (tag, nombre, magnitud, unidad, area_id, valor_nominal, min_fisico, max_fisico,
     aviso_bajo, alarma_bajo, aviso_alto, alarma_alto)
VALUES
    -- A1 · Reactor y circuito primario
    ('TE-101', 'Temperatura rama caliente',        'Temperatura', '°C',     1,   325.6,     0,    400,    NULL,  NULL,   327.0,   330.0),
    ('PT-102', 'Presión del presionador',          'Presión',     'bar',    1,   155.0,     0,    200,   152.0, 150.0,   157.0,   160.0),
    ('FT-103', 'Caudal refrigerante primario',     'Caudal',      'm³/h',   1, 22140.0,     0,  30000, 20000.0, 19000.0, 22500.0, 23000.0),
    ('LT-104', 'Nivel del presionador',            'Nivel',       '%',      1,    58.2,     0,    100,    45.0,  35.0,    65.0,    70.0),
    -- A2 · Generadores de vapor
    ('PT-201', 'Presión de vapor',                 'Presión',     'bar',    2,    67.0,     0,    100,    62.0,  60.0,    70.0,    72.0),
    ('LT-202', 'Nivel del generador de vapor',     'Nivel',       '%',      2,    50.0,     0,    100,    35.0,  25.0,    65.0,    75.0),
    ('TE-203', 'Temperatura agua de alimentación', 'Temperatura', '°C',     2,   227.0,     0,    300,   215.0, 210.0,   235.0,   240.0),
    ('FT-204', 'Caudal de vapor',                  'Caudal',      't/h',    2,  1450.0,     0,   2500,  1000.0, 800.0,  1600.0,  1750.0),
    -- A3 · Turbina y alternador
    ('ST-301', 'Velocidad de la turbina',          'Velocidad',   'rpm',    3,  1500.0,     0,   1800,  1470.0, 1440.0,  1530.0,  1560.0),
    ('VT-302', 'Vibración de la turbina',          'Vibración',   'mm/s',   3,     2.5,     0,     20,    NULL,  NULL,     7.1,    11.2),
    ('JT-303', 'Potencia eléctrica generada',      'Potencia',    'MW',     3,  1000.0,     0,   1200,    NULL,  NULL,  1080.0,  1120.0),
    ('TE-304', 'Temperatura cojinete principal',   'Temperatura', '°C',     3,    72.0,     0,    150,    NULL,  NULL,    90.0,   105.0),
    -- A4 · Edificio de contención
    ('PT-401', 'Presión de la contención',         'Presión',     'kPa',    4,    98.5,     0,    500,    NULL,  NULL,   110.0,   125.0),
    ('TE-402', 'Temperatura de la contención',     'Temperatura', '°C',     4,    32.0,     0,    200,    NULL,  NULL,    45.0,    55.0),
    ('AT-403', 'Concentración de hidrógeno',       'Concentración','% vol', 4,     0.1,     0,     10,    NULL,  NULL,     1.0,     2.0),
    ('MT-404', 'Humedad relativa',                 'Humedad',     '%',      4,    45.0,     0,    100,    NULL,  NULL,    80.0,    90.0),
    -- A5 · Piscina de combustible gastado
    ('TE-501', 'Temperatura del agua de la piscina','Temperatura','°C',     5,    30.0,     0,    120,    NULL,  NULL,    45.0,    60.0),
    ('LT-502', 'Nivel de la piscina',              'Nivel',       'm',      5,    11.8,     0,     14,    11.0,  10.5,    12.5,    13.0),
    ('RT-503', 'Tasa de dosis en la piscina',      'Radiación',   'µSv/h',  5,     1.2,     0,   1000,    NULL,  NULL,    10.0,    25.0),
    ('CT-504', 'Concentración de boro',            'Concentración','ppm',   5,  2300.0,     0,   4000,  2000.0, 1900.0,    NULL,    NULL),
    -- A6 · Refrigeración y agua de circulación
    ('TE-601', 'Temperatura agua de entrada',      'Temperatura', '°C',     6,    15.0,     0,     50,    NULL,  NULL,    28.0,    32.0),
    ('TE-602', 'Temperatura agua de salida',       'Temperatura', '°C',     6,    24.0,     0,     50,    NULL,  NULL,    33.0,    37.0),
    ('FT-603', 'Caudal de agua de circulación',    'Caudal',      'm³/s',   6,    42.0,     0,     70,    30.0,  25.0,    55.0,    60.0),
    ('VT-604', 'Vibración bomba de circulación',   'Vibración',   'mm/s',   6,     2.8,     0,     20,    NULL,  NULL,     7.1,    11.2),
    -- A7 · Sistema eléctrico y diésel de emergencia
    ('ET-701', 'Tensión de las barras de 6,6 kV',  'Tensión',     'kV',     7,     6.6,     0,      8,     6.2,   6.0,     7.0,     7.2),
    ('FT-702', 'Caudal de refrigeración del diésel','Caudal',     'm³/h',   7,    85.0,     0,    150,    60.0,  50.0,   120.0,   135.0),
    ('LT-703', 'Nivel del depósito de combustible','Nivel',       '%',      7,    92.0,     0,    100,    70.0,  50.0,    NULL,    NULL),
    ('TE-704', 'Temperatura del aceite del diésel','Temperatura', '°C',     7,    55.0,     0,    150,    NULL,  NULL,    85.0,    95.0),
    -- A8 · Protección radiológica y entorno
    ('RT-801', 'Dosis en la sala de control',      'Radiación',   'µSv/h',  8,    0.12,     0,   1000,    NULL,  NULL,     0.5,     2.5),
    ('RT-802', 'Dosis en el perímetro',            'Radiación',   'µSv/h',  8,    0.10,     0,   1000,    NULL,  NULL,     0.3,     1.0),
    ('WT-803', 'Velocidad del viento',             'Viento',      'm/s',    8,     3.5,     0,     60,    NULL,  NULL,    20.0,    30.0),
    ('TE-804', 'Temperatura ambiente',             'Temperatura', '°C',     8,    15.0,   -30,     50,    -5.0, -10.0,    38.0,    42.0),
    -- A9 · Red OT y ciberseguridad
    ('NT-901', 'Tráfico de la red OT',             'Tráfico',     'Mbit/s', 9,    85.0,     0,   1000,    NULL,  NULL,   400.0,   700.0),
    ('NT-902', 'Latencia de la pasarela',          'Latencia',    'ms',     9,     4.0,     0,   1000,    NULL,  NULL,    50.0,   200.0),
    ('NT-903', 'Conexiones rechazadas',            'Eventos',     '1/min',  9,     1.0,     0,  10000,    NULL,  NULL,    50.0,   200.0),
    ('NT-904', 'Paquetes con firma inválida',      'Eventos',     '1/min',  9,     0.0,     0,  10000,    NULL,  NULL,     1.0,     5.0);
