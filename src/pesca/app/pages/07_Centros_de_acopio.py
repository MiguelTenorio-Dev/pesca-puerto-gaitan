import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from pesca import acopios, config, grafo, visualizacion
from pesca.app import comun

comun.configurar_pagina("Centros de acopio")
escenario = comun.barra_lateral()


@st.cache_data(show_spinner="Calculando c_ij con Dijkstra por capas…")
def analisis():
    an = acopios.analizar()
    an.pop("grafo")
    return an


@st.cache_data
def precalculado():
    return acopios.cargar_precalculado()


an = analisis()
g = grafo.construir_grafo()
an["grafo"] = g
pre = precalculado()
nombres = config.cargar_centros_poblados().set_index("id")["nombre"]


def nombre(j: str) -> str:
    return nombres.get(j, g.nodes[j]["nombre"] if j in g else j)


def conjunto(s) -> str:
    return ", ".join(nombre(j) for j in s)


st.title("Centros de acopio: ¿dónde ponerlos y por qué ahí?")
st.markdown(
    "Un acopio solo puede estar en un **centro poblado** (ahí hay comprador, energía y carretera). Entre ellos se elige "
    "con la **p-mediana sobre los vértices del grafo**: el conjunto de pueblos que hace mínima la calidad perdida, "
    "ponderada por los kilos de cada zona. El costo de cada zona a cada pueblo (c_ij) lo calcula **Dijkstra por capas**."
)

st.subheader("1. ¿Qué pueblos pueden ser acopio?")
tabla = an["tabla_candidatos"].copy()
tabla["entra"] = tabla["candidato"].map({True: "✅ candidato", False: "❌ excluido"})
st.dataframe(tabla[["nombre", "habitantes_2018", "acceso_rio", "acceso_via", "entra", "motivo", "marca"]], hide_index=True, width="stretch")
st.caption(f"Regla: cabecera o centro poblado, ≥ {config.parametro('acopios_grafo.p_min_habitantes')} habitantes, "
           f"acceso {config.parametro('acopios_grafo.criterio_acceso')} por río o vía, con coordenadas y alcanzable por BFS. "
           "[CONFIRMAR] = coordenadas, acceso o energía sin confirmar.")

st.subheader("2. ¿Cuánto se pierde llevando cada zona a cada pueblo? (c_ij)")
c = an["c"].rename(columns=nombre, index=lambda i: g.nodes[i]["nombre"])
st.dataframe(c, width="stretch", column_config={col: st.column_config.NumberColumn(format="%.3f") for col in c.columns})
st.caption("c_ij = ΔQ de la ida por río (con hielo) + ΔQ de la espera en el cuarto frío + ΔQ de la vuelta a la plaza en frío. "
           "Promedio sobre la flota y las neveras [SIMULADO]. 1 = no se llega o se pierde todo.")

st.subheader("3. ¿Cuántos acopios valen la pena? (curva del codo)")
curva = an["curva"].assign(S=lambda d: d["S"].map(conjunto))
c1, c2 = st.columns([2, 1])
c1.line_chart(an["curva"].set_index("p")["f"], x_label="número de acopios p", y_label="kg perdidos por día f(p)")
c2.dataframe(curva, hide_index=True, width="stretch", column_config={"f": st.column_config.NumberColumn(format="%.3f")})
st.markdown(f"El codo está en **p = {an['p_codo']}**: abrir uno más ya casi no reduce la pérdida. "
            f"Los acopios elegidos son **{conjunto(an['S'])}**.")

st.subheader("4. Tres métodos, el mismo resultado")
st.dataframe(an["metodos"].assign(S=lambda d: d["S"].map(conjunto)), hide_index=True, width="stretch",
             column_config={"f": st.column_config.NumberColumn(format="%.4f"), "gap_pct": st.column_config.NumberColumn("gap (%)", format="%.2f")})
st.caption("Enumeración: todas las combinaciones (óptimo garantizado). ILP: PuLP/CBC. Búsqueda local Teitz–Bart: heurística, "
           "por eso se reporta su gap contra la enumeración.")

