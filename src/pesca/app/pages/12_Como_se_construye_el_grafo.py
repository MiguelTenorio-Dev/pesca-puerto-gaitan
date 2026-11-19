import streamlit as st
from streamlit_folium import st_folium

from pesca import grafo, visualizacion
from pesca.app import comun

comun.configurar_pagina("Cómo se construye el grafo")
comun.barra_lateral()

ICONO_ESTADO = {"hecho": "✅", "simulado": "🟠", "pendiente": "⏳", "error": "❌"}

g = grafo.construir_grafo()
calibracion = grafo.calibrar(g)
validacion = grafo.validar_grafo(g)

st.title("Cómo se construye el grafo (1/2)")
st.markdown(
    "El grafo sale **solo de archivos**: `centros_poblados.csv`, `grafo/nodos.csv` y `grafo/aristas.csv`. "
    "Cada tramo de río se guarda una vez y el programa crea el de vuelta con la corriente al revés. "
    "Cada pueblo se parte en **entra → sale** para que esperar o almacenar ahí sea un arco más."
)

st.subheader("Los 7 pasos de la construcción")
for p in grafo.estado_pasos(g, validacion, calibracion).itertuples():
    st.markdown(f"{ICONO_ESTADO[p.estado]} **{p.paso}. {p.nombre}**: {p.detalle}")

st.subheader("Mapa")
st.caption("Flecha ► = sentido de la corriente. Color del río = de dónde sale el dato. Carreteras en gris punteado.")
st_folium(visualizacion.mapa_grafo(g), height=480, use_container_width=True, returned_objects=[])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Nodos", g.number_of_nodes())
c2.metric("Arcos (con sentido)", g.number_of_edges())
c3.metric("Componentes conexas", validacion.n_componentes)
c4.metric("Zonas que llegan a un pueblo", f"{validacion.alcanzabilidad.groupby('zona')['alcanzable'].any().sum()}")

st.subheader("Nodos y arcos")
que = st.radio("Ver", ["Nodos", "Arcos"], horizontal=True, key="que_ver")
tabla = grafo.tabla_nodos(g) if que == "Nodos" else grafo.tabla_arcos(g)
f1, f2 = st.columns(2)
tipos = f1.multiselect("Tipo", sorted(tabla["tipo"].unique()), key=f"tipos_{que}")
etiquetas = f2.multiselect("Fuente", sorted(tabla["etiqueta"].unique()), format_func=comun.etiqueta, key=f"etiquetas_{que}")
if tipos:
    tabla = tabla[tabla["tipo"].isin(tipos)]
if etiquetas:
    tabla = tabla[tabla["etiqueta"].isin(etiquetas)]
tabla = tabla.reset_index(drop=True)
vista = tabla.assign(etiqueta=tabla["etiqueta"].map(comun.etiqueta))
evento = st.dataframe(vista, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key=f"tabla_{que}")
filas = evento.selection.rows if evento is not None else []
if filas:
    fila = tabla.iloc[filas[0]]
    st.markdown(f"**{fila.iloc[0]}** · {comun.etiqueta(fila['etiqueta'])}: {fila['fuente']}")
    st.table(fila.astype(str).rename("valor"))
else:
    st.caption("Elige una fila para ver todos sus atributos y de dónde viene el dato.")

st.subheader("Validación")
if validacion.ok:
    st.success("Toda zona de pesca llega a algún pueblo y al mercado, ningún arco mide menos que la línea recta y el agua no une las cuencas.")
for error in validacion.errores:
    st.error(error)
with st.expander("¿Desde qué zona se llega a qué pueblo? (BFS)"):
    alc = validacion.alcanzabilidad.pivot(index="zona", columns="destino", values="tramos")
    st.dataframe(alc, width="stretch")
    st.caption("Número de tramos de la ruta con menos tramos; vacío = no se llega.")

st.subheader("¿El grafo reproduce lo medido? (Dijkstra por distancia)")
st.dataframe(
    calibracion.assign(modo=calibracion["modo"].map(comun.TEXTO_MODO)),
    hide_index=True,
    width="stretch",
    column_config={
        "km_medido": st.column_config.NumberColumn("km medidos", format="%.2f"),
        "km_grafo": st.column_config.NumberColumn("km en el grafo", format="%.2f"),
        "error_pct": st.column_config.NumberColumn("error (%)", format="%.3f"),
    },
)
