import streamlit as st
from streamlit_folium import st_folium

from pesca import asignacion, red, visualizacion
from pesca.app import comun
from pesca.escenario import Escenario

comun.configurar_pagina("Toda la flota")
escenario = comun.barra_lateral()


@st.cache_data(show_spinner="Repartiendo el pescado de toda la flota…")
def resolver(esc: Escenario):
    return asignacion.problema_transporte(esc)


# Color de cada destino en el mapa (mismos colores que en el diagnostico)
SITIO_DESTINO = {"plaza": "malecon", "acopio": "san_miguel", "desembarque": "vichada"}

st.title("Toda la flota: ¿cómo repartir el pescado?")
st.markdown(
    "Si todos los pescadores se pusieran de acuerdo, ¿a dónde debería ir el pescado de cada uno para que se pierda lo menos posible? "
    "Es un **problema de transporte** (flujo de costo mínimo): cada destino tiene su capacidad y lo que no cabe en ninguna parte "
    "queda *sin destino* y se pierde."
)

r = resolver(escenario)
ahorro = r["costo_hoy_dia"] - r["costo_optimo_dia"]
c1, c2, c3 = st.columns(3)
c1.metric("Plata perdida hoy", f"{asignacion.pesos(r['costo_hoy_dia'])}/día",
          help="Cada pescador en su desembarque habitual de hoy")
c2.metric("Con el mejor reparto", f"{asignacion.pesos(r['costo_optimo_dia'])}/día",
          delta=f"-{asignacion.pesos(ahorro)}/día", delta_color="inverse")
c3.metric("Pescado sin destino", f"{r['kg_sin_destino']:.0f} kg/día", help="Lo que no cabe en ninguna parte")
st.caption(
    f"Flota: {r['flujos']['pescador'].nunique()} pescadores, {r['kg_dia']:.0f} kg/día en un mes típico fuera de veda. "
    f"Valor si todo llegara fresco: {asignacion.pesos(r['valor_posible_dia'])}/día."
)

st.subheader("¿Cuánto recibe cada destino?")
st.altair_chart(visualizacion.grafico_uso_destinos(r["uso"]), width="stretch")
st.caption("La raya gris es la capacidad del destino (si tiene).")

st.subheader("Por dónde va el pescado")
flujos = r["flujos"]
grafo = red.construir_red()
destinos = {}
for d in flujos["destino"].unique():
    if d == asignacion.SIN_DESTINO:
        continue
    tipo, lugar = d.split(":")[0], d.split(":")[1]
    destinos[lugar] = "senora" if lugar == escenario.desembarque_senora else SITIO_DESTINO[tipo]
st_folium(visualizacion.mapa_recorridos(grafo, asignacion.flujos_por_arista(flujos), destinos), height=420,
          use_container_width=True, returned_objects=[])
st.caption("Grosor proporcional a los kg/día. 🟢 a favor de la corriente · 🔴 contra la corriente · ⚫ carretera.")

st.subheader("Pescador por pescador")
tabla = flujos.assign(embarcacion=flujos["embarcacion"].map(comun.TEXTO_EMBARCACION))
st.dataframe(
    tabla[["pescador", "zona", "embarcacion", "destino_nombre", "kg_dia", "cop_perdidos_kg"]],
    hide_index=True, width="stretch",
    column_config={
        "destino_nombre": "destino",
        "kg_dia": st.column_config.NumberColumn("kg al día", format="%.1f"),
        "cop_perdidos_kg": st.column_config.NumberColumn("COP perdidos por kg", format="%.0f"),
    },
)
st.caption(
    f"{comun.etiqueta('SIMULADO')}: la flota es la población sintética del diagnóstico. "
    "El modelo no cobra el combustible ni el tiempo del pescador: solo mira cuánto vale el pescado al venderlo."
)
