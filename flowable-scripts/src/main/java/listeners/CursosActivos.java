package listeners;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.flowable.common.engine.api.FlowableException;
import org.flowable.engine.RuntimeService;
import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.ExecutionListener;
import org.flowable.engine.impl.util.CommandContextUtil;
import org.flowable.engine.runtime.ProcessInstance;

import db.ConexionDB;

/**
 * Asigna a cantidadInstancias la cantidad de cursos que están 'EN_CURSO' en la
 * tabla curso Y cuya instancia de proceso sigue viva en flowable.
 */
public class CursosActivos implements ExecutionListener {

    private static final String VAR_DECISION_TABLE = "cantidadInstancias";

    private static final String PROCESS_KEY = "Process_Curso";

    private static final String COL_ID = "id_curso";
    private static final String COL_INSTANCIA = "id_instancia";

    // si esta en true corrige las instancias que no se cancelaron
    private static final boolean CORREGIR = true;
    private static final String ESTADO_CORREGIDO = "CANCELADO";

    @Override
    public void notify(DelegateExecution execution) {

        // instancias de este proceso que siguen vivas en el motor
        RuntimeService runtimeService =
                CommandContextUtil.getProcessEngineConfiguration().getRuntimeService();

        Set<String> instanciasVivas = new HashSet<>();
        for (ProcessInstance pi : runtimeService.createProcessInstanceQuery()
                .processDefinitionKey(PROCESS_KEY)
                .list()) {
            instanciasVivas.add(pi.getId());
        }

        int cantidad = 0;
        List<Long> huerfanos = new ArrayList<>();

        try (Connection c = ConexionDB.abrir()) {

            // cursos que la base dice que estan EN_CURSO
            try (PreparedStatement ps = c.prepareStatement(
                    "SELECT " + COL_ID + ", " + COL_INSTANCIA
                            + " FROM curso WHERE estado = 'EN_CURSO'");
                 ResultSet rs = ps.executeQuery()) {

                while (rs.next()) {
                    long idCurso = rs.getLong(1);
                    String idInstancia = rs.getString(2);

                    if (idInstancia != null && instanciasVivas.contains(idInstancia)) {
                        cantidad++;            // curso realmente activo
                    } else {
                        huerfanos.add(idCurso); // en la base si, en flowable no
                    }
                }
            }

            // corregir los que quedaron colgados
            if (CORREGIR && !huerfanos.isEmpty()) {
                try (PreparedStatement up = c.prepareStatement(
                        "UPDATE curso SET estado = ? WHERE " + COL_ID + " = ?")) {
                    for (Long id : huerfanos) {
                        up.setString(1, ESTADO_CORREGIDO);
                        up.setLong(2, id);
                        up.addBatch();
                    }
                    up.executeBatch();
                }
            }

        } catch (SQLException e) {
            throw new FlowableException("Error al contar los cursos en desarrollo", e);
        }

        execution.setVariable(VAR_DECISION_TABLE, cantidad);
    }
}