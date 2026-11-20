import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from pesca import config
from pesca.app import comun

comun.configurar_pagina("Supuestos y datos")
comun.barra_lateral()

st.title("Supuestos y datos")
st.markdown(
    "De dónde sale cada número. 🟢 MEDIDO = medido por el equipo en Google Earth · "
    "🔵 DATO / OFICIAL = trabajo de campo o estadística pública · "
    "🟡 CALIBRADO = derivado de lo medido · 🟠 SIMULADO = supuesto del proyecto · 🔴 POR CONFIRMAR."
)

tab_param, tab_nodos, tab_dist, tab_ofic, tab_lim = st.tabs(
    ["Parámetros", "Lugares", "Distancias medidas", "Datos oficiales", "Limitaciones"]
)

with tab_param:
    filas = [
        {
            "grupo": ruta.split(".")[0],
            "parámetro": ruta.split(".", 1)[1],
            "valor": str(h["valor"]),
            "rango Monte Carlo": str(h.get("rango", "")),
            "etiqueta": comun.etiqueta(h["etiqueta"]),
            "nota": h.get("nota", ""),
        }
        for ruta, h in config.hojas_parametros()
    ]
    tabla = pd.DataFrame(filas)
    for grupo, sub in tabla.groupby("grupo", sort=False):
        st.markdown(f"**{grupo.replace('_', ' ').capitalize()}**")
        st.dataframe(sub.drop(columns="grupo"), hide_index=True, width="stretch")

with tab_nodos:
    nodos = config.cargar_nodos()
    if (nodos["validado"] == "no").any():
        st.warning(
            "Las coordenadas con `validado = no` son **aproximadas**. "
            "El equipo las está corrigiendo en Google Earth."
        )
    colores = {"acopio": "red", "desembarque": "orange", "comunidad": "purple", "zona_pesca": "blue", "confluencia": "gray"}
    mapa = folium.Map(location=[nodos["lat"].mean(), nodos["lon"].mean()], zoom_start=9, tiles="OpenStreetMap")
    for n in nodos.itertuples():
        folium.CircleMarker(
            [n.lat, n.lon],
            radius=7,
            color=colores.get(n.tipo, "black"),
            fill=True,
            fill_opacity=0.8,
            tooltip=f"{n.id} · {n.nombre} ({n.tipo}) · validado: {n.validado}",
        ).add_to(mapa)
    st_folium(mapa, height=450, use_container_width=True, returned_objects=[])
    st.dataframe(nodos, hide_index=True, width="stretch")
    st.markdown("**Mercados de referencia** (medidos en KML por el equipo; no entran a la red)")
    st.dataframe(config.puntos_referencia(), hide_index=True, width="stretch")

with tab_dist:
    dist = config.cargar_distancias_medidas()
    st.markdown("Rutas medidas por el equipo en Google Earth 🟢 MEDIDO. El grafo debe reproducirlas (±1 %).")
    st.dataframe(dist.drop(columns=["evidencia"]), hide_index=True, width="stretch")
    for d in dist.itertuples():
        with st.expander(f"{d.id}: {d.origen} → {d.destino} por {d.modo}, {d.distancia_km} km"):
            ruta = config.ruta_evidencia(d.evidencia)
            if ruta is not None and ruta.suffix.lower() in (".png", ".jpg", ".jpeg"):
                st.image(str(ruta), width="stretch")
            elif ruta is not None:
                st.info(f"Traza medida por el equipo en Google Earth: `{d.evidencia}`")
            else:
                st.info(f"Captura disponible en el repositorio: `{d.evidencia}`")

with tab_ofic:
    st.markdown("**Desembarcos registrados por el SEPEC (AUNAP), 2022** 🔵 OFICIAL")
    st.dataframe(config.cargar_sepec(), hide_index=True, width="stretch")
    st.markdown("**Precios mayoristas (SIPSA/DANE), Central de Abastos de Villavicencio** 🔵 OFICIAL")
    st.dataframe(config.cargar_precios(), hide_index=True, width="stretch")

with tab_lim:
    st.markdown(
        """
- La **ubicación del desembarque de la señora** no se conoce: se prueban varias candidatas y se reporta si las conclusiones cambian.
- El **SEPEC es un registro mínimo**: los desembarques informales no aparecen, y por eso se usa un factor de subregistro (SIMULADO).
- El modelo de deterioro (Ratkowsky / Spencer–Baines) se calibró sobre todo con pescado de aguas templadas y aquí se usa como aproximación.
- Velocidades, corriente, cortes de luz y capacidades son supuestos hasta que haya datos de campo.
- No se usan datos de calidad del agua, batimetría ni caudales.
"""
    )
