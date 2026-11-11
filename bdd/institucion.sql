-- bdd:
-- Database: institucion
-- Owner: flowable
CREATE TABLE empresa (
    id_empresa SERIAL PRIMARY KEY,
    nombre_empresa VARCHAR(100) NOT NULL,
    persona_contacto VARCHAR(100),
    usuario_flowable VARCHAR(50)
);

CREATE TABLE curso (
    id_curso SERIAL PRIMARY KEY,
    id_empresa INT NOT NULL,
    id_instancia VARCHAR(64),
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    programa TEXT,
    presupuesto NUMERIC(10, 2),
    fecha_inicio DATE,
    informe_resultados TEXT,
    estado VARCHAR(50) DEFAULT 'en_preparacion',

    CONSTRAINT fk_empresa
        FOREIGN KEY(id_empresa)
        REFERENCES empresa(id_empresa)
);
