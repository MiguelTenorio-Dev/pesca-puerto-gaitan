import streamlit as st

from pesca.app import comun

comun.configurar_pagina("Inicio")
comun.barra_lateral()

st.title("🐟 El pescado de Puerto Gaitán pierde valor antes de venderse")

st.markdown(
    """
**El problema, en tres líneas**
- Del río a la plaza el viaje es largo y muchas veces va **contra la corriente**.
- **No hay cadena de frío**: las neveras de icopor se dañan rápido y los congeladores son caseros.
- El comprador tarda **de 7 a 15 días** en llegar, y mientras tanto el pescado se daña y vale menos.
"""
)

st.subheader("Así funciona hoy")
st.markdown(
    """
`zona de pesca` → **río** (icopor) → `desembarque de la señora` → **espera de 7 a 15 días**
(congelador o icopor, cortes de luz) → **carretera** (carro del comprador) → `plaza de Puerto Gaitán`
"""
)

st.subheader("Cómo navegar")
st.markdown(
    """
- **Barra lateral:** define el escenario (acopios activos, dónde está el desembarque, temporada, hielo y camión).
  Lo que cambies ahí se ve en todas las pantallas.
- **Del dato a la decisión:** el recorrido completo del modelo de grafos en cinco pasos, con números del escenario.
- **Datos del grafo → Cómo se construye el grafo → Cómo se calculan los pesos → Laboratorio de algoritmos → Centros de acopio:**
  de dónde sale cada arista, cada peso y cada acopio.
- **Centros de acopio:** el reacomodo de los acopios y los puntos fríos, decidido con Dijkstra, A*, BFS, DFS y la p-mediana.
- **Diagnóstico, Bimodal y cadena de frío, Hoy vs propuesta:** la cadena de hoy y la propuesta, con todas sus instalaciones.
- **Supuestos y datos:** de dónde sale cada número: qué es medido, qué es oficial y qué es simulado.
"""
)

st.caption("Los valores marcados como SIMULADO son supuestos del proyecto, no datos medidos.")
