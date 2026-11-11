package listeners;

import org.flowable.engine.delegate.TaskListener;
import org.flowable.task.service.delegate.DelegateTask;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
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

        String processInstanceId = task.getProcessInstanceId();

        String dbUrl = "jdbc:postgresql://postgres:5432/institucion";
        String dbUser = "flowable";
        String dbPassword = "flow10";

        try (Connection conn = DriverManager.getConnection(dbUrl, dbUser, dbPassword)) {
            // Se actualiza la fila que coincida con la instancia actual de Flowable
            String sql = "UPDATE curso SET programa = ?, presupuesto = ?, fecha_inicio = ? WHERE process_instance_id = ?";
            try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
                pstmt.setString(1, propuesta);

                // Convertir el presupuesto a Double/BigDecimal si tu base de datos usa NUMERIC
                double presupuestoValor = presupuesto != null ? Double.parseDouble(presupuestoFormateado) : 0.0;
                pstmt.setDouble(2, presupuestoValor);

                // Guardamos la primera fecha posible como referencia (luego se pisa cuando la empresa acepte)
                if (fechaPosible1 instanceof Date) {
                    pstmt.setDate(3, new java.sql.Date(((Date) fechaPosible1).getTime()));
                } else {
                    pstmt.setNull(3, java.sql.Types.DATE);
                }

                pstmt.setString(4, processInstanceId);

                pstmt.executeUpdate();
                System.out.println("Base de datos actualizada correctamente para la instancia: " + processInstanceId);
            }
        } catch (SQLException e) {
            System.err.println("Error al actualizar la base de datos: " + e.getMessage());
            e.printStackTrace();
        }

        System.out.println("Generando PDF...");
        byte[] pdfGenerado = GeneradorPdf.crearDocumento(propuesta, presupuestoFormateado, fecha1Formateada, fecha2Formateada, otrasFechas);

        task.setVariable("pdfPropuesta", pdfGenerado);
    }
}
