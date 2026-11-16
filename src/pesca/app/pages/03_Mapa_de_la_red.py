import streamlit as st
from streamlit_folium import st_folium

from pesca import config, red, transporte, visualizacion
from pesca.app import comun
from pesca.escenario import Escenario

comun.configurar_pagina("Mapa de la red")
escenario = comun.barra_lateral()


@st.cache_data(show_spinner="Calculando las rutas de cada lugar a cada acopio…")
def matriz(esc: Escenario):
    return transporte.matriz_origen_acopio(esc)


grafo = red.construir_red()

st.title("Mapa de la red: ríos, carreteras y transbordos")
st.markdown(
    "El pescado se mueve por **río** (línea continua) y por **carretera** (línea punteada). "
    "Donde se cambia de bote a carro hay un **transbordo** (círculo morado). "
    "El color dice **de dónde sale cada distancia**: 🟢 medida por el equipo, "
    "🟡 calibrada con lo medido, 🟠 simulada."
)
st.warning(
    "Las trazas de los ríos y casi todas las coordenadas son **aproximadas** (`validado = no`); "
    "solo el malecón de Puerto Gaitán y San Miguel están medidos en KML (`validado = si`). "
    "Las distancias, en cambio, se ajustan a lo medido en Google Earth."
)

st_folium(visualizacion.mapa_red(grafo), height=520, use_container_width=True, returned_objects=[])

modos = [d["modo"] for _, _, d in grafo.edges(data=True)]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Nodos", grafo.number_of_nodes())
c2.metric("Aristas (con sentido)", grafo.number_of_edges())
c3.metric("Tramos de río", modos.count(red.CAPA_RIO) // 2)
c4.metric("Transbordos", modos.count("transbordo") // 2)

st.subheader("¿El grafo reproduce lo medido?")
cal = red.calibracion(grafo)
st.dataframe(
    cal.assign(modo=cal["modo"].map(comun.TEXTO_MODO)),
    hide_index=True,
    width="stretch",
    column_config={
        "km_medido": st.column_config.NumberColumn("km medidos", format="%.2f"),
        "km_grafo": st.column_config.NumberColumn("km en el grafo", format="%.2f"),
        "error_pct": st.column_config.NumberColumn("error (%)", format="%.3f"),
    },
)
tolerancia = 100 * config.parametro("red.tolerancia_calibracion")
if (cal["error_pct"].abs() <= tolerancia).all():
    st.success(f"Las cuatro rutas medidas se reproducen con un error menor al {tolerancia:g} %.")
else:
    st.error(f"Alguna ruta medida se aleja más del {tolerancia:g} %.")

s = grafo.graph["sinuosidad"]
c1, c2 = st.columns(2)
c1.metric("Sinuosidad de los ríos sin medir", f"{s[red.CAPA_RIO]:.2f}", help="km por río ÷ km en línea recta, calibrado con M02 y M04")
c2.metric("Sinuosidad de las vías sin medir", f"{s[red.CAPA_VIA]:.2f}", help="km por carretera ÷ km en línea recta, calibrado con M01 y M03")
st.caption(f"{comun.etiqueta('CALIBRADO')}: en Monte Carlo varía ±{100 * config.parametro('rio.variacion_sinuosidad'):g} %.")

st.subheader("Dos cuencas sin conexión por agua")
cruces = red.aristas_entre_cuencas(grafo)
if cruces:
    st.error(f"Hay {len(cruces)} tramos de río que unen las cuencas del Meta y del Vichada: {cruces}")
else:
    st.success(
        "Ningún tramo de río une la cuenca del **Meta** (Meta, Manacacías, Yucao) con la del **Vichada** "
        "(Planas, Muco, Guarrojo). Entre las dos solo se pasa por carretera."
    )

st.subheader("De cada lugar a cada acopio")
st.markdown(
    "La mejor ruta (menor pérdida de calidad) desde cada zona, comunidad o desembarque hasta cada acopio, "
    "con la embarcación elegida y el escenario de la barra lateral."
)
tabla = matriz(escenario)
c1, c2 = st.columns(2)
emb = c1.selectbox("Embarcación", transporte.embarcaciones(), format_func=comun.TEXTO_EMBARCACION.get)
nodos = config.cargar_nodos().set_index("id")
acopio = c2.selectbox("Acopio", list(tabla["acopio"].unique()), format_func=lambda i: nodos.at[i, "nombre"])
vista = tabla[(tabla["embarcacion"] == emb) & (tabla["acopio"] == acopio)]
st.dataframe(
    vista[["origen_nombre", "factible", "km", "km_rio", "km_via", "horas", "pct_contra_corriente", "transbordos", "calidad_viaje", "motivo"]],
    hide_index=True,
    width="stretch",
    column_config={
        "origen_nombre": "desde",
        "km": st.column_config.NumberColumn("km", format="%.1f"),
        "km_rio": st.column_config.NumberColumn("km por río", format="%.1f"),
        "km_via": st.column_config.NumberColumn("km por carretera", format="%.1f"),
        "horas": st.column_config.NumberColumn("horas", format="%.1f"),
        "pct_contra_corriente": st.column_config.NumberColumn("% del río contra corriente", format="%.0f"),
        "calidad_viaje": st.column_config.ProgressColumn("calidad al llegar (solo el viaje)", min_value=0, max_value=1, format="%.2f"),
    },
)
st.caption(
    f"{comun.etiqueta('SIMULADO')}: velocidades, corriente y temperaturas son supuestos del proyecto. "
    "La calidad cuenta solo el viaje; el diagnóstico (Fase 2) suma la faena y la espera en el desembarque."
)
