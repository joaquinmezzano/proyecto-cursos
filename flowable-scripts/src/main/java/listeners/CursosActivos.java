package listeners;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

import org.flowable.common.engine.api.FlowableException;
import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.ExecutionListener;

import db.ConexionDB;

/**
 *  asigna a cantidadInstancias la cantidad de cursos que en la tabla curso esten en 'EN_CURSO'
 */
public class CursosActivos implements ExecutionListener {

    private static final String VAR_DECISION_TABLE = "cantidadInstancias";

    @Override
    public void notify(DelegateExecution execution) {
        int cantidad = 0;

        try (Connection c = ConexionDB.abrir();
             PreparedStatement ps = c.prepareStatement(
                     "SELECT COUNT(*) FROM curso WHERE estado = 'EN_CURSO'");
             ResultSet rs = ps.executeQuery()) {

            if (rs.next()) {
                cantidad = rs.getInt(1);
            }

        } catch (SQLException e) {
            throw new FlowableException("Error al contar los cursos en desarrollo", e);
        }

        execution.setVariable(VAR_DECISION_TABLE, cantidad);
    }

}