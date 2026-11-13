package delegates;

import java.util.List;

import org.flowable.engine.RuntimeService;
import org.flowable.engine.delegate.BpmnError;
import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.JavaDelegate;
import org.flowable.engine.impl.util.CommandContextUtil;

/**
 * Service task "Reservar aula". Simula la conexión con un web service de reservas:
 * busca un aula que no esté asignada a otro curso activo y la guarda en "aulaAsignada".
 * Si no hay aulas libres lanza un BpmnError, que captura el evento de error
 * del subproceso "Preparar curso".
 */
public class ReservarAula implements JavaDelegate {

    private static final String PROCESS_KEY = "Process_Curso";
    private static final String VAR_AULA = "aulaAsignada";
    private static final List<String> AULAS = List.of("Aula 1", "Aula 2", "Aula 3");

    @Override
    public void execute(DelegateExecution execution) {
        String idInstancia = execution.getProcessInstanceId();
        log("instancia " + idInstancia + ": consultando disponibilidad al web service de aulas...");

        RuntimeService runtimeService = CommandContextUtil.getProcessEngineConfiguration().getRuntimeService();

        for (String aula : AULAS) {
            long ocupada = runtimeService.createProcessInstanceQuery()
                    .processDefinitionKey(PROCESS_KEY)
                    .variableValueEquals(VAR_AULA, aula)
                    .count();

            if (ocupada == 0) {
                execution.setVariable(VAR_AULA, aula);
                log("instancia " + idInstancia + ": reservada " + aula);
                return;
            }
        }

        log("instancia " + idInstancia + ": no hay aulas disponibles");
        throw new BpmnError("SIN_AULAS", "No hay aulas disponibles para el curso");
    }

    private void log(String mensaje) {
        System.out.println("[ReservarAula] " + mensaje);
    }
}
