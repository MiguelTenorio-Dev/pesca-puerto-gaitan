"""Piezas de interfaz compartidas: barra lateral del escenario y etiquetas de datos."""

from __future__ import annotations

import streamlit as st

from pesca import config
from pesca.escenario import Escenario

TEXTO_TEMPORADA = {"aguas_bajas": "Aguas bajas (verano)", "aguas_altas": "Aguas altas (invierno)"}

TEXTO_ETIQUETA = {
    "MEDIDO": "🟢 MEDIDO",
    "DATO": "🔵 DATO",
    "OFICIAL": "🔵 OFICIAL",
    "CALIBRADO": "🟡 CALIBRADO",
    "SIMULADO": "🟠 SIMULADO",
    "CONFIRMAR": "🔴 POR CONFIRMAR",
}


def configurar_pagina(titulo: str) -> None:
    st.set_page_config(page_title=f"{titulo} · Pesca Puerto Gaitán", page_icon="🐟", layout="wide")


def etiqueta(clave: str) -> str:
    return TEXTO_ETIQUETA.get(clave, clave)


def barra_lateral() -> Escenario:
    """Dibuja los controles del escenario y devuelve el escenario vigente."""
    if "escenario" not in st.session_state:
        st.session_state["escenario"] = Escenario.base()
    actual: Escenario = st.session_state["escenario"]

    nodos = config.cargar_nodos().set_index("id")
    acopios = list(nodos.index[nodos["tipo"] == "acopio"])
    candidatas = config.parametro("cadena_actual.candidatas_desembarque_senora")

    with st.sidebar:
        st.header("Escenario")
        activos = st.multiselect(
            "Acopios activos",
            acopios,
            default=sorted(actual.acopios_activos),
            format_func=lambda i: nodos.at[i, "nombre"],
        )
        senora = st.selectbox(
            "¿Dónde está el desembarque de la señora?",
            candidatas,
            index=candidatas.index(actual.desembarque_senora),
            format_func=lambda i: nodos.at[i, "nombre"].split(": ")[-1],
            help="La ubicación real no se conoce. Se prueban varias candidatas.",
        )
        temporada = st.radio(
            "Temporada",
            sorted(config.TEMPORADAS),
            index=sorted(config.TEMPORADAS).index(actual.temporada),
            format_func=TEXTO_TEMPORADA.get,
        )
        hielo = st.toggle("Hielo a bordo", value=actual.hielo_a_bordo)
        camion = st.toggle("Camión refrigerado", value=actual.camion_refrigerado)

        if not activos:
            st.warning("Debe quedar al menos un acopio activo. Se mantiene la selección anterior.")
            activos = sorted(actual.acopios_activos)

    nuevo = actual.con(
        acopios_activos=frozenset(activos),
        desembarque_senora=senora,
        temporada=temporada,
        hielo_a_bordo=hielo,
        camion_refrigerado=camion,
    )
    st.session_state["escenario"] = nuevo
    return nuevo
