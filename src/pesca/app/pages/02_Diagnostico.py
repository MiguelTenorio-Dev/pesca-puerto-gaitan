import streamlit as st
from streamlit_folium import st_folium

from pesca import cadena_actual, config, visualizacion
from pesca.app import comun
from pesca.escenario import Escenario

comun.configurar_pagina("Diagnóstico: la situación hoy")
escenario = comun.barra_lateral()
hoy = cadena_actual.escenario_hoy(escenario)


@st.cache_data
def precalculado():
    return cadena_actual.cargar_precalculado()


@st.cache_resource
def ejemplo(esc: Escenario):
    corrida = cadena_actual.corrida_ejemplo(esc)
    return corrida, cadena_actual.flujos(corrida), cadena_actual.por_pescador(corrida)


nodos = config.cargar_nodos().set_index("id")
datos = precalculado()
if datos is None:
    st.error("Faltan los resultados de Monte Carlo. Córrelos con `python scripts/correr_todo.py --solo r2`.")
    st.stop()

corridas = datos["corridas"]
sub = corridas[(corridas["candidata"] == hoy.desembarque_senora) & (corridas["temporada"] == hoy.temporada)]
r = cadena_actual.resumen(sub)


def intervalo(fila: str, formato: str = "{:.2f}") -> str:
    return f"{formato.format(r.at[fila, 'p5'])} – {formato.format(r.at[fila, 'p95'])}"


st.title(f"Hoy, el pescado pierde el {r.at['pct_valor_perdido', 'media']:.0f} % de su valor antes de venderse")
st.markdown(
    f"Simulación de la cadena de hoy, pescador por pescador, en un mes típico fuera de veda. "
    f"Las cifras salen de **{datos['meta']['corridas']} corridas de Monte Carlo**: se muestra la media y, debajo, "
    "el rango donde cae el 90 % de los resultados. "
    f"{comun.etiqueta('OFICIAL')} volúmenes (SEPEC 2022) y precios (SIPSA) · {comun.etiqueta('MEDIDO')} distancias · "
    f"{comun.etiqueta('SIMULADO')} todo lo demás."
)
if escenario.hielo_a_bordo or escenario.camion_refrigerado:
    st.info("El diagnóstico es la situación de hoy: no usa el hielo a bordo ni el camión refrigerado de la barra lateral.")
st.caption(
    f"Desembarque de la señora: **{nodos.at[hoy.desembarque_senora, 'nombre'].split(': ')[-1]}** · "
    f"temporada: **{comun.TEXTO_TEMPORADA[hoy.temporada]}** (se cambian en la barra lateral)."
)

c1, c2, c3 = st.columns(3)
c1.metric("Calidad al vender (0 a 1)", f"{r.at['calidad_media', 'media']:.2f}", help="1 = recién pescado; por debajo de 0,25 lo rechazan")
c1.caption(f"90 %: {intervalo('calidad_media')}")
c2.metric("Valor perdido", f"{r.at['pct_valor_perdido', 'media']:.0f} %")
c2.caption(f"90 %: {intervalo('pct_valor_perdido', '{:.0f} %')}")
c3.metric("Plata perdida al mes", f"${r.at['cop_perdidos_mes', 'media'] / 1e6:.1f} millones")
c3.caption(f"90 %: {intervalo('cop_perdidos_mes', '{:,.0f}').replace(',', '.')} COP")
c1, c2, c3 = st.columns(3)
c1.metric("Pescado rechazado al mes", f"{r.at['kg_rechazados_mes', 'media']:,.0f} kg".replace(",", "."))
c1.caption(f"90 %: {intervalo('kg_rechazados_mes', '{:,.0f}').replace(',', '.')} kg")
c2.metric("Donde la señora: se desborda a icopor", f"{r.at['pct_desborde_senora', 'media']:.0f} %",
          help="Parte del pescado que no cabe en los congeladores y espera en neveras de icopor")
c2.caption(f"90 %: {intervalo('pct_desborde_senora', '{:.0f} %')}")
pct_espera = r.at["espera_mayor_que_rio", "media"]
c3.metric("La espera pesa más que el río", f"en el {pct_espera:.0f} % de las corridas")
c3.caption(f"Pérdida en la espera ÷ pérdida en el río: {r.at['razon_espera_rio', 'media']:.0f} veces (90 %: {intervalo('razon_espera_rio', '{:.1f}')})")
if r.at["pct_desviados", "media"] > 0.5:
    st.caption(
        f"⚠️ En promedio el {r.at['pct_desviados', 'media']:.1f} % del pescado no puede remontar la corriente hasta su "
        "desembarque habitual y se vende río abajo, en el centro más cercano."
    )

if pct_espera >= 50:
    st.success("**Hipótesis confirmada:** la mayor pérdida no ocurre en el río (horas) sino en la espera hasta que llega el comprador (días).")
else:
    st.warning("**Hipótesis descartada:** en la mayoría de las corridas el río pesa más que la espera.")

st.subheader("¿En qué etapa se pierde el valor?")
st.markdown("Pesos por kilo, desde lo que valdría el pescado recién sacado hasta lo que recibe el pescador. La línea gris es el rango del 90 %.")
st.altair_chart(visualizacion.grafico_cascada(cadena_actual.pasos_cascada(r)), width="stretch")
st.caption(
    "La congelación lenta de un congelador casero daña la textura y baja el precio (factor_precio_congelado, SIMULADO). "
    "Las etapas suman exactamente la pérdida total."
)

corrida, flujos, pescadores = ejemplo(hoy)

