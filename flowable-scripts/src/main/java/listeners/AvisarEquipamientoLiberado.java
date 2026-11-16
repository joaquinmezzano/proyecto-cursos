package listeners;

import java.util.List;

import org.flowable.engine.RuntimeService;
import org.flowable.engine.delegate.TaskListener;
import org.flowable.engine.impl.util.CommandContextUtil;
import org.flowable.engine.runtime.Execution;
import org.flowable.task.service.delegate.DelegateTask;

/**
 * Task listener del evento "complete" de la tarea de compensación "Liberar Equipamiento".
 *
 * En Flowable 6.8 los eventos que lanzan una compensación no esperan a que terminen
 * las tareas de compensación. Como "Liberar Equipamiento" es una tarea humana, el
 * proceso espera en una tarea de recepción cuyo id empieza con "EsperarLiberacion"
 * (una en la cancelación y otra al finalizar el curso). Este listener la libera cuando
 * un administrativo completa la tarea.
 */
public class AvisarEquipamientoLiberado implements TaskListener {

    private static final String PREFIJO_ESPERA = "EsperarLiberacion";

    @Override
    public void notify(DelegateTask task) {
        RuntimeService runtimeService = CommandContextUtil.getProcessEngineConfiguration().getRuntimeService();

        List<Execution> esperando = runtimeService.createExecutionQuery()
                .processInstanceId(task.getProcessInstanceId())
                .list();

        for (Execution execution : esperando) {
            String actividad = execution.getActivityId();
            if (actividad != null && actividad.startsWith(PREFIJO_ESPERA)) {
                System.out.println("[AvisarEquipamientoLiberado] instancia " + task.getProcessInstanceId()
                        + ": equipamiento liberado, se continúa desde " + actividad);
                runtimeService.trigger(execution.getId());
            }
        }
    }
}