st.subheader("5. ¿Por qué estos pueblos y no otro punto?")
libre = an["libre"]
filas = [
    {"referencia": "Propuesta (p-mediana sobre pueblos)", "S": conjunto(an["S"]), "kg perdidos/día": acopios.f(an["c"], an["w"], an["S"])},
    {"referencia": "Acopios de hoy", "S": conjunto(an["actuales"]), "kg perdidos/día": an["f_actuales"]},
    {"referencia": "p-mediana libre (cualquier punto del río, cota inferior)", "S": conjunto(libre["S"]) if libre else "—",
     "kg perdidos/día": libre["f"] if libre else None},
    {"referencia": "Centroide de las zonas (1 acopio)", "S": nombre(an["centroide"]), "kg perdidos/día": an["f_centroide_p1"]},
    {"referencia": "p-mediana con 1 acopio", "S": conjunto(an["curva"]["S"].iloc[0]), "kg perdidos/día": an["f_p1"]},
]
st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch", column_config={"kg perdidos/día": st.column_config.NumberColumn(format="%.3f")})
st.markdown(
    f"- **Costo de exigir pueblos:** {an['costo_exigir_pueblos']:.3f} kg/día (propuesta − p-mediana libre).\n"
    f"- **El punto medio no sirve:** el centroide cae en {nombre(an['centroide'])} y pierde "
    f"{an['f_centroide_p1']:.2f} kg/día contra {an['f_p1']:.2f} del mejor pueblo."
)

st.subheader("6. Mapa: hoy, propuesta y área de influencia")
modo = st.radio("Modo", ["evaluar", "agregar", "reubicar"], horizontal=True, key="modo_pmediana",
                format_func={"evaluar": "Evaluar los de hoy", "agregar": "Mantener y agregar", "reubicar": "Reubicar (p libre)"}.get)
if modo == "evaluar":
    propuesta = list(an["actuales"])
elif modo == "agregar":
    if len(an["agregar"]):
        k = st.select_slider("¿Cuántos agregar?", list(an["agregar"]["k"]), key="k_agregar")
        propuesta = list(an["agregar"].set_index("k").at[k, "S"])
    else:
        st.info("No hay más candidatos que agregar: los demás pueblos no tienen coordenadas o acceso confirmado [CONFIRMAR].")
        propuesta = list(an["actuales"])
else:
    propuesta = list(an["S"])
asignacion = acopios.voronoi(an["c"], propuesta).to_dict()
st_folium(visualizacion.mapa_acopios_grafo(g, an["actuales"], [j for j in propuesta if j not in an["actuales"]] or propuesta, asignacion),
          height=420, use_container_width=True, returned_objects=[])

st.subheader("7. Veredicto por acopio")
mc = pre["mc"] if pre is not None else None
via = acopios.viabilidad(an, propuesta, mc)
via["nombre"] = via["acopio"].map(nombre)
st.dataframe(via.drop(columns=["acopio"]), hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="%,.0f") for c in ("beneficio_anual", "inversion", "vpn", "vpn_p5", "vpn_p95")})
umbral = 100 * config.parametro("economia.umbral_vpn_positivo")
st.caption(f"Regla: vale la pena si el VPN a {config.parametro('economia.horizonte_anios')} años es positivo en al menos el {umbral:.0f} % "
           "de las corridas de Monte Carlo. Pérdida evitada = f(S sin el acopio) − f(S). Costos e inversiones: SIMULADO.")
if mc is None:
    st.info("Falta el Monte Carlo: córrelo con `python scripts/correr_todo.py --solo g5`.")

if pre is not None:
    st.subheader("8. ¿Cambia la conclusión? (sensibilidad)")
    sens = pre["sensibilidad"].assign(S=lambda d: d["S"].map(conjunto))
    st.dataframe(sens, hide_index=True, width="stretch")

if st.button("Activar esta propuesta en el escenario", key="activar_propuesta"):
    st.session_state["escenario"] = escenario.con(acopios_grafo=frozenset(propuesta))
    st.rerun()
