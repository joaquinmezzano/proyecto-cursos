-- Base de datos: institucion (owner: flowable)
-- Se crea en el mismo Postgres que usa Flowable:
--   docker exec -i flowable-postgres psql -U flowable -d postgres -c "CREATE DATABASE institucion"
--   docker exec -i flowable-postgres psql -U flowable -d institucion < bdd/institucion.sql

CREATE TABLE empresa (
    id_empresa       SERIAL PRIMARY KEY,
    nombre_empresa   VARCHAR(100) NOT NULL,
    persona_contacto VARCHAR(100),
    cuit             VARCHAR(20) UNIQUE,
    email_contacto   VARCHAR(100)
);

CREATE TABLE curso (
    id_curso               SERIAL PRIMARY KEY,
    id_empresa             INT NOT NULL REFERENCES empresa(id_empresa),
    -- id de la instancia de Process_Curso en Flowable (la web lo completa al iniciar el proceso)
    id_instancia           VARCHAR(64) UNIQUE,
    nombre                 VARCHAR(150) NOT NULL,
    descripcion            TEXT,
    programa               TEXT,
    presupuesto            NUMERIC(10, 2),
    fecha_inicio           DATE,
    fecha_posible_1        DATE,
    fecha_posible_2        DATE,
    otras_fechas           TEXT,
    informe_resultados     TEXT,
    estado                 VARCHAR(50) DEFAULT 'EN_TRAMITE'
        CHECK (estado IN ('EN_TRAMITE', 'EN_CURSO', 'FINALIZADO', 'CANCELADO',
                          'RECHAZADO', 'SIN_RESPUESTA', 'NO_VIABLE')),
    acceso_habilitado      BOOLEAN NOT NULL DEFAULT false,
    cantidad_participantes INT,
    fechas_preferidas      TEXT
);

-- cuenta con la que la empresa entra a la web (la crea HabilitarAccesoEmpresa: usuario = digitos del CUIT)
CREATE TABLE cuenta_empresa (
    id_empresa INT PRIMARY KEY REFERENCES empresa(id_empresa),
    usuario    VARCHAR(20) NOT NULL UNIQUE,
    salt       VARCHAR(32) NOT NULL,
    clave_hash CHAR(64) NOT NULL,
    fecha_alta TIMESTAMP NOT NULL DEFAULT now()
);