st.subheader("Los recorridos de hoy")
st.markdown(
    "Por dónde viaja el pescado en un ciclo simulado. El grosor es proporcional a los kilos. "
    "🟢 río a favor de la corriente · 🔴 río contra la corriente · ⚫ carretera (punteada). "
    "Círculos: 🔵 Malecón (venta directa) · 🟠 San Miguel · 🟢 la señora · 🟡 Vichada."
)
vendieron = corrida.lotes.dropna(subset=["sitio_venta"])
desembarques = dict(zip(vendieron["desembarque"], vendieron["sitio_venta"]))
st_folium(visualizacion.mapa_recorridos(corrida.tiempos.grafo, flujos, desembarques), height=480,
          use_container_width=True, returned_objects=[])

st.subheader("El congelador de la señora, día a día")
st.markdown(
    f"Un ciclo simulado de **{corrida.ciclos['senora']} días** hasta que llega el comprador. "
    f"Capacidad: **{corrida.capacidad_kg:.0f} kg** (línea punteada). Lo que no cabe espera en neveras de icopor y se daña."
)
st.altair_chart(visualizacion.grafico_inventario(corrida.inventario), width="stretch")
st.caption(f"{comun.etiqueta('CONFIRMAR')}: número y tamaño de los congeladores, cortes de luz y días de espera.")

st.subheader("¿Qué zonas pierden más?")
zonas = datos["zonas"]
zonas = zonas[(zonas["candidata"] == hoy.desembarque_senora) & (zonas["temporada"] == hoy.temporada)].copy()
zonas["nombre"] = zonas["zona"].map(nodos["nombre"])
st.altair_chart(visualizacion.grafico_zonas(zonas), width="stretch")
st.dataframe(
    zonas[["nombre", "kg_mes", "calidad_media", "pct_valor_perdido", "pct_valor_perdido_p5", "pct_valor_perdido_p95"]],
    hide_index=True, width="stretch",
    column_config={
        "nombre": "zona",
        "kg_mes": st.column_config.NumberColumn("kg al mes", format="%.0f"),
        "calidad_media": st.column_config.NumberColumn("calidad al vender", format="%.2f"),
        "pct_valor_perdido": st.column_config.NumberColumn("% perdido", format="%.0f"),
        "pct_valor_perdido_p5": st.column_config.NumberColumn("p5", format="%.0f"),
        "pct_valor_perdido_p95": st.column_config.NumberColumn("p95", format="%.0f"),
    },
)

st.subheader("¿Importa dónde está el desembarque de la señora?")
sens = cadena_actual.sensibilidad(corridas, hoy.temporada)
cambia, texto = cadena_actual.veredicto_sensibilidad(sens)
(st.warning if cambia else st.success)(texto)
sens = sens.assign(candidata=sens["candidata"].map(lambda i: nodos.at[i, "nombre"].split(": ")[-1]))
st.dataframe(
    sens[["candidata", "calidad_media_media", "pct_valor_perdido_media", "pct_valor_perdido_p5", "pct_valor_perdido_p95",
          "horas_rio_media_media", "pct_corridas_espera_mayor"]],
    hide_index=True, width="stretch",
    column_config={
        "calidad_media_media": st.column_config.NumberColumn("calidad al vender", format="%.2f"),
        "pct_valor_perdido_media": st.column_config.NumberColumn("% perdido", format="%.0f"),
        "pct_valor_perdido_p5": st.column_config.NumberColumn("p5", format="%.0f"),
        "pct_valor_perdido_p95": st.column_config.NumberColumn("p95", format="%.0f"),
        "horas_rio_media_media": st.column_config.NumberColumn("horas de río", format="%.1f"),
        "pct_corridas_espera_mayor": st.column_config.NumberColumn("% corridas: espera > río", format="%.0f"),
    },
)
st.caption("Las cuatro candidatas usan las mismas muestras de Monte Carlo: la diferencia se debe solo a la ubicación.")

with st.expander("Pescador por pescador (ciclo simulado)"):
    st.dataframe(
        pescadores.assign(embarcacion=pescadores["embarcacion"].map(comun.TEXTO_EMBARCACION)),
        hide_index=True, width="stretch",
        column_config={c: st.column_config.NumberColumn(format="%.1f") for c in
                       ["km_rio", "km_carretera", "pct_contra_corriente", "kg", "horas_totales"]}
        | {"calidad": st.column_config.NumberColumn(format="%.2f"),
           **{c: st.column_config.NumberColumn(format="%.0f") for c in pescadores.columns if c.startswith("cop_") or c == "precio_cop_kg"}},
    )
    st.caption(f"{comun.etiqueta('SIMULADO')}: pescadores sintéticos, sin datos personales.")

with st.expander("Supuestos de esta pantalla"):
    st.markdown(
        """
- **Volumen:** SEPEC 2022 × factor de subregistro. Lo registrado desembarca en el Malecón (venta directa) y en San Miguel;
  lo no registrado va donde la señora (cuenca del Meta) y a los cruces con la vía (Vichada).
- **San Miguel:** el cuarto frío no se usa porque no se pudo pagar la luz. Hoy el pescado espera en icopor al comprador.
- **Deterioro:** RRS(T) = (1 + 0,1·T)², calidad = 1 − Σ horas·RRS / VU0. Congelado no se daña, pero la congelación lenta baja el precio.
- **Cortes de luz:** si duran más de lo que aguanta el congelador, el pescado se deteriora a temperatura ambiente durante el exceso.
- Todos los valores y rangos están en la página **Supuestos y datos**.
"""
    )
