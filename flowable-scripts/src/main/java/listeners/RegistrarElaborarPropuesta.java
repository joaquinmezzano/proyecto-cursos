package listeners;

import org.flowable.common.engine.api.FlowableException;
import org.flowable.engine.delegate.TaskListener;
import org.flowable.task.service.delegate.DelegateTask;

import java.math.BigDecimal;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Date;
import aux.GeneradorPdf;
import db.ConexionDB;

/**
 * el curso ya existe en la db desde el inicio de la instancia: lo crea la web
 * (website/company_learning.py) al enviar el formulario de solicitud y le guarda el id de la
 * instancia. Aca solo se actualiza esa fila con los datos de la propuesta y se genera el PDF.
 */
public class RegistrarElaborarPropuesta implements TaskListener {

    private static final DateTimeFormatter FORMATO_PDF = DateTimeFormatter.ofPattern("dd/MM/yyyy");
    private static final String SIN_OTRAS_FECHAS = "No se propusieron fechas nuevas";
    private static final BigDecimal PRESUPUESTO_MAXIMO = new BigDecimal("99999999.99");

    @Override
    public void notify(DelegateTask task) {
        String propuesta = textoOpcional(task.getVariable("programa"));
        BigDecimal presupuesto = parsearPresupuesto(task.getVariable("presupuesto"));

        if (presupuesto.signum() < 0 || presupuesto.compareTo(PRESUPUESTO_MAXIMO) > 0) {
            throw new FlowableException("Presupuesto fuera de rango: " + presupuesto.toPlainString()
                    + " (debe estar entre 0 y " + PRESUPUESTO_MAXIMO.toPlainString() + ")");
        }

        LocalDate fechaPosible1 = parsearFecha(task.getVariable("fechaposible1"), "fechaposible1");
        if (fechaPosible1 == null) {
            throw new FlowableException("La fecha posible 1 es obligatoria");
        }

        LocalDate fechaPosible2 = parsearFecha(task.getVariable("fechaposible2"), "fechaposible2");
        String otrasFechas = textoOpcional(task.getVariable("otrasfechasopcional"));
        String nombreCurso = textoOpcional(task.getVariable("nombreCurso"));

        String processInstanceId = task.getProcessInstanceId();

        byte[] pdfGenerado = GeneradorPdf.crearDocumento(
                propuesta != null ? propuesta : "",
                presupuesto.toPlainString(),
                fechaPosible1.format(FORMATO_PDF),
                fechaPosible2 != null ? fechaPosible2.format(FORMATO_PDF) : "",
                otrasFechas != null ? otrasFechas : SIN_OTRAS_FECHAS);
        if (pdfGenerado == null) {
            throw new FlowableException("No se pudo generar el PDF de la propuesta (ver el log)");
        }

        // COALESCE(?, nombre): si el formulario trae un nombre de curso, lo reemplaza;
        // si viene vacio, conserva el que se guardo al inicio (la tematica de la solicitud).
        String update = "UPDATE curso SET nombre = COALESCE(?, nombre), programa = ?, presupuesto = ?, "
                + "fecha_inicio = ?, fecha_posible_1 = ?, fecha_posible_2 = ?, otras_fechas = ? "
                + "WHERE id_instancia = ?";

        try (Connection conn = ConexionDB.abrir();
             PreparedStatement ps = conn.prepareStatement(update)) {

            ps.setString(1, nombreCurso);
            ps.setString(2, propuesta);
            ps.setBigDecimal(3, presupuesto);
            ps.setDate(4, java.sql.Date.valueOf(fechaPosible1));
            ps.setDate(5, java.sql.Date.valueOf(fechaPosible1));
            ps.setDate(6, aSqlDate(fechaPosible2));
            ps.setString(7, otrasFechas);
            ps.setString(8, processInstanceId);

            int filas = ps.executeUpdate();
            if (filas == 0) {
                // El curso deberia existir desde el inicio (lo crea la web al enviar la solicitud).
                // Si no esta, algo fallo antes: mejor avisar que crear un curso incompleto.
                throw new FlowableException("No existe un curso vinculado a la instancia " + processInstanceId);
            }

            System.out.println("[RegistrarElaborarPropuesta] propuesta guardada para la instancia " + processInstanceId);

        } catch (SQLException e) {
            // Se relanza para que la tarea no se complete si no se pudo guardar en la base
            throw new FlowableException("Error al guardar la propuesta en la base de datos: " + e.getMessage(), e);
        }

        task.setVariable("pdfPropuesta", pdfGenerado);
    }

    /** Devuelve el texto sin espacios de los extremos, o null si viene vacio. */
    private static String textoOpcional(Object valor) {
        if (valor == null) {
            return null;
        }
        String texto = valor.toString().trim();
        return texto.isEmpty() ? null : texto;
    }

    /** Convierte el presupuesto a BigDecimal con 2 decimales. Vacio = 0.00. */
    private static BigDecimal parsearPresupuesto(Object valor) {
        if (valor == null) {
            return new BigDecimal("0.00");
        }

        if (valor instanceof Number) {
            return new BigDecimal(valor.toString()).setScale(2, java.math.RoundingMode.HALF_UP);
        }

        String texto = valor.toString().trim().replace("$", "").replace(" ", "");
        if (texto.isEmpty()) {
            return new BigDecimal("0.00");
        }

        if (texto.contains(",")) {
            texto = texto.replace(".", "").replace(",", ".");
        }

        try {
            return new BigDecimal(texto).setScale(2, java.math.RoundingMode.HALF_UP);
        } catch (NumberFormatException e) {
            throw new FlowableException("Presupuesto invalido: '" + valor + "'");
        }
    }

    /** Convierte la variable de fecha del formulario a LocalDate. */
    private static LocalDate parsearFecha(Object valor, String nombreVariable) {
        if (valor == null) {
            return null;
        }

        if (valor instanceof Date) {
            return ((Date) valor).toInstant().atZone(ZoneId.systemDefault()).toLocalDate();
        }

        if (valor instanceof LocalDate) {
            return (LocalDate) valor;
        }

        if (valor instanceof LocalDateTime) {
            return ((LocalDateTime) valor).toLocalDate();
        }

        if (valor instanceof org.joda.time.LocalDate) {
            org.joda.time.LocalDate joda = (org.joda.time.LocalDate) valor;
            return LocalDate.of(joda.getYear(), joda.getMonthOfYear(), joda.getDayOfMonth());
        }

        String texto = valor.toString().trim();
        if (texto.isEmpty()) {
            return null;
        }

        try {
            return LocalDate.parse(texto); // yyyy-MM-dd
        } catch (DateTimeParseException ignorada) { }
        try {
            return LocalDate.parse(texto, FORMATO_PDF); // dd/MM/yyyy
        } catch (DateTimeParseException ignorada) { }
        try {
            return OffsetDateTime.parse(texto).atZoneSameInstant(ZoneId.systemDefault()).toLocalDate();
        } catch (DateTimeParseException ignorada) { }
        try {
            return Instant.parse(texto).atZone(ZoneId.systemDefault()).toLocalDate();
        } catch (DateTimeParseException ignorada) { }
        try {
            return LocalDateTime.parse(texto).toLocalDate();
        } catch (DateTimeParseException ignorada) { }

        throw new FlowableException("Fecha invalida en '" + nombreVariable + "': '" + texto + "'");
    }

    private static java.sql.Date aSqlDate(LocalDate fecha) {
        return fecha != null ? java.sql.Date.valueOf(fecha) : null;
    }
}