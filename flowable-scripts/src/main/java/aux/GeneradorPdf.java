package aux;

import com.lowagie.text.Document;
import com.lowagie.text.Paragraph;
import com.lowagie.text.pdf.PdfWriter;
import java.io.ByteArrayOutputStream;

public class GeneradorPdf {

    public static byte[] crearDocumento(String propuesta, String presupuesto, String fechaposible1, String fechaposible2, String fechasPosibles) {
        try (ByteArrayOutputStream baos = new ByteArrayOutputStream()) {

            Document document = new Document();
            PdfWriter.getInstance(document, baos);
            document.open();

            document.add(new Paragraph("\nPropuesta: " + propuesta));
            document.add(new Paragraph("Presupuesto: $" + presupuesto));
            document.add(new Paragraph("Fechas posibles: " + fechaposible1 + " | " + fechaposible2));
            document.add(new Paragraph("Notas extras: " + fechasPosibles));

            document.close();

            return baos.toByteArray();

        } catch (Exception e) {
            e.printStackTrace();
            return null;
        }
    }
}
