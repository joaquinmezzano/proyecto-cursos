package app_materiales;
import org.flowable.engine.HistoryService;
import org.flowable.engine.history.HistoricProcessInstance;
import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import org.flowable.engine.IdentityService;
import org.flowable.engine.history.HistoricActivityInstance;
import java.util.Date;
import java.util.List;

public class HistorialEjecuciones {
    private final HistoryService historial;
    private final IdentityService identidad;

    public HistorialEjecuciones(HistoryService historial, IdentityService identidad) {
        this.historial = historial;
        this.identidad = identidad;
    }
    
    public void mostrarHistorial(JFrame frame) {
        Set<String> terminadas = new HashSet<>();
        for (HistoricProcessInstance instancia : historial.createHistoricProcessInstanceQuery()
            .processDefinitionKey("Process_Curso")
            .finished()
            .list()) {
            terminadas.add(instancia.getId());
        }
        Map<String, String> resultadoPorInstancia = new HashMap<>();
        if (!terminadas.isEmpty()) {
            for ( var variable : historial.createHistoricVariableInstanceQuery()
                .variableName("resultado")
                .excludeTaskVariables()
                .list()) {
                    String idInstancia = variable.getProcessInstanceId();
                    Object valor = variable.getValue();
                    if (terminadas.contains(idInstancia) && valor instanceof String) {
                        resultadoPorInstancia.put(idInstancia, (String) valor);
                    }
            }
        }

        Map<String, Integer> conteos = new HashMap<>();
        for(String resultado : resultadoPorInstancia.values()) {
            conteos.merge(resultado, 1, Integer::sum);
        }
        
        String[][] categorias = {
            {"FINALIZADO", "Curso finalizado"},
            {"CANCELADO", "Cancelacion"},
            {"RECHAZADO", "Rechazo de la propuesta"},
            {"NO_VIABLE", "Solicitud no viable"},
            {"SIN_RESPUESTA", "Cierre por falta de respuesta"}
        };

        DefaultTableModel modelo = new DefaultTableModel(new String[]{"Resultado", "Cantidad", "Porcentaje"}, 0) {
            @Override
            public boolean isCellEditable(int fila, int columna) {
                return false;
            }
        };

        int total = terminadas.size();
        int reconocidas = 0;

        for (String[] categoria : categorias) {
            int cantidad = conteos.getOrDefault(categoria[0], 0);
            modelo.addRow(new Object[] {
                categoria[1], cantidad, porcentaje(cantidad, total)
            });
            reconocidas += cantidad;
        }

        if(reconocidas < total) {
            int sinResultado = total - reconocidas;
            modelo.addRow(new Object[]{
                "Sin resultado reconocido", sinResultado, porcentaje(sinResultado, total)
            });
        }

        JTabbedPane pestanas = new JTabbedPane();
        pestanas.addTab("Resultados", new JScrollPane(new JTable(modelo)));
        pestanas.addTab("Preparacion paralela", tablaPreparacion());
        pestanas.addTab("Distribucion de tareas", tablaDistribucion());

        JDialog ventana = new JDialog(frame, "Analisis de ejecuciones", true);
        ventana.setDefaultCloseOperation(JDialog.DISPOSE_ON_CLOSE);
        ventana.setContentPane(pestanas);
        ventana.setSize(700, 350);
        ventana.setLocationRelativeTo(frame);
        ventana.setVisible(true);
    } 

    private String porcentaje(int cantidad, int total) {
        return total == 0 ? "—" : String.format("%.2f%%", 100.0 * cantidad / total);
    }

