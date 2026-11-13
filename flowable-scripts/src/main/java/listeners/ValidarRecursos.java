package listeners;

import org.flowable.common.engine.api.FlowableException;
import org.flowable.engine.delegate.TaskListener;
import org.flowable.task.service.delegate.DelegateTask;

/**
 * Task listener del evento "complete" de la tarea Evaluar Recursos.
 * La consigna exige seleccionar al menos un recurso; si no se marca ninguno,
 * la compuerta inclusiva no tendría salida. Lanzar la excepción cancela el
 * completado y la tarea queda pendiente.
 */
public class ValidarRecursos implements TaskListener {

    @Override
    public void notify(DelegateTask task) {
        boolean aula = Boolean.TRUE.equals(task.getVariable("requiereAula"));
        boolean plataforma = Boolean.TRUE.equals(task.getVariable("requierePlataforma"));
        boolean equipamiento = Boolean.TRUE.equals(task.getVariable("requiereEquipamiento"));

        if (!aula && !plataforma && !equipamiento) {
            throw new FlowableException(
                    "Hay que seleccionar al menos un recurso: aula física, aula virtual o equipamiento especial");
        }

        System.out.println("[ValidarRecursos] instancia " + task.getProcessInstanceId()
                + ": aula=" + aula + ", plataforma=" + plataforma + ", equipamiento=" + equipamiento);
    }
}