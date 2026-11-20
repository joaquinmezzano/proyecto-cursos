-- Database: institucion
-- Owner: flowable
CREATE TABLE empresa (
    id_empresa       SERIAL PRIMARY KEY,
    nombre_empresa   VARCHAR(100) NOT NULL,
    persona_contacto VARCHAR(100),
    cuit             VARCHAR(13) UNIQUE,
    email_contacto   VARCHAR(100)
);

CREATE TABLE curso (
    id_curso               SERIAL PRIMARY KEY,
    id_empresa             INT NOT NULL REFERENCES empresa(id_empresa),
    id_instancia           VARCHAR(64) UNIQUE,
    nombre                 VARCHAR(150) NOT NULL,
    descripcion            TEXT,
    programa               TEXT,
    presupuesto            NUMERIC(10, 2),
    fecha_inicio           DATE,
    informe_resultados     TEXT,
    estado                 VARCHAR(50) DEFAULT 'EN_TRAMITE'
    CHECK (estado IN ('EN_TRAMITE','EN_CURSO', 'FINALIZADO', 'CA    NCELADO',
        'RECHAZADO', 'SIN_RESPUESTA', 'NO_VIABLE')),
    fecha_posible_1        DATE,
    fecha_posible_2        DATE,
    otras_fechas           TEXT,
    cantidad_participantes INT,
    fechas_preferidas      TEXT,
    acceso_habilitado      BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE cuenta_empresa (
    id_empresa INT PRIMARY KEY REFERENCES empresa(id_empresa),
    usuario    VARCHAR(20) NOT NULL UNIQUE,
    salt       VARCHAR(32) NOT NULL,
    clave_hash CHAR(64) NOT NULL,
    fecha_alta TIMESTAMP NOT NULL DEFAULT now()
);