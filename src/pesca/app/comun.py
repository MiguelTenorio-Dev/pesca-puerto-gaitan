"""Piezas de interfaz compartidas: barra lateral del escenario y etiquetas de datos."""

from __future__ import annotations

import streamlit as st

from pesca import config, red
from pesca.escenario import Escenario

TEXTO_TEMPORADA = {"aguas_bajas": "Aguas bajas (verano)", "aguas_altas": "Aguas altas (invierno)"}

TEXTO_EMBARCACION = {
    "madera_remo": "Madera, a remo",
    "madera_motor": "Madera, con motor",
    "aluminio_remo": "Aluminio, a remo",
    "aluminio_motor": "Aluminio, con motor",
}

TEXTO_CRITERIO = {
    "perdida": "Menor pérdida de calidad",
    "tiempo": "Menor tiempo",
    "distancia": "Menor distancia",
}

TEXTO_NEVERA = {"sin_hielo": "Sin hielo", "deteriorada": "Nevera dañada (poco hielo)", "buena": "Nevera buena con hielo"}

TEXTO_TIPO_OPCION = {"plaza": "por río a la plaza", "desembarque": "dejarlo y esperar al comprador", "acopio": "acopio con frío + carretera"}

TEXTO_ALGORITMO = {"dijkstra": "Dijkstra", "a_estrella": "A*", "bfs": "BFS (menos tramos)"}

TEXTO_MODO = {"rio": "río", "via": "carretera", "transbordo": "transbordo"}

TEXTO_SENTIDO = {"aguas_abajo": "a favor de la corriente", "aguas_arriba": "contra la corriente"}

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

        nuevos = actual.acopios_nuevos
        if nuevos:
            grafo = red.construir_red()
            nombres = ", ".join(f"{grafo.nodes[red.clave(n, red.CAPA_RIO)]['nombre']} ({n})" for n in sorted(nuevos))
            st.caption(f"Acopios nuevos activos: {nombres}")
            if st.button("Quitar acopios nuevos"):
                nuevos = frozenset()

        del_grafo = actual.acopios_grafo
        if del_grafo:
            centros = config.cargar_centros_poblados().set_index("id")["nombre"]
            st.caption("Acopios activados en el grafo: " + ", ".join(centros[j] for j in sorted(del_grafo)))
            if st.button("Quitar acopios del grafo"):
                del_grafo = frozenset()

        medidas = {"inversiones": actual.inversiones, "cajas_termicas": actual.cajas_termicas,
                   "ciclo_camion_dias": actual.ciclo_camion_dias, "desembarque_mejorado": actual.desembarque_mejorado,
                   "subsidio_motor": actual.subsidio_motor}
        if actual.inversiones:
            st.caption("Inversiones activas: " + ", ".join(sorted(actual.inversiones)))
            if st.button("Quitar inversiones"):
                medidas = {"inversiones": frozenset(), "cajas_termicas": False, "ciclo_camion_dias": None,
                           "desembarque_mejorado": False, "subsidio_motor": False}

    nuevo = actual.con(
        acopios_activos=frozenset(activos),
        desembarque_senora=senora,
        temporada=temporada,
        hielo_a_bordo=hielo,
        camion_refrigerado=camion,
        acopios_nuevos=nuevos,
        acopios_grafo=del_grafo,
        **medidas,
    )
    st.session_state["escenario"] = nuevo
    return nuevo
