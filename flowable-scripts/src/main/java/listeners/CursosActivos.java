package listeners;

import java.util.List;

import org.flowable.engine.RuntimeService;
import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.ExecutionListener;
import org.flowable.engine.impl.util.CommandContextUtil;
import org.flowable.engine.runtime.ProcessInstance;

public class CursosActivos implements ExecutionListener {

    private static final String PROCESS_KEY = "Process_Curso";
    private static final String VAR_DECISION_TABLE = "cantidadInstancias";

    @Override
    public void notify(DelegateExecution execution) {
        int cantidad = 0;
        RuntimeService runtimeService = CommandContextUtil
                                        .getProcessEngineConfiguration()
                                        .getRuntimeService();
        List<ProcessInstance> cursosActivos = runtimeService.createProcessInstanceQuery()
                                                .processDefinitionKey(PROCESS_KEY)
                                                .list();
        String idActual = execution.getProcessInstanceId();

        for (ProcessInstance instancia : cursosActivos) {
            boolean igual = instancia.getId().equals(idActual);

            if (!igual) {
                cantidad++;
            }
        }

        execution.setVariable(VAR_DECISION_TABLE, cantidad);
    }

}
