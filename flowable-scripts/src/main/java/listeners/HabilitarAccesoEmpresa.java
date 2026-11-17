package listeners;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

import org.flowable.common.engine.api.FlowableException;
import org.flowable.engine.delegate.DelegateExecution;
import org.flowable.engine.delegate.JavaDelegate;

import db.ConexionDB;

public class HabilitarAccesoEmpresa implements JavaDelegate {

    private static final String CLAVE_POR_DEFECTO = "empresa123";

    @Override
    public void execute(DelegateExecution execution) {
        int idCurso = ((Number) execution.getVariable("idCurso")).intValue();
        int idEmpresa = ((Number) execution.getVariable("idEmpresa")).intValue();

        String usuario = null;
        boolean cuentaNueva = false;

        try (Connection c = ConexionDB.abrir()) {
            c.setAutoCommit(false);

            // ver si existe una cuenta ya para la empresa
            try (PreparedStatement ps = c.prepareStatement(
                    "SELECT usuario FROM cuenta_empresa WHERE id_empresa = ?")) {
                ps.setInt(1, idEmpresa);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) usuario = rs.getString(1);
                }
            }

            // si no existe, se crea con el CUIT como usuario y la clave por defecto
            if (usuario == null) {
                try (PreparedStatement ps = c.prepareStatement(
                        "SELECT cuit FROM empresa WHERE id_empresa = ?")) {
                    ps.setInt(1, idEmpresa);
                    try (ResultSet rs = ps.executeQuery()) {
                        if (!rs.next()) throw new FlowableException("No existe la empresa " + idEmpresa);
                        usuario = rs.getString(1).replaceAll("[^0-9]", "");
                    }
                }

                // salt se agrega para que no todas las empresas tengan la misma contraseña ya que por ahora es fija
                String salt = usuario;
                try (PreparedStatement ps = c.prepareStatement(
                        "INSERT INTO cuenta_empresa (id_empresa, usuario, salt, clave_hash) VALUES (?, ?, ?, ?)")) {
                    ps.setInt(1, idEmpresa);
                    ps.setString(2, usuario);
                    ps.setString(3, salt);
                    ps.setString(4, sha256(salt + CLAVE_POR_DEFECTO));
                    ps.executeUpdate();
                }
                cuentaNueva = true;
            }

            // vincular el curso con la cuenta
            try (PreparedStatement ps = c.prepareStatement(
                    "UPDATE curso SET acceso_habilitado = TRUE WHERE id_curso = ?")) {
                ps.setInt(1, idCurso);
                ps.executeUpdate();
            }

            c.commit();
        } catch (SQLException e) {
            throw new FlowableException("Error al habilitar el acceso de la empresa " + idEmpresa, e);
        }

        // comunicacion simulada de credenciales. aca la idea seria que si en un futuro
        // la contraseña se genera automatica, entonces poder ver su valor desde la
        // variable usuarioEmpresa dentro de flowable
        execution.setVariable("usuarioEmpresa", usuario);
    }

    // hash para las contraseñas
    private static String sha256(String texto) {
        try {
            byte[] h = MessageDigest.getInstance("SHA-256").digest(texto.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : h) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}