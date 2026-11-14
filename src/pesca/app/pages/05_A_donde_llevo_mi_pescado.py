import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from pesca import asignacion, config, red, transporte, visualizacion
from pesca.app import comun
from pesca.escenario import Escenario

comun.configurar_pagina("¿A dónde llevo mi pescado?")
escenario = comun.barra_lateral()
grafo = red.construir_red()
ORIGEN_INICIAL = "P02@rio"


@st.cache_data
def recomendar(origen: str, embarcacion: str, kg: float, esc: Escenario, nevera: str):
    return asignacion.recomendar(origen, embarcacion, kg, esc, nevera)


st.title("🐟 ¿A dónde llevo mi pescado?")
st.markdown("Dinos dónde estás, en qué bote vas y cuánto pescado llevas. Te decimos dónde te pagan más.")

# Lugares para elegir: zonas de pesca y comunidades; tambien el punto que se toque en el mapa
nodos = config.cargar_nodos()
propios = nodos[nodos["tipo"].isin(["zona_pesca", "comunidad"])]
lugares = {red.clave(i, red.CAPA_RIO): n for i, n in zip(propios["id"], propios["nombre"])}
if "origen_pescador" not in st.session_state:
    st.session_state["origen_pescador"] = ORIGEN_INICIAL
origen = st.session_state["origen_pescador"]
if origen not in lugares:
    lugares = {origen: f"El punto que tocaste ({grafo.nodes[origen]['nombre']})", **lugares}
lista = list(lugares)
elegido = st.selectbox("¿Dónde estás?", lista, index=lista.index(origen), format_func=lugares.get,
                       help="También puedes tocar el río en el mapa de abajo.")
if elegido != origen:
    st.session_state["origen_pescador"] = origen = elegido

c1, c2 = st.columns(2)
embarcacion = c1.selectbox("Tu bote", transporte.embarcaciones(), format_func=comun.TEXTO_EMBARCACION.get)
kg = c2.number_input("¿Cuántos kilos llevas?", min_value=1.0, max_value=500.0, value=20.0, step=5.0)
nevera = st.radio("¿Cómo llevas el pescado?", list(asignacion.NEVERAS), index=1, format_func=comun.TEXTO_NEVERA.get,
                  horizontal=True, key="nevera")

rec = recomendar(origen, embarcacion, kg, escenario, nevera)
m = rec.mejor

with st.container(border=True):
    if m is None:
        st.error(rec.explicacion)
    else:
        st.markdown(f"### 👉 {'Lleva tu pescado a' if m.cop_total > 0 else 'Lo menos malo:'} {m.nombre}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Horas hasta vender", asignacion.numero(m.horas_hasta_venta),
                  help="Faena + viaje + espera hasta que lo compran")
        c2.metric("Calidad al vender", asignacion.numero(m.calidad, 2), help="1 = recién pescado; por debajo de 0,25 lo rechazan")
        c3.metric("Te pagan", asignacion.pesos(m.cop_total))
        st.markdown(rec.explicacion)

st.markdown("**Tu ruta** — toca el río para cambiar dónde estás")
mapa = visualizacion.mapa_recomendacion(grafo, origen, m.ruta if m else ())
salida = st_folium(mapa, height=380, use_container_width=True, returned_objects=["last_clicked"], key="mapa_pescador")
st.caption("🟢 río a favor de la corriente · 🔴 río contra la corriente · ⚫ carretera (punteada) · 🟣 transbordo")
clic = (salida or {}).get("last_clicked")
if clic and clic != st.session_state.get("ultimo_clic"):
    st.session_state["ultimo_clic"] = clic
    cercano = red.nodo_rio_mas_cercano(clic["lat"], clic["lng"], grafo)
    if cercano != origen:
        st.session_state["origen_pescador"] = cercano
        st.rerun()

st.subheader("Todas las opciones")
filas = [
    {
        "destino": o.nombre,
        "cómo": comun.TEXTO_TIPO_OPCION[o.tipo],
        "horas hasta vender": o.horas_hasta_venta if o.factible else None,
        "calidad": o.calidad if o.factible else None,
        "te pagan": asignacion.pesos(o.cop_total) if o.factible else "—",
        "río contra corriente": f"{o.pct_contra_corriente:.0f} %" if o.factible else "—",
        "por qué no": o.motivo,
    }
    for o in rec.alternativas
]
st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch",
             column_config={"horas hasta vender": st.column_config.NumberColumn(format="%.1f"),
                            "calidad": st.column_config.NumberColumn(format="%.2f")})
st.caption(
    f"{comun.etiqueta('SIMULADO')}: velocidades, corriente, espera del comprador y precio según la calidad. "
    "La probabilidad de que haya espacio en el congelador de la señora sale del Monte Carlo del diagnóstico. "
    "Activa acopios, el camión refrigerado o el hielo a bordo en la barra lateral para ver cómo cambia la recomendación."
)
