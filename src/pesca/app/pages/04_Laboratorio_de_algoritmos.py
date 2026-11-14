import streamlit as st
from streamlit_folium import st_folium

from pesca import busqueda, red, transporte, visualizacion
from pesca.app import comun
from pesca.escenario import Escenario

comun.configurar_pagina("Laboratorio de algoritmos")
escenario = comun.barra_lateral()

ORIGEN_INICIAL, DESTINO_INICIAL = busqueda.pares_comparacion()[0]


@st.cache_data
def buscar(origen: str, destino: str, embarcacion: str, criterio: str, esc: Escenario) -> dict:
    perfil = transporte.Perfil.desde_escenario(esc, embarcacion)
    grafo = red.construir_red()
    return {a: busqueda.correr(a, grafo, origen, destino, perfil, criterio) for a in busqueda.ALGORITMOS}


@st.cache_data
def comparar(embarcacion: str, criterio: str, esc: Escenario):
    perfil = transporte.Perfil.desde_escenario(esc, embarcacion)
    return busqueda.comparar(red.construir_red(), busqueda.pares_comparacion(), perfil, criterio)


grafo = red.construir_red()
opciones = red.opciones_lugares(grafo)
lista = list(opciones)

st.title("Laboratorio de algoritmos")
st.markdown(
    "Elige de dónde a dónde y mira cómo busca cada algoritmo. "
    "**Dijkstra** revisa todo lo que está más cerca que el destino; **A\\*** hace lo mismo pero se guía "
    "hacia el destino y revisa menos lugares; **BFS** busca la ruta con menos tramos, sin mirar kilómetros, "
    "corriente ni deterioro."
)

c1, c2, c3 = st.columns(3)
origen = c1.selectbox("Desde", lista, index=lista.index(ORIGEN_INICIAL), format_func=opciones.get)
destino = c2.selectbox("Hasta", lista, index=lista.index(DESTINO_INICIAL), format_func=opciones.get)
embarcacion = c3.selectbox("Embarcación", transporte.embarcaciones(), format_func=comun.TEXTO_EMBARCACION.get)
c1, c2 = st.columns(2)
criterio = c1.radio("Qué se minimiza", transporte.CRITERIOS, format_func=comun.TEXTO_CRITERIO.get, horizontal=True)
algoritmo = c2.radio("Algoritmo", busqueda.ALGORITMOS, format_func=comun.TEXTO_ALGORITMO.get, horizontal=True, key="algoritmo")

resultados = buscar(origen, destino, embarcacion, criterio, escenario)
res = resultados[algoritmo]
perfil = transporte.Perfil.desde_escenario(escenario, embarcacion)

paso = res.n_explorados
if res.n_explorados > 1:
    paso = st.slider(
        "Paso de la exploración (cuántos lugares lleva revisados)", 1, res.n_explorados, res.n_explorados,
        help="Mueve el control para ver en qué orden revisa los lugares el algoritmo.",
    )
st_folium(visualizacion.mapa_busqueda(grafo, res, paso), height=500, use_container_width=True, returned_objects=[])
st.caption(
    "Círculos: lugares revisados, de claro (primeros) a oscuro (últimos). "
    "Ruta: 🟢 a favor de la corriente · 🔴 contra la corriente · ⚫ carretera (punteada) · 🟣 transbordo."
)

if not res.alcanzable:
    st.error(f"No hay ruta factible. {transporte.motivo_infactible(grafo, origen, destino, perfil)}")
else:
    columnas = st.columns(3)
    optimo = resultados["dijkstra"].costo
    for col, (nombre, r) in zip(columnas, resultados.items()):
        resumen = transporte.resumen_ruta(grafo, r.ruta, perfil)
        col.markdown(f"**{comun.TEXTO_ALGORITMO[nombre]}**")
        col.metric("Lugares revisados", r.n_explorados)
        col.metric(
            "Horas de viaje", f"{resumen['horas']:.1f}",
            delta=f"{100 * (r.costo - optimo) / optimo:+.0f} % de costo frente a Dijkstra" if optimo > 0 and r.costo > optimo * (1 + 1e-9) else None,
            delta_color="inverse",
        )
        col.metric("Calidad al llegar (solo el viaje)", f"{resumen['calidad_viaje']:.2f}")
        col.caption(f"{r.tramos} tramos · {resumen['km']:.1f} km · {resumen['pct_contra_corriente']:.0f} % del río contra corriente")

    st.markdown(f"**Tramos de la ruta de {comun.TEXTO_ALGORITMO[algoritmo]}**")
    tramos = transporte.tramos_ruta(grafo, res.ruta, perfil)
    st.dataframe(
        tramos.assign(modo=tramos["modo"].map(comun.TEXTO_MODO), sentido=tramos["sentido"].map(comun.TEXTO_SENTIDO)),
        hide_index=True,
        width="stretch",
        column_config={
            "km": st.column_config.NumberColumn(format="%.1f"),
            "horas": st.column_config.NumberColumn(format="%.2f"),
            "perdida": st.column_config.NumberColumn("pérdida de calidad", format="%.4f"),
        },
    )

st.subheader(f"Dijkstra vs A* vs BFS en {len(busqueda.pares_comparacion())} pares de prueba")
tabla = comparar(embarcacion, criterio, escenario)
st.dataframe(
    tabla.drop(columns=["origen", "destino"]).assign(algoritmo=tabla["algoritmo"].map(comun.TEXTO_ALGORITMO)),
    hide_index=True,
    width="stretch",
    column_config={
        "costo": st.column_config.NumberColumn(comun.TEXTO_CRITERIO[criterio].lower(), format="%.4f"),
        "nodos_explorados": "lugares revisados",
        "ms": st.column_config.NumberColumn("milisegundos", format="%.3f"),
        "pct_peor_que_dijkstra": st.column_config.NumberColumn("% peor que Dijkstra", format="%.1f"),
        "horas": st.column_config.NumberColumn(format="%.1f"),
        "km": st.column_config.NumberColumn(format="%.1f"),
    },
)
resumen = tabla.groupby("algoritmo")[["nodos_explorados", "pct_peor_que_dijkstra"]].mean()
st.markdown(
    f"- **A\\*** encuentra siempre el mismo costo que Dijkstra y revisa en promedio "
    f"**{resumen.at['a_estrella', 'nodos_explorados']:.1f}** lugares frente a "
    f"**{resumen.at['dijkstra', 'nodos_explorados']:.1f}** de Dijkstra.\n"
    f"- **BFS** queda en promedio **{resumen.at['bfs', 'pct_peor_que_dijkstra']:.1f} %** peor: "
    "prefiere la ruta con menos tramos aunque vaya contra la corriente o sea más larga. Por eso no sirve aquí."
)
st.caption(
    f"{comun.etiqueta('SIMULADO')}: velocidades, corriente y temperaturas. "
    "Heurística de A*: distancia en línea recta ÷ velocidad máxima posible × menor tasa de deterioro posible. "
    "Nunca sobreestima el costo real, por eso A* sigue siendo óptimo."
)
