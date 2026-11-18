package app_materiales;

import org.flowable.engine.IdentityService;
import org.flowable.engine.ProcessEngine;
import org.flowable.engine.ProcessEngineConfiguration;
import org.flowable.engine.TaskService;
import org.flowable.engine.impl.cfg.StandaloneProcessEngineConfiguration;
import org.flowable.task.api.Task;

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.util.List;
import java.util.Map;

public class AppMateriales {

    private static final String DB_URL = "jdbc:postgresql://localhost:5434/flowable";
    private static final String DB_USER = "flowable";
    private static final String DB_PASS = "flow10";

    private static final String GRUPO_ADMIN = "administracion";
    private static final String TASK_KEY_MATERIALES = "Material"; //id de la tarea

    private final ProcessEngine processEngine;
    private final IdentityService identityService;
    private final TaskService taskService;

    private String usuarioLogueado;
    private JFrame frame;
    private DefaultTableModel modeloAsignadas;
    private DefaultTableModel modeloDisponibles;
    private JTable tablaAsignadas;
    private JTable tablaDisponibles;

    public AppMateriales() {
        // processEngine conectado a postgres
        ProcessEngineConfiguration cfg = new StandaloneProcessEngineConfiguration()
                .setJdbcUrl(DB_URL)
                .setJdbcUsername(DB_USER)
                .setJdbcPassword(DB_PASS)
                .setJdbcDriver("org.postgresql.Driver")
                .setDatabaseSchemaUpdate(ProcessEngineConfiguration.DB_SCHEMA_UPDATE_FALSE);

        this.processEngine = cfg.buildProcessEngine();
        this.identityService = processEngine.getIdentityService();
        this.taskService = processEngine.getTaskService();
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            try {
                AppMateriales app = new AppMateriales();
                app.mostrarLogin();
            } catch (Exception e) {
                JOptionPane.showMessageDialog(null,
                        "Error al conectar con el motor Flowable:\n" + e.getMessage(),
                        "Error de conexión", JOptionPane.ERROR_MESSAGE);
            }
        });
    }

    // login usando identityservice
    private void mostrarLogin() {
        JFrame loginFrame = new JFrame("Preparación de Materiales");
        loginFrame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        loginFrame.setSize(400, 220);
        loginFrame.setLocationRelativeTo(null);

        JPanel panel = new JPanel(new GridLayout(4, 2, 10, 10));
        panel.setBorder(BorderFactory.createEmptyBorder(20, 20, 20, 20));

        JTextField txtUsuario = new JTextField();
        JPasswordField txtClave = new JPasswordField();
        JButton btnIngresar = new JButton("Ingresar");

        panel.add(new JLabel("Usuario Flowable:"));
        panel.add(txtUsuario);
        panel.add(new JLabel("Contraseña:"));
        panel.add(txtClave);
        panel.add(new JLabel(""));
        panel.add(btnIngresar);

        btnIngresar.addActionListener(e -> {
            String user = txtUsuario.getText().trim();
            String pass = new String(txtClave.getPassword());

            if (user.isEmpty() || pass.isEmpty()) {
                JOptionPane.showMessageDialog(loginFrame, "Complete usuario y contraseña.");
                return;
            }

            // verificacion datos en ACT_ID_USER y pertenencia al grupo administracion.
            if (autenticarAdministrativo(user, pass)) {
                this.usuarioLogueado = user;
                loginFrame.dispose();
                mostrarPanelTareas();
            } else {
                JOptionPane.showMessageDialog(loginFrame,
                        "Credenciales inválidas o el usuario no pertenece al grupo administracion.",
                        "Acceso denegado", JOptionPane.WARNING_MESSAGE);
            }
        });

        loginFrame.add(panel);
        loginFrame.setVisible(true);
    }

    private boolean autenticarAdministrativo(String usuarioId, String password) {
        if (!identityService.checkPassword(usuarioId, password)) {
            return false;
        }
        // identityservice
        long perteneceAdmin = identityService.createGroupQuery()
                .groupMember(usuarioId)
                .groupId(GRUPO_ADMIN)
                .count();
        return perteneceAdmin > 0;
    }

    // gestionando la tarea preparar materiales, pueden ser en diferentes instancias, usando taskservice
    private void mostrarPanelTareas() {
        frame = new JFrame("Preparación de Materiales, usuario: " + usuarioLogueado);
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(800, 520);
        frame.setLocationRelativeTo(null);
        frame.setLayout(new BorderLayout(10, 10));

        JPanel topPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        JButton btnActualizar = new JButton("🔄 Actualizar");
        JButton btnSalir = new JButton("Cerrar sesión");
        topPanel.add(new JLabel("Sesión activa: " + usuarioLogueado + "   "));
        topPanel.add(btnActualizar);
        topPanel.add(btnSalir);
        frame.add(topPanel, BorderLayout.NORTH);

        // panel central
        JPanel centerPanel = new JPanel(new GridLayout(2, 1, 10, 10));
        centerPanel.setBorder(BorderFactory.createEmptyBorder(0, 15, 10, 15));

        String[] columnas = {"ID Tarea", "Instancia", "ID Curso", "Temática", "Empresa", "Cantidad de participantes"};

        // asignar tarea/s
        modeloAsignadas = new DefaultTableModel(columnas, 0) {
            @Override public boolean isCellEditable(int row, int col) { return false; }
        };
        tablaAsignadas = new JTable(modeloAsignadas);
        JPanel panelAsignadas = new JPanel(new BorderLayout(5, 5));
        panelAsignadas.setBorder(BorderFactory.createTitledBorder("Tareas Preparar materiales asignadas"));
        panelAsignadas.add(new JScrollPane(tablaAsignadas), BorderLayout.CENTER);
        JButton btnCompletar = new JButton("Completar tarea seleccionada");
        panelAsignadas.add(btnCompletar, BorderLayout.SOUTH);

        // tarea/s disponible/s
        modeloDisponibles = new DefaultTableModel(columnas, 0) {
            @Override public boolean isCellEditable(int row, int col) { return false; }
        };
        tablaDisponibles = new JTable(modeloDisponibles);
        JPanel panelDisponibles = new JPanel(new BorderLayout(5, 5));
        panelDisponibles.setBorder(BorderFactory.createTitledBorder("Disponibles para el grupo administracion"));
        panelDisponibles.add(new JScrollPane(tablaDisponibles), BorderLayout.CENTER);
        JButton btnReclamar = new JButton("Reclamar tarea seleccionada");
        panelDisponibles.add(btnReclamar, BorderLayout.SOUTH);

        centerPanel.add(panelAsignadas);
        centerPanel.add(panelDisponibles);
        frame.add(centerPanel, BorderLayout.CENTER);

        // eventos
        btnActualizar.addActionListener(e -> recargarTablas());
        btnSalir.addActionListener(e -> {
            usuarioLogueado = null;
            frame.dispose();
            mostrarLogin();
        });

        btnReclamar.addActionListener(e -> {
            int fila = tablaDisponibles.getSelectedRow();
            if (fila == -1) {
                JOptionPane.showMessageDialog(frame, "Seleccione una tarea para reclamar.");
                return;
            }
            String taskId = (String) modeloDisponibles.getValueAt(fila, 0);
            try {
                taskService.claim(taskId, usuarioLogueado);
                JOptionPane.showMessageDialog(frame, "Tarea reclamada correctamente.");
                recargarTablas();
            } catch (Exception ex) {
                JOptionPane.showMessageDialog(frame, "No se pudo reclamar: " + ex.getMessage(),
                        "Aviso", JOptionPane.WARNING_MESSAGE);
                recargarTablas();
            }
        });

        btnCompletar.addActionListener(e -> {
            int fila = tablaAsignadas.getSelectedRow();
            if (fila == -1) {
                JOptionPane.showMessageDialog(frame, "Seleccione una tarea asignada para completar.");
                return;
            }
            String taskId = (String) modeloAsignadas.getValueAt(fila, 0);
            try {
                taskService.complete(taskId);
                JOptionPane.showMessageDialog(frame, "Tarea Preparar materiales completada.");
                recargarTablas();
            } catch (Exception ex) {
                JOptionPane.showMessageDialog(frame, "Error al completar la tarea: " + ex.getMessage(),
                        "Error", JOptionPane.ERROR_MESSAGE);
            }
        });

        recargarTablas();
        frame.setVisible(true);
    }

    private void recargarTablas() {
        modeloAsignadas.setRowCount(0);
        modeloDisponibles.setRowCount(0);

        // consultar asignadas
        List<Task> asignadas = taskService.createTaskQuery()
                .taskDefinitionKey(TASK_KEY_MATERIALES)
                .taskAssignee(usuarioLogueado)
                .includeProcessVariables()
                .orderByTaskCreateTime().asc()
                .list();

        for (Task t : asignadas) {
            modeloAsignadas.addRow(extraerFila(t));
        }

        // Consultar disponibles
        List<Task> disponibles = taskService.createTaskQuery()
                .taskDefinitionKey(TASK_KEY_MATERIALES)
                .taskCandidateUser(usuarioLogueado)
                .taskUnassigned()
                .includeProcessVariables()
                .orderByTaskCreateTime().asc()
                .list();

        for (Task t : disponibles) {
            modeloDisponibles.addRow(extraerFila(t));
        }
    }

    private Object[] extraerFila(Task t) {
        Map<String, Object> vars = t.getProcessVariables();
        return new Object[]{
                t.getId(),
                t.getProcessInstanceId(),
                vars.getOrDefault("idCurso", "-"),
                vars.getOrDefault("tematica", "Sin temática"),
                vars.getOrDefault("nombreEmpresa", "Sin empresa"),
                vars.getOrDefault("cantidadParticipantes", "A confirmar")
        };
    }
}