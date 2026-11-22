import streamlit as st

from services import flowable


# Descargar pdf asi el cliente de la empresa lo analiza
def mostrar_documento(instance_id):
    st.markdown("### 📄 Documento de la propuesta seleccionada")
    pdf_bytes = flowable.descargar_pdf(instance_id)

    if pdf_bytes:
        st.download_button(
            label="📥 Descargar Propuesta Comercial (PDF)",
            data=pdf_bytes,
            file_name=f"Propuesta_{instance_id}.pdf",
            mime="application/pdf"
        )
        with st.expander("️Previsualizar propuesta", expanded=True):
            st.pdf(pdf_bytes, height=600)
    else:
        st.info("El documento PDF no está disponible para la instancia seleccionada")
