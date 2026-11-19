import streamlit as st
from streamlit_folium import st_folium

from pesca import grafo, pesos, recomendador, visualizacion
from pesca.app import comun
from pesca.red import haversine_km

comun.configurar_pagina("¿A dónde llevo mi pescado?")
escenario = comun.barra_lateral()
g = grafo.construir_grafo()

# Se puede salir de una zona de pesca, una comunidad o cualquier punto del río
salidas = {n: a["nombre"] for n, a in g.nodes(data=True) if a["tipo"] in ("zona_pesca", "comunidad", "punto_rio")}
lista = sorted(salidas, key=lambda n: (g.nodes[n]["tipo"] != "zona_pesca", n))
if "origen_pescador" not in st.session_state or st.session_state["origen_pescador"] not in salidas:
    st.session_state["origen_pescador"] = "P02" if "P02" in salidas else lista[0]

st.title("🐟 ¿A dónde llevo mi pescado?")
st.markdown("Dinos dónde estás, en qué bote vas y cuánto pescado llevas. Te decimos dónde te pagan más.")

origen = st.selectbox("¿Dónde estás?", lista, index=lista.index(st.session_state["origen_pescador"]), format_func=salidas.get,
                      help="También puedes tocar el mapa: se toma el punto del río más cercano.")
st.session_state["origen_pescador"] = origen
c1, c2 = st.columns(2)
bote = c1.selectbox("Tu bote", list(comun.TEXTO_EMBARCACION), format_func=comun.TEXTO_EMBARCACION.get, key="bote_reco")
kg = c2.number_input("¿Cuántos kilos llevas?", min_value=1.0, max_value=500.0, value=20.0, step=5.0, key="kg_reco")
nevera = st.radio("¿Cómo llevas el pescado?", list(pesos.NEVERAS), index=1, format_func=comun.TEXTO_NEVERA.get, horizontal=True, key="nevera")

cond = pesos.condiciones(escenario, bote, nevera)
rec = recomendador.recomendar(origen, bote, kg, cond, g)

with st.container(border=True):
    st.markdown(recomendador.explicar(rec))

if rec.mejor is not None:
    st.markdown("**Tu ruta, tramo a tramo**")
    for linea in rec.mejor.texto:
        st.markdown(f"- {linea}")

mapa = visualizacion.mapa_ruta_grafo(g, rec.mejor.sentidos if rec.mejor else [], origen)
clic = st_folium(mapa, height=420, use_container_width=True, returned_objects=["last_clicked"], key="mapa_reco")
st.caption("🟢 río a favor de la corriente · 🔴 río en contra · 🔵 sin corriente (acceso) · gris punteado: carretera")
if clic and clic.get("last_clicked"):
    lat, lon = clic["last_clicked"]["lat"], clic["last_clicked"]["lng"]
    cercano = min(salidas, key=lambda n: haversine_km(lat, lon, g.nodes[n]["lat"], g.nodes[n]["lon"]))
    if cercano != origen:
        st.session_state["origen_pescador"] = cercano
        st.rerun()

st.subheader("Todas las opciones")
st.dataframe(recomendador.tabla_opciones(rec), hide_index=True, width="stretch",
             column_config={"calidad": st.column_config.NumberColumn(format="%.2f"), "neto COP": st.column_config.NumberColumn(format="%,.0f"),
                            "km por río": st.column_config.NumberColumn(format="%.1f"),
                            "km contra corriente": st.column_config.NumberColumn(format="%.1f")})
st.caption("Precio base de la plaza y costos del viaje: SIMULADO (parametros.yaml). Coordenadas aproximadas (validado = no).")
