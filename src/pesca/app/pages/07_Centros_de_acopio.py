import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from pesca import asignacion, config, red, ubicacion, visualizacion
from pesca.app import comun

comun.configurar_pagina("Centros de acopio")
escenario = comun.barra_lateral()


@st.cache_data
def precalculado():
    return ubicacion.cargar_precalculado()


def activar(nuevo) -> None:
    st.session_state["escenario"] = nuevo
    st.rerun()


st.title("Centros de acopio: ¿sirven los de hoy? ¿dónde deberían estar?")
datos = precalculado()
if datos is None:
    st.error("Faltan los resultados. Córrelos con `python scripts/correr_todo.py --solo r4`.")
    st.stop()

grafo = red.construir_red()
umbral = 100 * config.parametro("economia.umbral_vpn_positivo")
anios = config.parametro("economia.horizonte_anios")

# ---------------------------------------------------------------- 1. viabilidad
st.header("1. ¿Vale la pena rehabilitar los cuartos fríos?")
st.markdown(
    f"**Regla de decisión:** un acopio **vale la pena** si su valor presente neto (VPN) a {anios} años es positivo "
    f"en al menos el **{umbral:.0f} %** de las {datos['meta']['corridas']} corridas de Monte Carlo. "
    "El beneficio es lo que se deja de perder (pescado dañado + viaje de los pescadores) en el mejor reparto de la flota; "
    "los costos son la rehabilitación, la operación y **la energía**, que fue lo que hizo abandonar el cuarto frío de San Miguel."
)
resumen = ubicacion.resumen_viabilidad(datos["viabilidad"])
acopios_del_escenario = {"A02": {"A02"}, "A03": {"A03"}, "todos": {"A02", "A03"}}
for fila in resumen.itertuples():
    with st.container(border=True):
        veredicto = "✅ VALE LA PENA" if fila.vale_la_pena else "❌ NO VALE LA PENA"
        st.markdown(f"#### {fila.nombre}: {veredicto}")
        st.caption(f"VPN > 0 en el {fila.pct_vpn_positivo:.0f} % de las corridas (la regla pide {umbral:.0f} %).")
        c1, c2, c3 = st.columns(3)
        c1.metric("VPN medio", f"{asignacion.pesos(fila.vpn_media / 1e6)} M")
        c1.caption(f"90 %: {fila.vpn_p5 / 1e6:,.0f} a {fila.vpn_p95 / 1e6:,.0f} millones".replace(",", "."))
        c2.metric("Valor que se salva al año", f"{asignacion.pesos(fila.beneficio_anual_media / 1e6)} M")
        c2.caption(f"{fila.kg_salvados_dia_media:.0f} kg/día más se venden · uso del cuarto frío {fila.uso_pct_media:.0f} %")
        c3.metric("Energía al año", f"{asignacion.pesos(fila.energia_anual_media / 1e6)} M")
        if fila.equilibrio_cop_kwh > 0:
            c3.caption(f"El VPN medio llega a 0 con la luz a {asignacion.pesos(fila.equilibrio_cop_kwh)}/kWh")
        else:
            c3.caption("Ni con la luz gratis el VPN medio es positivo")
        nuevos_activos = acopios_del_escenario[fila.acopio]
        if nuevos_activos <= escenario.acopios_activos:
            st.caption("✔ Ya está activo en el escenario.")
        elif st.button("Activar en el escenario", key=f"activar_{fila.acopio}"):
            activar(escenario.con(acopios_activos=frozenset(escenario.acopios_activos | nuevos_activos)))
st.altair_chart(visualizacion.grafico_vpn(resumen), width="stretch")
st.caption(
    f"{comun.etiqueta('SIMULADO')}: costos de rehabilitación, operación, consumo de energía y tarifa. "
    "Cada corrida cambia los parámetros dentro de sus rangos, la población de pescadores y la temporada."
)

# ---------------------------------------------------------------- 2. reubicacion
st.header("2. ¿Están bien ubicados?")
st.markdown(
    "Con la **p-mediana** se buscan los puntos del río donde poner los acopios para que se pierda lo menos posible "
    "(pescado dañado + viaje), sumando sobre todos los pescadores según sus kilos."
)
pm = datos["pmediana"]
resultados = pd.DataFrame(pm["resultados"])
modo = st.radio("¿Qué quieres ver?", ["mover", "agregar"], horizontal=True, key="modo_pmediana",
                format_func={"mover": "Mover los 3 acopios", "agregar": "Mantener los de hoy y agregar"}.get)
if modo == "mover":
    elegido = resultados[(resultados["modo"] == "mover") & (resultados["p"] == 3)].iloc[0]
else:
    k = st.select_slider("¿Cuántos acopios agregar?", options=sorted(resultados["k"].dropna().astype(int)), value=1)
    elegido = resultados[(resultados["modo"] == "agregar") & (resultados["k"] == k)].iloc[0]

propuestos = elegido["acopios"]
st_folium(
    visualizacion.mapa_acopios(grafo, list(ubicacion.ACTUALES), propuestos, elegido["asignacion"]),
    height=440, use_container_width=True, returned_objects=[],
)
st.caption("🏠 rojo: acopios de hoy · ⭐ azul: acopios propuestos · líneas: a qué acopio va cada zona.")

ahorro = pm["costo_actuales_dia"] - elegido["costo_dia"]
c1, c2 = st.columns(2)
c1.metric("Con los 3 acopios de hoy", f"{asignacion.pesos(pm['costo_actuales_dia'])}/día")
c2.metric("Con la propuesta", f"{asignacion.pesos(elegido['costo_dia'])}/día",
          delta=f"-{100 * ahorro / pm['costo_actuales_dia']:.0f} %", delta_color="inverse")

tabla = pd.DataFrame(propuestos)[["lugar", "nombre", "rio", "lat", "lon", "actual"]]
tabla["actual"] = tabla["actual"].map({True: "existe hoy", False: "nuevo"})
st.dataframe(tabla, hide_index=True, width="stretch",
             column_config={"lat": st.column_config.NumberColumn(format="%.4f"), "lon": st.column_config.NumberColumn(format="%.4f"),
                            "actual": "estado"})
c1, c2 = st.columns(2)
c1.download_button("⬇ Descargar coordenadas (CSV)", tabla.to_csv(index=False).encode("utf-8"),
                   file_name=f"acopios_propuestos_{modo}.csv", mime="text/csv")
if c2.button("Activar estos acopios en el escenario", key="activar_propuesta"):
    activar(ubicacion.escenario_con_propuesta(escenario, propuestos))
st.caption(
    "Al activarlos, aparecen en «¿A dónde llevo mi pescado?» y en «Toda la flota». "
    "Las coordenadas de los puntos nuevos salen de trazas aproximadas del río (validado = no)."
)

st.subheader("¿Cuántos acopios hacen falta?")
codo = resultados[resultados["modo"] == "mover"][["p", "costo_dia"]]
st.altair_chart(visualizacion.grafico_codo(codo, pm["costo_actuales_dia"], 3), width="stretch")
st.caption(
    "Cada acopio más reduce la pérdida, pero cada vez menos (el «codo»). La línea punteada es el costo con los 3 de hoy. "
    "La p-mediana no limita la capacidad de cada acopio; las capacidades entran en «Toda la flota»."
)
