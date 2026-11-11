package db;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/* la idea de esta clase es que cada vez que nos querramos
conectar a la db la usemos, asi no repetimos la conexion por todos lados */

public final class ConexionDB {

    private static final String URL =
            env("INSTITUCION_DB_URL", "jdbc:postgresql://postgres:5432/institucion");
    private static final String USUARIO =
            env("INSTITUCION_DB_USER", env("SPRING_DATASOURCE_USERNAME", "flowable"));
    private static final String CLAVE =
            env("INSTITUCION_DB_PASSWORD", env("SPRING_DATASOURCE_PASSWORD", ""));

    private ConexionDB() {
        // clase utilitaria: no se instancia
    }

    public static Connection abrir() throws SQLException {
        return DriverManager.getConnection(URL, USUARIO, CLAVE);
    }

    private static String env(String nombre, String porDefecto) {
        String valor = System.getenv(nombre);
        return valor != null && !valor.isEmpty() ? valor : porDefecto;
    }
}
