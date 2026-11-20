package listeners;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.Set;

import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.ExecutionListener;

import db.ConexionDB;

/**
 * esta clase se ejecuta cuando finaliza un proceso y guarda en la variable
 * resultado el estado de como termino el proceso, y actualiza eso en la db
 */
public class ActualizarEstadoCurso implements ExecutionListener {

    private static final Set<String> RESULTADOS_VALIDOS = Set.of(
            "FINALIZADO", "CANCELADO", "RECHAZADO", "SIN_RESPUESTA", "NO_VIABLE"
    );

    @Override
    public void notify(DelegateExecution execution) {
        String idInstancia = execution.getProcessInstanceId();
        String resultado = (String) execution.getVariable("resultado");

        if (resultado == null || !RESULTADOS_VALIDOS.contains(resultado)) {
            log("instancia " + idInstancia + ": resultado ausente o invalido (" + resultado + "). No se actualiza la BD.");
            return;
        }

        Object idCursoVar = execution.getVariable("idCurso");
        boolean porIdCurso = idCursoVar instanceof Number;

        String sql = porIdCurso
                ? "UPDATE curso SET estado = ? WHERE id_curso = ?"
                : "UPDATE curso SET estado = ? WHERE id_instancia = ?";

        try (Connection conexion = ConexionDB.abrir();
             PreparedStatement actualizar = conexion.prepareStatement(sql)) {

            actualizar.setString(1, resultado);
            if (porIdCurso) {
                actualizar.setInt(2, ((Number) idCursoVar).intValue());
            } else {
                actualizar.setString(2, idInstancia);
            }

            int filas = actualizar.executeUpdate();
            if (filas == 0) {
                log("instancia " + idInstancia + ": no existe un curso vinculado en la BD.");
            } else {
                log("instancia " + idInstancia + " finalizada -> estado " + resultado);
            }

        } catch (SQLException e) {
            log("instancia " + idInstancia + ": error al actualizar la BD: " + e.getMessage());
        }
    }

    private void log(String mensaje) {
        System.out.println("[ActualizarEstadoCurso] " + mensaje);
    }
}