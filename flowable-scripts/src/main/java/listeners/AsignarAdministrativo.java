package listeners;

import java.util.List;

import org.flowable.engine.IdentityService;
import org.flowable.engine.ProcessEngineConfiguration;
import org.flowable.engine.TaskService;
import org.flowable.engine.delegate.TaskListener;
import org.flowable.engine.impl.util.CommandContextUtil;
import org.flowable.idm.api.User;
import org.flowable.task.service.delegate.DelegateTask;

public class AsignarAdministrativo implements TaskListener {

    private static final String GRUPO_ADMINISTRACION = "administracion";

    @Override
    public void notify(DelegateTask task) {
        ProcessEngineConfiguration config = CommandContextUtil.getProcessEngineConfiguration();
        IdentityService identityService = config.getIdentityService();
        TaskService taskService = config.getTaskService();

        List<User> administrativos = identityService.createUserQuery().memberOfGroup(GRUPO_ADMINISTRACION).orderByUserId().asc().list();

        // Sin integrantes no se puede asignar la tarea queda disponible para el grupo
        if (administrativos.isEmpty()) {
            System.out.println("[AsignarAdministrativo] el grupo '" + GRUPO_ADMINISTRACION + "' no tiene integrantes; la tarea " + task.getId() + " queda sin asignar");
            return;
        }

        String elegido = null;
        long menorCantidad = Long.MAX_VALUE;

        for (User usuario : administrativos) {
            long pendientes = taskService.createTaskQuery().taskAssignee(usuario.getId()).active().count();

            System.out.println("[AsignarAdministrativo] " + usuario.getId() + " tiene " + pendientes + " tareas pendientes");

            // Ante un empate se queda el primero en orden alfabetico
            if (pendientes < menorCantidad) {
                menorCantidad = pendientes;
                elegido = usuario.getId();
            }
        }

        task.setAssignee(elegido);

        System.out.println("[AsignarAdministrativo] tarea " + task.getId() + " de la instancia " + task.getProcessInstanceId() + " asignada a " + elegido + " (" + menorCantidad + " pendientes)");
    }
}
