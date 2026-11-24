package delegates;

import java.time.OffsetDateTime;
import java.time.ZoneId;

import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.JavaDelegate;

/**
 * Service task "Enviar recordatorio". Se ejecuta cada vez que vence el plazo de 5 días
 * sin respuesta de la empresa: suma uno a "recordatorios" y guarda la fecha en "fechaUltimoRecordatorio".
 */
public class EnviarRecordatorio implements JavaDelegate {

    private static final String VAR_CANTIDAD = "recordatorios";
    private static final String VAR_FECHA = "fechaUltimoRecordatorio";
    private static final ZoneId ZONA = ZoneId.of("America/Argentina/Buenos_Aires");

    @Override
    public void execute(DelegateExecution execution) {
        Object actual = execution.getVariable(VAR_CANTIDAD);
        int cantidad = (actual instanceof Number ? ((Number) actual).intValue() : 0) + 1;
        String fecha = OffsetDateTime.now(ZONA).withNano(0).toString();

        execution.setVariable(VAR_CANTIDAD, cantidad);
        execution.setVariable(VAR_FECHA, fecha);

        Object empresa = execution.getVariable("nombreEmpresa");
        System.out.println("[Recordatorio] " + cantidad + "/2 enviado a "
                + (empresa != null ? empresa : "la empresa") + " el " + fecha
                + ": la propuesta sigue sin respuesta - instancia " + execution.getProcessInstanceId());
    }
}
