import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from pesca import acopios, config, grafo, visualizacion
from pesca.app import comun

comun.configurar_pagina("Centros de acopio")
escenario = comun.barra_lateral()


@st.cache_data(show_spinner="Reacomodando los acopios con Dijkstra, A*, BFS y DFS…")
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


def nombre(j: str) -> str:
    return acopios.nombre_acopio(an, j)


def conjunto(s) -> str:
    return ", ".join(nombre(j) for j in s)


st.title("Centros de acopio: reacomodo con algoritmos de búsqueda")
st.markdown(
    "Un acopio solo puede estar en un **centro poblado** (ahí hay comprador, energía y carretera). El reacomodo se decide "
    "con **algoritmos de búsqueda sobre el grafo**: **BFS** dice qué pueblos se alcanzan, **Dijkstra** calcula cuánta calidad "
    "pierde cada zona yendo a cada pueblo, la **p-mediana** (búsqueda exhaustiva, ILP y búsqueda local) escoge los pueblos, "
    "**A\\*** verifica cada ruta asignada y **DFS** revisa qué tramos son críticos."
)

st.header("La propuesta")
frios = an["puntos_frios"]
filas = []
for j in an["actuales"]:
    rol = "punto frío (se recoge hielo)" if j in frios["todos"] else ("acopio" if j in an["propuesta"] else "sale")
    filas.append({"lugar": nombre(j), "hoy": "acopio" if j != "CP02" else "acopio (cuarto frío sin uso)", "con la propuesta": rol})
for j in an["propuesta"]:
    if j not in an["actuales"]:
        filas.append({"lugar": nombre(j), "hoy": "—", "con la propuesta": "acopio nuevo (reemplaza a La Cristalina)"})
for j in frios["todos"]:
    if j not in an["actuales"]:
        filas.append({"lugar": nombre(j), "hoy": "—", "con la propuesta": "punto frío (se recoge hielo)"})
st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
c1, c2 = st.columns(2)
c1.metric("kg perdidos por día, hoy", f"{an['f_actuales']:.3f}")
c2.metric("kg perdidos por día, con la propuesta", f"{an['f_propuesta']:.3f}", delta=f"{an['f_propuesta'] - an['f_actuales']:.3f}",
          delta_color="inverse")
st_folium(visualizacion.mapa_acopios_grafo(g, list(an["actuales"]), [j for j in an["propuesta"] if j not in an["actuales"]],
                                           an["voronoi_propuesta"].to_dict(), list(frios["todos"]),
                                           {j: nombre(j) for j in set(an["actuales"]) | set(an["propuesta"]) | set(frios["todos"])}),
          height=440, use_container_width=True, returned_objects=[])
st.caption("🏠 rojo: acopios de hoy · ⭐ azul: acopio nuevo · ✳ celeste: punto frío · líneas: a qué acopio va cada zona.")

st.header("1. ¿Qué pueblos pueden ser acopio? (BFS)")
tabla = an["tabla_candidatos"].copy()
tabla["entra"] = tabla["candidato"].map({True: "✅ candidato", False: "❌ excluido"})
st.dataframe(tabla[["nombre", "habitantes_2018", "acceso_rio", "acceso_via", "entra", "motivo", "marca"]], hide_index=True, width="stretch")
st.caption("BFS desde cada zona de pesca: un pueblo es candidato si se llega a él. La Cristalina es punto frío por decisión del equipo.")

st.header("2. ¿Cuánto se pierde llevando cada zona a cada pueblo? (Dijkstra)")
c = an["c"].rename(columns=nombre, index=lambda i: g.nodes[i]["nombre"])
st.dataframe(c, width="stretch", column_config={col: st.column_config.NumberColumn(format="%.3f") for col in c.columns})
st.caption("c_ij = calidad que se pierde en la ida por río (con hielo) + la espera en el cuarto frío + la vuelta a la plaza en frío. "
           "Dijkstra por capas desde cada zona; promedio de la flota, las neveras y las dos temporadas [SIMULADO]. 1 = no se llega.")

st.header("3. ¿Cuántos acopios y dónde? (p-mediana: búsqueda exhaustiva, ILP y búsqueda local)")
curva = an["curva"].assign(S=lambda d: d["S"].map(conjunto))
c1, c2 = st.columns([2, 1])
c1.line_chart(an["curva"].set_index("p")["f"], x_label="número de acopios p", y_label="kg perdidos por día f(p)")
c2.dataframe(curva, hide_index=True, width="stretch", column_config={"f": st.column_config.NumberColumn(format="%.3f")})
st.dataframe(an["metodos"].assign(S=lambda d: d["S"].map(conjunto)), hide_index=True, width="stretch",
             column_config={"f": st.column_config.NumberColumn(format="%.4f"), "gap_pct": st.column_config.NumberColumn("gap (%)", format="%.2f")})
