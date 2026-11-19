import streamlit as st
from streamlit.errors import StreamlitPageNotFoundError

from pesca import decision
from pesca.app import comun

comun.configurar_pagina("Del dato a la decisión")
escenario = comun.barra_lateral()

st.title("Del dato a la decisión")
st.markdown("Cinco pasos, del archivo con coordenadas a la elección de los acopios. Cada uno con un número real del escenario activo.")

for paso in decision.recorrido(escenario):
    with st.container(border=True):
        st.subheader(f"{paso['n']}. {paso['titulo']}")
        st.markdown(paso["respuesta"])
        st.markdown(f"**Ejemplo:** {paso['ejemplo']}")
        try:
            st.page_link(paso["pagina"], label=f"Ver: {paso['enlace']}", icon="➡️")
        except StreamlitPageNotFoundError:  # la pagina se abrio sola (sin Inicio.py como entrada)
            st.markdown(f"➡️ Ver la pantalla **{paso['enlace']}** en el menú.")
