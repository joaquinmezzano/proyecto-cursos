package listeners;

import org.flowable.common.engine.api.FlowableException;
import org.flowable.engine.ProcessEngineConfiguration;
import org.flowable.engine.delegate.TaskListener;
import org.flowable.engine.impl.util.CommandContextUtil;
import org.flowable.engine.runtime.ProcessInstance;
import org.flowable.idm.api.User;
import org.flowable.task.service.delegate.DelegateTask;

import java.math.BigDecimal;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Date;
import aux.GeneradorPdf;

public class RegistrarElaborarPropuesta implements TaskListener {

    // Se usan las mismas credenciales que el contenedor de Flowable usa para su propia base
    // (variables de entorno del docker-compose), así no hay contraseñas escritas en el código.
    // Se pueden sobrescribir con INSTITUCION_DB_URL / INSTITUCION_DB_USER / INSTITUCION_DB_PASSWORD.
    private static final String DB_URL = env("INSTITUCION_DB_URL", "jdbc:postgresql://postgres:5432/institucion");
    private static final String DB_USER = env("INSTITUCION_DB_USER", env("SPRING_DATASOURCE_USERNAME", "flowable"));
    private static final String DB_PASSWORD = env("INSTITUCION_DB_PASSWORD", env("SPRING_DATASOURCE_PASSWORD", ""));

    private static String env(String nombre, String porDefecto) {
        String valor = System.getenv(nombre);
        return valor != null && !valor.isEmpty() ? valor : porDefecto;
    }

    private static final DateTimeFormatter FORMATO_PDF = DateTimeFormatter.ofPattern("dd/MM/yyyy");
    private static final String SIN_OTRAS_FECHAS = "No se propusieron fechas nuevas";

    @Override
    public void notify(DelegateTask task) {

        // Variables que vienen del formulario, validadas y convertidas una sola vez.
        // Los mismos valores se usan para la base de datos y para el PDF.
        // En el formulario "elaborarPropuesta" el campo se llama "programa"
        String propuesta = textoOpcional(task.getVariable("programa"));
        BigDecimal presupuesto = parsearPresupuesto(task.getVariable("presupuesto"));
        LocalDate fechaPosible1 = parsearFecha(task.getVariable("fechaposible1"), "fechaposible1");
        if (fechaPosible1 == null) {
            throw new FlowableException("La fecha posible 1 es obligatoria");
        }
        LocalDate fechaPosible2 = parsearFecha(task.getVariable("fechaposible2"), "fechaposible2");
        String otrasFechas = textoOpcional(task.getVariable("otrasfechasopcional"));

        String processInstanceId = task.getProcessInstanceId();

        // Usuario de Flowable que inició el proceso (la empresa)
        ProcessEngineConfiguration config = CommandContextUtil.getProcessEngineConfiguration();
        ProcessInstance instancia = config.getRuntimeService()
                .createProcessInstanceQuery()
                .processInstanceId(processInstanceId)
                .singleResult();
        String usuarioEmpresa = instancia != null ? instancia.getStartUserId() : null;
        if (usuarioEmpresa == null) {
            throw new FlowableException("No se pudo determinar el usuario que inició la instancia " + processInstanceId);
        }

        String nombreCurso = textoOpcional(task.getVariable("nombreCurso"));
        if (nombreCurso == null) {
            nombreCurso = "Curso " + processInstanceId;
        }

        try (Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD)) {
            conn.setAutoCommit(false);

            int idEmpresa = obtenerOCrearEmpresa(conn, config, usuarioEmpresa);

            // Si la propuesta ya se registró (p. ej. se volvió a esta tarea), se actualiza; si no, se inserta.
            // fecha_inicio guarda la fecha posible 1 como referencia (luego se pisa cuando la empresa acepte).
            String update = "UPDATE curso SET programa = ?, presupuesto = ?, fecha_inicio = ?, "
                    + "fecha_posible_1 = ?, fecha_posible_2 = ?, otras_fechas = ? WHERE id_instancia = ?";
            int filas;
            try (PreparedStatement ps = conn.prepareStatement(update)) {
                ps.setString(1, propuesta);
                ps.setBigDecimal(2, presupuesto);
                ps.setDate(3, java.sql.Date.valueOf(fechaPosible1));
                ps.setDate(4, java.sql.Date.valueOf(fechaPosible1));
                ps.setDate(5, aSqlDate(fechaPosible2));
                ps.setString(6, otrasFechas);
                ps.setString(7, processInstanceId);
                filas = ps.executeUpdate();
            }

            if (filas == 0) {
                String insert = "INSERT INTO curso (id_empresa, id_instancia, nombre, programa, presupuesto, "
                        + "fecha_inicio, fecha_posible_1, fecha_posible_2, otras_fechas) "
                        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";
                try (PreparedStatement ps = conn.prepareStatement(insert)) {
                    ps.setInt(1, idEmpresa);
                    ps.setString(2, processInstanceId);
                    ps.setString(3, nombreCurso);
                    ps.setString(4, propuesta);
                    ps.setBigDecimal(5, presupuesto);
                    ps.setDate(6, java.sql.Date.valueOf(fechaPosible1));
                    ps.setDate(7, java.sql.Date.valueOf(fechaPosible1));
                    ps.setDate(8, aSqlDate(fechaPosible2));
                    ps.setString(9, otrasFechas);
                    ps.executeUpdate();
                }
            }

            conn.commit();
            System.out.println("Curso registrado para la instancia " + processInstanceId
                    + " (empresa " + idEmpresa + ", usuario " + usuarioEmpresa + ")");
        } catch (SQLException e) {
            // Se relanza para que la tarea no se complete si no se pudo guardar en la base
            throw new FlowableException("Error al guardar el curso en la base de datos: " + e.getMessage(), e);
        }

