import streamlit as st
from streamlit_folium import st_folium

from pesca import grafo, visualizacion
from pesca.app import comun

comun.configurar_pagina("Mapa de la red")
comun.barra_lateral()

g = grafo.construir_grafo()
calibracion = grafo.calibrar(g)
validacion = grafo.validar_grafo(g)

st.title("Mapa de la red: ríos, carreteras y pueblos")
st.markdown(
    "El pescado se mueve por **río** (la flecha ► marca la corriente) y por **carretera** (gris punteado). "
    "El color del río dice **de dónde sale el dato**: 🟢 medido por el equipo en Google Earth (el Meta desde Puerto Gaitán "
    "hasta El Porvenir y las vías a San Pedro de Arimena, El Porvenir, La Cristalina y Domo Planas), 🟠 traza aproximada "
    "(el Meta alto, el Yucao y los caños, ajustados a las rutas medidas)."
)
st_folium(visualizacion.mapa_grafo(g), height=520, use_container_width=True, returned_objects=[])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Nodos", g.number_of_nodes())
c2.metric("Arcos (con sentido)", g.number_of_edges())
c3.metric("Pueblos en la red", len(grafo.candidatos(g)))
c4.metric("Zonas de pesca", sum(1 for _, a in g.nodes(data=True) if a["tipo"] == "zona_pesca"))

st.subheader("¿La red reproduce lo medido?")
st.dataframe(
    calibracion.assign(modo=calibracion["modo"].map(comun.TEXTO_MODO)).drop(columns=["ajuste"]),
    hide_index=True,
    width="stretch",
    column_config={
        "km_medido": st.column_config.NumberColumn("km medidos", format="%.2f"),
        "km_grafo": st.column_config.NumberColumn("km en la red", format="%.2f"),
        "error_pct": st.column_config.NumberColumn("diferencia (%)", format="%.2f"),
    },
)
st.caption(
    "Donde la ruta va por una traza KML del equipo **manda la traza**: la diferencia con la medición a mano solo se reporta "
    "(M04: la traza del Meta mide un poco menos que la medición con la regla de Google Earth). Las demás rutas se reproducen."
)
if validacion.ok:
    st.success("Toda zona de pesca llega a algún pueblo y a la plaza, y el agua no une la cuenca del Meta con la del Vichada.")
for error in validacion.errores:
    st.error(error)

st.caption("Detalle de cada nodo y arco: pantalla «Cómo se construye el grafo».")