    private JScrollPane tablaPreparacion() {
        DefaultTableModel modelo = modeloHistorial(
            "Rama", "Promedio (Segundos)", "Preparaciones medidas"
        );

        Set<String> definiciones = new HashSet<>();
        for (HistoricProcessInstance instancia : historial.createHistoricProcessInstanceQuery()
            .processDefinitionKey("Process_Curso")
            .list()) {
                definiciones.add(instancia.getProcessDefinitionId());
        }

        Set<String> preparadas = new HashSet<>();
        for(String definicion : definiciones) {
            for (HistoricActivityInstance cierre : historial.createHistoricActivityInstanceQuery()
                .processDefinitionId(definicion)
                .activityId("SubFin")
                .finished()
                .list()) {
                    preparadas.add(cierre.getProcessInstanceId());
                }
        }

        long totalInscripciones = 0;
        long totalMateriales = 0;
        long totalRecursos = 0;
        int medidas = 0;

        for ( String idInstancia : preparadas) {
            Map<String, HistoricActivityInstance> actividades = new HashMap<>();
            for ( HistoricActivityInstance actividad : historial.createHistoricActivityInstanceQuery()
                .processInstanceId(idInstancia)
                .list()) {
                    actividades.put(actividad.getActivityId(), actividad);
            }
            
            Date ultimoFinRecurso = null;
            boolean recursoIncompleto = false;
            for (String idRecurso : List.of("Aula", "Virtual", "Equipo")) {
                HistoricActivityInstance recurso = actividades.get(idRecurso);
                if (recurso == null){
                    continue;
                }
                Date fin = recurso.getEndTime();
                if (fin == null) {
                    recursoIncompleto = true;
                    break;
                }
                if (ultimoFinRecurso == null || fin.after(ultimoFinRecurso)) {
                    ultimoFinRecurso = fin;
                }
            }

            long inscripciones = duracion(actividades.get("Nomina"), fin(actividades.get("Lista")));
            long materiales = duracion(actividades.get("Material"), fin(actividades.get("Material")));
            long recursos = duracion(actividades.get("Activity_12i2hpf"), ultimoFinRecurso);

            if (recursoIncompleto || inscripciones < 0 || materiales < 0 || recursos < 0) {
                continue;
            }

            totalInscripciones += inscripciones;
            totalMateriales += materiales;
            totalRecursos += recursos;
            medidas++;
        }

        modelo.addRow(new Object[]{"Inscripciones", promedioSegundos(totalInscripciones, medidas), medidas});
        modelo.addRow(new Object[]{"Maeriales", promedioSegundos(totalMateriales, medidas), medidas});
        modelo.addRow(new Object[]{"Recursos", promedioSegundos(totalRecursos, medidas), medidas});

        JPanel panel = new JPanel(new java.awt.BorderLayout());
        panel.add(new JScrollPane(new JTable(modelo)), java.awt.BorderLayout.CENTER);
        if (medidas < preparadas.size()) {
            panel.add(new JLabel("Preparaciones con historial incompleto: " + (preparadas.size() - medidas)), java.awt.BorderLayout.SOUTH);
        }

        return new JScrollPane(panel);
    }

    private Date fin(HistoricActivityInstance actividad) {
        return actividad == null ? null : actividad.getEndTime();
    }

    private long duracion(HistoricActivityInstance inicio, Date fin) {
        if (inicio == null || inicio.getStartTime() == null || fin == null) {
            return -1;
        }
        return fin.getTime() - inicio.getStartTime().getTime();
    }

    private String promedioSegundos(long totalMilisegundos, int cantidad) {
        return cantidad == 0? "—" : String.format("%.3f", totalMilisegundos / 1000.0 / cantidad);
    }

    private JScrollPane tablaDistribucion() {
        DefaultTableModel modelo = modeloHistorial(
            "Grupo", "Usuario Flowable", "Tareas completadas"
        );

        Map<String, String> gruposPorUsuario = new java.util.TreeMap<>();
        for(String grupo : List.of("administracion", "docentes")) {
            String nombreGrupo = grupo.equals("administracion") ? "Administración" : "Docentes";

            for (var usuario : identidad.createUserQuery().memberOfGroup(grupo).list()) {
                gruposPorUsuario.merge(usuario.getId(), nombreGrupo, (anterior, nuevo) -> anterior + ", " + nuevo);
            }
        }

        gruposPorUsuario.forEach((usuario, grupos) -> {
            long cantidad = historial.createHistoricTaskInstanceQuery()
                .processDefinitionKey("Process_Curso")
                .taskAssignee(usuario)
                .finished()
                .taskWithoutDeleteReason()
                .count();
            
            modelo.addRow(new Object[]{grupos, usuario, cantidad});
        });

        return new JScrollPane(new JTable(modelo));
    }

    private DefaultTableModel modeloHistorial(String... columnas) {
        return new DefaultTableModel(columnas, 0) {
            @Override
            public boolean isCellEditable(int fila, int columna){
                return false;
            } 
        };
    }


}
