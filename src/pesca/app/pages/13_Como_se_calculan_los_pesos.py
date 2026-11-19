import streamlit as st

from pesca import grafo, pesos
from pesca.app import comun

comun.configurar_pagina("Cómo se calculan los pesos")
escenario = comun.barra_lateral()

EJEMPLO = "M04"
g = grafo.construir_grafo()
arcos = {a["id"]: a for *_, a in g.edges(data=True)}
etiquetas = {EJEMPLO: "Ejemplo §3.8: San Miguel → Puerto Gaitán por río (M04, 41,65 km, todo en contra)"}
etiquetas.update(
    {i: f"{i}: {a['tipo']} {g.nodes[u]['nombre']} → {g.nodes[v]['nombre']} ({a['d_km']:.2f} km)" for u, v, a in g.edges(data=True) for i in [a["id"]]}
)

st.title("Cómo se calcula el peso de una arista")
st.markdown(
    "El peso de un arco es **cuánta calidad pierde el pescado** al recorrerlo (ΔQ). Depende del bote, de la "
    "temporada (la corriente), de cómo viaja el pescado (con hielo, en frío o congelado) y de **cuántas horas lleva "
    "desde la captura**, porque el hielo se acaba."
)

if st.button("Cargar el ejemplo de §3.8", key="cargar_ejemplo"):
    st.session_state.update(arco_peso=EJEMPLO, bote_peso="madera_remo", temporada_peso="aguas_bajas", nevera_peso="buena",
                            capa_peso="hielo", t_peso=0.0)

c1, c2 = st.columns([2, 1])
arco_id = c1.selectbox("Arco", list(etiquetas), format_func=etiquetas.get, key="arco_peso")
capa = c2.radio("Cómo viaja el pescado al entrar", pesos.CAPAS, horizontal=True, key="capa_peso")
c1, c2, c3, c4 = st.columns(4)
bote = c1.selectbox("Bote", list(comun.TEXTO_EMBARCACION), format_func=comun.TEXTO_EMBARCACION.get, key="bote_peso")
temporada = c2.selectbox("Temporada", list(comun.TEXTO_TEMPORADA), format_func=comun.TEXTO_TEMPORADA.get, key="temporada_peso")
nevera = c3.selectbox("Nevera", list(pesos.NEVERAS), format_func=comun.TEXTO_NEVERA.get, key="nevera_peso", index=1)
t = c4.number_input("Horas desde la captura (t)", 0.0, 200.0, 0.0, 1.0, key="t_peso")

cond = pesos.condiciones(escenario, bote, nevera).con(temporada=temporada, nevera=nevera)
arco = pesos.arco_ejemplo_m04() if arco_id == EJEMPLO else arcos[arco_id]

with st.container(border=True):
    for linea in pesos.explicar_arco(arco, cond, capa, t):
        st.markdown(linea)
    if "fuente" in arco:
        st.caption(f"Dato: {comun.etiqueta(arco['etiqueta'])} · {arco['fuente']}")

st.subheader("El mismo tramo, según cómo viaje el pescado (§3.8)")
st.markdown("Con las mismas 20,8 horas a remo, el tramo San Miguel → Puerto Gaitán cuesta entre 0,11 y 1,02 de calidad:")
filas = []
ejemplo = pesos.arco_ejemplo_m04()
for bote_e, temp_e, nev_e in [("madera_remo", "aguas_bajas", "buena"), ("madera_remo", "aguas_bajas", "deteriorada"),
                              ("madera_remo", "aguas_bajas", "sin_hielo"), ("madera_remo", "aguas_altas", "buena"),
                              ("madera_motor", "aguas_altas", "deteriorada"), ("aluminio_motor", "aguas_altas", "deteriorada")]:
    c = pesos.Condiciones(bote=bote_e, temporada=temp_e, nevera=nev_e)
    r = pesos.costo_arco(ejemplo, "hielo", 0.0, c)
    filas.append({"bote": comun.TEXTO_EMBARCACION[bote_e], "temporada": comun.TEXTO_TEMPORADA[temp_e], "nevera": comun.TEXTO_NEVERA[nev_e],
                  "horas": r[1] if r else None, "ΔQ": r[0] if r else None, "calidad": max(0.0, 1 - r[0]) if r else None,
                  "": "" if r else "infactible: la corriente no deja subir"})
c = pesos.Condiciones()
r = pesos.costo_arco(pesos.arco_ejemplo_m03(), "frio", 0.0, c)
filas.append({"bote": "camión refrigerado (M03, 38,9 km)", "temporada": "aguas bajas", "nevera": "en frío", "horas": r[1], "ΔQ": r[0],
              "calidad": 1 - r[0], "": ""})
st.dataframe(filas, hide_index=True, width="stretch",
             column_config={"ΔQ": st.column_config.NumberColumn(format="%.4f"), "calidad": st.column_config.NumberColumn(format="%.3f"),
                            "horas": st.column_config.NumberColumn(format="%.3f")})
st.caption("RRS(T) = (1 + 0,1·T)² · VU0 = 360 h · todos los parámetros están en `parametros.yaml` con su etiqueta.")