        System.out.println("Generando PDF...");
        byte[] pdfGenerado = GeneradorPdf.crearDocumento(
                propuesta != null ? propuesta : "",
                presupuesto.toPlainString(),
                fechaPosible1.format(FORMATO_PDF),
                fechaPosible2 != null ? fechaPosible2.format(FORMATO_PDF) : "",
                otrasFechas != null ? otrasFechas : SIN_OTRAS_FECHAS);

        task.setVariable("pdfPropuesta", pdfGenerado);
    }

    /** Devuelve el texto sin espacios de los extremos, o null si viene vacío. */
    private static String textoOpcional(Object valor) {
        if (valor == null) {
            return null;
        }
        String texto = valor.toString().trim();
        return texto.isEmpty() ? null : texto;
    }

    /** Convierte el presupuesto a BigDecimal con 2 decimales. Vacío = 0.00. */
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
        // Formato argentino "1.500,50": se quitan los puntos de miles y la coma pasa a ser decimal
        if (texto.contains(",")) {
            texto = texto.replace(".", "").replace(",", ".");
        }
        try {
            return new BigDecimal(texto).setScale(2, java.math.RoundingMode.HALF_UP);
        } catch (NumberFormatException e) {
            throw new FlowableException("Presupuesto inválido: '" + valor + "'");
        }
    }

    /**
     * Convierte la variable de fecha del formulario a LocalDate.
     * Acepta Date, LocalDate, LocalDateTime o texto (yyyy-MM-dd, dd/MM/yyyy o ISO con hora).
     * Devuelve null si viene vacía; lanza error si no se puede interpretar.
     */
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

        throw new FlowableException("Fecha inválida en '" + nombreVariable + "': '" + texto + "'");
    }

    private static java.sql.Date aSqlDate(LocalDate fecha) {
        return fecha != null ? java.sql.Date.valueOf(fecha) : null;
    }

    /**
     * Busca la empresa por usuario_flowable. Si no existe, la crea usando
     * los datos del usuario en el IDM de Flowable.
     */
    private int obtenerOCrearEmpresa(Connection conn, ProcessEngineConfiguration config, String usuario) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(
                "SELECT id_empresa FROM empresa WHERE usuario_flowable = ?")) {
            ps.setString(1, usuario);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return rs.getInt(1);
                }
            }
        }

        // No existe: se registra con los datos del usuario de Flowable
        User user = config.getIdentityService().createUserQuery().userId(usuario).singleResult();
        String nombreEmpresa = usuario;
        String contacto = null;
        if (user != null) {
            String nombreCompleto = ((user.getFirstName() != null ? user.getFirstName() : "") + " "
                    + (user.getLastName() != null ? user.getLastName() : "")).trim();
            if (!nombreCompleto.isEmpty()) {
                nombreEmpresa = nombreCompleto;
            }
            contacto = user.getEmail();
        }

        try (PreparedStatement ps = conn.prepareStatement(
                "INSERT INTO empresa (nombre_empresa, persona_contacto, usuario_flowable) VALUES (?, ?, ?)",
                Statement.RETURN_GENERATED_KEYS)) {
            ps.setString(1, nombreEmpresa);
            ps.setString(2, contacto);
            ps.setString(3, usuario);
            ps.executeUpdate();
            try (ResultSet rs = ps.getGeneratedKeys()) {
                rs.next();
                return rs.getInt(1);
            }
        }
    }
}
