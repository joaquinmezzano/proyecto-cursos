package db;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/* la idea de esta clase es que cada vez que nos querramos
conectar a la db la usemos, asi no repetimos la conexion por todos lados */

public final class ConexionDB {

    private static final String URL = "jdbc:postgresql://postgres:5432/institucion";
    private static final String USUARIO = "flowable";
    private static final String CLAVE = "flow10";

    private ConexionDB() {
        // clase utilitaria: no se instancia
    }

    public static Connection abrir() throws SQLException {
        return DriverManager.getConnection(URL, USUARIO, CLAVE);
    }
}
