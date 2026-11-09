package listeners;

import org.flowable.engine.delegate.TaskListener;
import org.flowable.task.service.delegate.DelegateTask;

import java.text.SimpleDateFormat;
import java.util.Date;
import aux.GeneradorPdf;

public class RegistrarElaborarPropuesta implements TaskListener {

    @Override
    public void notify(DelegateTask task) {

        // Variables que vienen del formulario
        String propuesta = (String) task.getVariable("propuesta");
        Object presupuesto = task.getVariable("presupuesto");
        String presupuestoFormateado = presupuesto != null ? String.valueOf(presupuesto) : "0.00";
        Object fechaPosible1 = task.getVariable("fechaposible1");
        Object fechaPosible2 = task.getVariable("fechaposible2");

        SimpleDateFormat sdf = new SimpleDateFormat("dd/MM/yyyy");

        String fecha1Formateada = "";
        String fecha2Formateada = "";

        // Formateando fecha 1 y 2, para que sean legible en el PDF
        if (fechaPosible1 instanceof Date) {
            fecha1Formateada = sdf.format((Date) fechaPosible1);
        } else if (fechaPosible1 != null) { // por si lo deja como texto el motor de flowable
            fecha1Formateada = fechaPosible1.toString();
        }
        if (fechaPosible2 instanceof Date) {
            fecha2Formateada = sdf.format((Date) fechaPosible2);
        } else if (fechaPosible2 != null) {
            fecha2Formateada = fechaPosible2.toString();
        }

        Object otrasFechasPosibles = task.getVariable("otrasfechasopcional");
        String otrasFechas = otrasFechasPosibles != null ? otrasFechasPosibles.toString() : "No se propusieron fechas nuevas";

        System.out.println("Generando PDF...");
        byte[] pdfGenerado = GeneradorPdf.crearDocumento(propuesta, presupuestoFormateado, fecha1Formateada, fecha2Formateada, otrasFechas);

        task.setVariable("pdfPropuesta", pdfGenerado);
    }
}
