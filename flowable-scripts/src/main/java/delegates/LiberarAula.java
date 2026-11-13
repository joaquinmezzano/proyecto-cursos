package delegates;

import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.JavaDelegate;

/**
 * Tarea de compensación "Liberar Aula". Simula avisar al web service de reservas
 * que el aula quedó libre y borra la variable "aulaAsignada".
 */
public class LiberarAula implements JavaDelegate {

    private static final String VAR_AULA = "aulaAsignada";

    @Override
    public void execute(DelegateExecution execution) {
        Object aula = execution.getVariable(VAR_AULA);
        System.out.println("[LiberarAula] instancia " + execution.getProcessInstanceId()
                + ": web service notificado, se libera " + aula);
        execution.removeVariable(VAR_AULA);
    }
}
