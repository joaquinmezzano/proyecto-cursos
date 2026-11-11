package listeners;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Types;

import org.flowable.common.engine.api.FlowableException;
import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.ExecutionListener;

import db.ConexionDB;

/**
 * esta clase se ejecuta apenas inicia una instancia, osea que
 * una vez tengamos la app, cuando una empresa mande una solicitud
 * lo primero que se va a ejecutar es esta clase asi podemos agregar a
 * la empresa a la bdd sin importar si era viable o no
 *   
 * Variables que espera (las envia el sitio web al iniciar la instancia):
 *      empresaNombre, empresaCuit, contactoNombre, contactoEmail,
 *      tematica, descripcion, cantidadParticipantes, fechasPreferidas
 */
public class RegistrarSolicitud implements ExecutionListener {

    @Override
    public void notify(DelegateExecution execution) {
        String idInstancia = execution.getProcessInstanceId();

        String empresaNombre = getVar(execution, "empresaNombre", null);
        String empresaCuit = getVar(execution, "empresaCuit", null);
        String contactoNombre = getVar(execution, "contactoNombre", null);
        String contactoEmail = getVar(execution, "contactoEmail", null);
        String tematica = getVar(execution, "tematica", null);
        String descripcion = getVar(execution, "descripcion", null);
        Integer participantes = entero(execution, "cantidadParticipantes");
        String fechasPreferidas = getVar(execution, "fechasPreferidas", null);

        try (Connection conexion = ConexionDB.abrir()) {
            int idEmpresa = buscarOCrearEmpresa(conexion, empresaNombre, empresaCuit, contactoNombre, contactoEmail);
            int idCurso = insertarCurso(conexion, idEmpresa, idInstancia, tematica, descripcion,
                    participantes, fechasPreferidas);

            log("instancia " + idInstancia + " -> curso " + idCurso + " (empresa " + idEmpresa + ")");

        } catch (SQLException e) {
            // este try and catch es mas que nada por si pasa algun error con la db, entonces
            // no se crea la instancia dentro de flowable directamente
            throw new FlowableException("No se pudo registrar la solicitud en la BD: " + e.getMessage(), e);
        }
    }

    private int buscarOCrearEmpresa(Connection conexion, String nombre, String cuit,
                                    String contacto, String email) throws SQLException {
        if (cuit != null) {
            String sqlBuscar = "SELECT id_empresa FROM empresa WHERE cuit = ?";
            try (PreparedStatement buscar = conexion.prepareStatement(sqlBuscar)) {
                buscar.setString(1, cuit);
                try (ResultSet rs = buscar.executeQuery()) {
                    if (rs.next()) {
                        return rs.getInt("id_empresa");
                    }
                }
            }
        }

        String sqlInsertar = "INSERT INTO empresa (nombre_empresa, cuit, persona_contacto, email_contacto) "
                + "VALUES (?, ?, ?, ?)";
        try (PreparedStatement insertar = conexion.prepareStatement(sqlInsertar, Statement.RETURN_GENERATED_KEYS)) {
            insertar.setString(1, nombre);
            insertar.setString(2, cuit);
            insertar.setString(3, contacto);
            insertar.setString(4, email);
            insertar.executeUpdate();
            return idGenerado(insertar);
        }
    }

    private int insertarCurso(Connection conexion, int idEmpresa, String idInstancia, String tematica,
                              String descripcion, Integer participantes, String fechasPreferidas)
            throws SQLException {
        String sql = "INSERT INTO curso (id_empresa, id_instancia, nombre, descripcion, "
                + "cantidad_participantes, fechas_preferidas) VALUES (?, ?, ?, ?, ?, ?)";

        try (PreparedStatement insertar = conexion.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
            insertar.setInt(1, idEmpresa);
            insertar.setString(2, idInstancia);
            insertar.setString(3, tematica);
            insertar.setString(4, descripcion);
            if (participantes != null) {
                insertar.setInt(5, participantes);
            } else {
                insertar.setNull(5, Types.INTEGER);
            }
            insertar.setString(6, fechasPreferidas);
            insertar.executeUpdate();
            return idGenerado(insertar);
        }
    }

    private int idGenerado(PreparedStatement sentencia) throws SQLException {
        try (ResultSet claves = sentencia.getGeneratedKeys()) {
            claves.next();
            return claves.getInt(1);
        }
    }

    // estas 2 funciones sirver para leer las variables ahora que todavia no tenemos la app
    // y poder probar el execution listener desde la UI de flowable
    private String getVar(DelegateExecution execution, String variable, String valorPorDefecto) {
        Object valor = execution.getVariable(variable);
        if (valor == null || valor.toString().isBlank()) {
            return valorPorDefecto;
        }
        return valor.toString().trim();
    }

    private Integer entero(DelegateExecution execution, String variable) {
        Object valor = execution.getVariable(variable);
        if (valor == null) {
            return null;
        }
        if (valor instanceof Number) {
            return ((Number) valor).intValue();
        }
        try {
            return Integer.parseInt(valor.toString().trim());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private void log(String mensaje) {
        System.out.println("[RegistrarSolicitud] " + mensaje);
    }
}