st.markdown(f"El codo está en **p = {an['p_codo']}**: **{conjunto(an['S'])}**. San Miguel atiende las zonas del Meta, que en aguas "
            "altas no pueden remontar a Puerto Gaitán a remo.")

st.header("4. El acopio del Manacacías (búsqueda exhaustiva)")
m = an["manacacias"]
st.dataframe(m["tabla"].assign(nombre=m["tabla"]["nombre"]), hide_index=True, width="stretch",
             column_config={"f": st.column_config.NumberColumn("kg perdidos/día con ese acopio", format="%.3f"),
                            "si_todos": st.column_config.NumberColumn("pérdida si todas las zonas entregaran ahí", format="%.3f")})
st.markdown(f"El mejor punto del Manacacías es **{m['nombre']}** ({m['pueblo']} [CONFIRMAR]). Con los otros dos acopios, baja la pérdida "
            f"en **{m['ganancia']:.3f} kg/día**: las zonas del Manacacías ya bajan rápido a Puerto Gaitán.")

st.header("5. Puntos fríos: dónde recoger hielo en la ruta (búsqueda exhaustiva)")
st.dataframe(frios["curva"].assign(S=lambda d: d["S"].map(conjunto)), hide_index=True, width="stretch",
             column_config={"p": "puntos fríos extra", "f": st.column_config.NumberColumn("kg perdidos/día", format="%.3f")})
st.markdown(f"Candidatos (pueblos con embarcadero que no son acopio): {conjunto(frios['candidatos'])}. La Cristalina queda fija. "
            f"Elegidos por el algoritmo: **{conjunto(frios['elegidos']) or 'ninguno además de La Cristalina'}**.")

st.header("6. Verificación de las rutas: Dijkstra, A*, BFS y DFS")
alg = an["algoritmos"]
rutas = alg["rutas"].assign(zona=lambda d: d["zona"].map(lambda i: g.nodes[i]["nombre"]), acopio=lambda d: d["acopio"].map(nombre))
st.dataframe(rutas, hide_index=True, width="stretch",
             column_config={"dq_dijkstra": st.column_config.NumberColumn("ΔQ Dijkstra", format="%.4f"),
                            "dq_a_estrella": st.column_config.NumberColumn("ΔQ A*", format="%.4f")})
st.markdown(f"A\\* llega al mismo costo que Dijkstra en todas las rutas. DFS (Tarjan): la red tiene {alg['componentes']} componente(s) y "
            f"{len(alg['articulaciones'])} puntos críticos; si uno de ellos se corta, alguna zona se queda sin su acopio.")

st.header("7. Referencias: ¿por qué pueblos y no otro punto?")
libre = an["libre"]
ref = pd.DataFrame([
    {"referencia": "Propuesta", "S": conjunto(an["propuesta"]), "kg perdidos/día": an["f_propuesta"]},
    {"referencia": "Acopios de hoy", "S": conjunto(an["actuales"]), "kg perdidos/día": an["f_actuales"]},
    {"referencia": "p-mediana libre (cualquier punto del río)", "S": conjunto(libre["S"]) if libre else "—", "kg perdidos/día": libre["f"] if libre else None},
    {"referencia": "Centroide de las zonas (1 acopio)", "S": nombre(an["centroide"]), "kg perdidos/día": an["f_centroide_p1"]},
])
st.dataframe(ref, hide_index=True, width="stretch", column_config={"kg perdidos/día": st.column_config.NumberColumn(format="%.3f")})

st.header("8. Veredicto por acopio")
mc = pre["mc"] if pre is not None else None
via = acopios.viabilidad(an, list(an["propuesta"]), mc)
st.dataframe(via.drop(columns=["acopio"]), hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="%,.0f") for c in ("beneficio_anual", "inversion", "vpn", "vpn_p5", "vpn_p95")})
umbral = 100 * config.parametro("economia.umbral_vpn_positivo")
st.caption(f"Regla: vale la pena si el VPN a {config.parametro('economia.horizonte_anios')} años es positivo en al menos el {umbral:.0f} % de las "
           "corridas de Monte Carlo. Pérdida evitada = f(sin el acopio) − f(con todos). Costos: SIMULADO.")

if pre is not None:
    st.header("9. ¿Cambia la conclusión? (sensibilidad)")
    st.dataframe(pre["sensibilidad"].assign(S=lambda d: d["S"].map(conjunto)), hide_index=True, width="stretch")

if st.button("Activar esta propuesta en el escenario", key="activar_propuesta"):
    centros = set(config.cargar_centros_poblados()["id"])
    st.session_state["escenario"] = escenario.con(acopios_grafo=frozenset(j for j in an["propuesta"] if j in centros),
                                                  puntos_frios_grafo=frozenset(frios["todos"]))
    st.rerun()
