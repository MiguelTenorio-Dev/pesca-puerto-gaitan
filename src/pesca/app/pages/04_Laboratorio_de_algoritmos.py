import streamlit as st
from streamlit_folium import st_folium

from pesca import grafo, laboratorio, pesos, visualizacion
from pesca.app import comun

comun.configurar_pagina("Laboratorio de algoritmos")
escenario = comun.barra_lateral()

g = grafo.construir_grafo()
lugares = laboratorio.lugares(g)
lista = list(lugares)
ORIGEN, DESTINO = laboratorio.pares()[0]

st.title("Laboratorio de algoritmos")
st.markdown(
    "Elige de dónde a dónde y mira cómo busca cada algoritmo sobre el **grafo por capas**: cada lugar existe "
    "*con hielo*, *en frío* y *congelado*. **Dijkstra** expande primero lo que menos calidad ha perdido; **A\\*** hace "
    "lo mismo pero guiado hacia el destino; **BFS** busca la ruta con menos tramos sin mirar kilómetros, corriente ni deterioro."
)

c1, c2 = st.columns(2)
origen = c1.selectbox("Desde", lista, index=lista.index(ORIGEN), format_func=lugares.get, key="origen_lab")
destino = c2.selectbox("Hasta", lista, index=lista.index(DESTINO), format_func=lugares.get, key="destino_lab")
c1, c2, c3 = st.columns(3)
bote = c1.selectbox("Bote", list(comun.TEXTO_EMBARCACION), format_func=comun.TEXTO_EMBARCACION.get, key="bote_lab")
nevera = c2.selectbox("Nevera", list(pesos.NEVERAS), index=1, format_func=comun.TEXTO_NEVERA.get, key="nevera_lab")
algoritmo = c3.radio("Algoritmo", laboratorio.ALGORITMOS, format_func=comun.TEXTO_ALGORITMO.get, horizontal=True, key="algoritmo")
cond = pesos.condiciones(escenario, bote, nevera)

r = laboratorio.correr(algoritmo, g, origen, destino, cond)
if not r.alcanzable:
    st.error("No hay ruta con este bote y esta temporada (algún tramo es infactible o no hay conexión).")
else:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Calidad al llegar", f"{max(0.0, 1 - r.costo):.3f}")
    c2.metric("Horas", f"{r.horas:.1f}")
    c3.metric("km", f"{r.km:.1f}")
    c4.metric("Estados expandidos", r.nodos_expandidos)
    c5.metric("ms", f"{r.ms:.2f}")
    with st.container(border=True):
        st.markdown("**La ruta, tramo a tramo**")
        for linea in laboratorio.ruta_texto(g, r):
            st.markdown(f"- {linea}")
        st.caption("Estados del camino: " + " → ".join(f"{n} ({c})" for n, c in r.camino))

paso = st.slider("Ver la exploración paso a paso", 1, max(1, r.nodos_expandidos), max(1, r.nodos_expandidos), key="paso_lab") \
    if r.nodos_expandidos > 1 else None
st_folium(visualizacion.mapa_busqueda_capas(g, r, None if paso in (None, r.nodos_expandidos) else paso),
          height=440, use_container_width=True, returned_objects=[])
st.caption("Círculos: estados expandidos, de claro (primeros) a oscuro (últimos). Línea negra: la ruta encontrada.")

st.subheader("Dijkstra vs A* vs BFS")
tabla = laboratorio.comparar(g, cond)
st.dataframe(
    tabla.drop(columns=["origen", "destino"]).assign(algoritmo=tabla["algoritmo"].map(comun.TEXTO_ALGORITMO)),
    hide_index=True, width="stretch",
    column_config={"costo": st.column_config.NumberColumn("ΔQ", format="%.4f"), "horas": st.column_config.NumberColumn(format="%.2f"),
                   "km": st.column_config.NumberColumn(format="%.1f"), "ms": st.column_config.NumberColumn(format="%.3f"),
                   "pct_peor_que_dijkstra": st.column_config.NumberColumn("% peor que Dijkstra", format="%.1f")},
)
dij, ast = tabla[tabla["algoritmo"] == "dijkstra"], tabla[tabla["algoritmo"] == "a_estrella"]
menos = int((ast["nodos_expandidos"].to_numpy() <= dij["nodos_expandidos"].to_numpy()).sum())
st.markdown(f"A* llega al mismo costo que Dijkstra y expande igual o menos estados en **{menos} de {len(dij)}** pares. "
            "BFS usa menos tramos pero puede perder mucha más calidad.")

st.subheader("¿Cuánto vale poder pasar del río a la carretera?")
modos = laboratorio.por_modos(g, origen, destino, cond)
st.dataframe(modos, hide_index=True, width="stretch",
             column_config={"dq": st.column_config.NumberColumn("ΔQ", format="%.4f"), "calidad": st.column_config.NumberColumn(format="%.3f")})
valor = laboratorio.valor_transbordo(modos)
if valor == valor:
    st.markdown(f"El transbordo salva **{valor:.3f}** de calidad en esta ruta (solo río − río y vía).")
