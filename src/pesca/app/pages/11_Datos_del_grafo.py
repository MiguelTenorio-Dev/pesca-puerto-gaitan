import streamlit as st

from pesca import config, grafo_datos
from pesca.app import comun

comun.configurar_pagina("Datos del grafo")
comun.barra_lateral()

st.title("Datos del grafo")
st.markdown(
    "De qué archivos sale el grafo y de dónde viene cada dato. "
    "🟢 MEDIDO = medido por el equipo en Google Earth · 🔵 DATO / OFICIAL = trabajo de campo o estadística pública · "
    "🟡 CALIBRADO = derivado de lo medido · 🟠 SIMULADO = supuesto del proyecto · 🔴 POR CONFIRMAR."
)

centros, nodos, aristas = config.cargar_centros_poblados(), config.cargar_nodos_grafo(), config.cargar_aristas()
tablas = {"Centros poblados": centros, "Nodos": nodos, "Arcos": aristas}

errores = grafo_datos.validar_esquema(nodos, aristas, centros)
for error in errores:
    st.error(error)

st.subheader("Filas por fuente")
resumen = grafo_datos.resumen_fuentes(tablas)
resumen.index = [comun.etiqueta(e) for e in resumen.index]
st.dataframe(resumen, width="stretch")

if any((t["validado"] == "no").any() for t in tablas.values()):
    st.warning(
        "Las filas con `validado = no` son **aproximadas o por confirmar**. "
        "Mientras llega el KML del equipo, el grafo es un esqueleto 🟠 SIMULADO que reproduce M01–M04."
    )

for pestana, (nombre, tabla) in zip(st.tabs(list(tablas)), tablas.items()):
    with pestana:
        vista = grafo_datos.con_etiqueta(tabla)
        vista["etiqueta"] = vista["etiqueta"].map(comun.etiqueta)
        st.dataframe(vista, hide_index=True, width="stretch")

st.subheader("Rutas medidas en el grafo")
st.dataframe(grafo_datos.comparar_medidas(aristas).round(2), hide_index=True, width="stretch")
st.caption("Para cambiar el grafo: deja los KML en `src/pesca/datos/grafo/kml/` y corre `python scripts/kml_a_grafo.py`.")
