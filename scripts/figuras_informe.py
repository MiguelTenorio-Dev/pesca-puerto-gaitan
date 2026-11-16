"""Figuras del informe (outputs/figuras/*.png) a partir de lo precalculado.

Uso: python scripts/figuras_informe.py
El mapa de la red (F1) se captura con Google Chrome sin ventana; si no esta, se omite.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from pesca import (busqueda, cadena_actual, comparacion, config, frio_bimodal, red, transporte,  # noqa: E402
                   ubicacion, visualizacion)
from pesca.escenario import Escenario  # noqa: E402

DESTINO = config.DIR_REPO / "outputs" / "figuras"
AZUL, NARANJA, GRIS = visualizacion.COLOR_VALOR, visualizacion.COLOR_PERDIDA, visualizacion.COLOR_TEXTO_SECUNDARIO
NOTA = "SIMULADO: supuestos del proyecto (especificación §10)"
ANCHO_MAPA, ALTO_MAPA = 1400, 900
ESPERA_TESELAS_MS = 8000


def _guardar(fig, nombre: str, nota: bool = True) -> None:
    if nota:
        fig.text(0.01, -0.04, NOTA, fontsize=8, color=GRIS, style="italic")
    fig.savefig(DESTINO / nombre, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {nombre}")


def f1_mapa_red() -> None:
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if chrome is None:
        print("  f1 omitida: no hay Chrome")
        return
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "red.html"
        visualizacion.mapa_red(red.construir_red()).save(str(html))
        subprocess.run([chrome, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={ANCHO_MAPA},{ALTO_MAPA}",
                        f"--virtual-time-budget={ESPERA_TESELAS_MS}", f"--screenshot={DESTINO / 'f1_red.png'}", html.as_uri()],
                       check=True, capture_output=True)
    print("  f1_red.png")


def f2_cascada() -> None:
    r2 = cadena_actual.cargar_precalculado()["corridas"]
    base = config.parametro("escenario_base.desembarque_senora")
    fig, ejes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for ax, t in zip(ejes, comparacion.TEMPORADAS):
        r = cadena_actual.resumen(r2[(r2["candidata"] == base) & (r2["temporada"] == t)])
        etapas = [("faena", "faena"), ("rio", "río"), ("espera", "espera"), ("congelacion_lenta", "congel.\nlenta"),
                  ("carretera", "carretera")]
        nivel = r.at["precio_base", "media"]
        ax.bar(0, nivel, color=AZUL)
        for i, (e, texto) in enumerate(etapas, start=1):
            v = r.at[f"cop_kg_{e}", "media"]
            ax.bar(i, -v, bottom=nivel, color=NARANJA)
            ax.text(i, nivel + 120, f"{v:,.0f}".replace(",", "."), ha="center", fontsize=9)
            nivel -= v
        ax.bar(len(etapas) + 1, r.at["cop_kg_recibido", "media"], color=AZUL)
        ax.set_xticks(range(len(etapas) + 2), ["precio\nbase", *[t for _, t in etapas], "recibe"], fontsize=9)
        ax.set_title(comparacion.TEXTO_TEMPORADA[t], pad=18)
        ax.spines[["top", "right"]].set_visible(False)
    ejes[0].set_ylabel("COP por kg (media de 500 corridas)")
    fig.suptitle("¿Dónde se pierde el valor del pescado? (hoy, desembarque base)", y=1.02)
    _guardar(fig, "f2_perdida_por_etapa.png")


def f3_algoritmos() -> None:
    perfil = transporte.Perfil.desde_escenario(Escenario.base(), comparacion.EMBARCACION_ALGORITMOS)
    comp = busqueda.comparar(red.construir_red(), busqueda.pares_comparacion(), perfil)
    tabla = comp.pivot_table(index="par", columns="algoritmo", values="nodos_explorados", sort=False)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ancho = 0.27
    for k, (alg, color) in enumerate((("dijkstra", GRIS), ("a_estrella", AZUL), ("bfs", NARANJA))):
        ax.barh([i + (k - 1) * ancho for i in range(len(tabla))], tabla[alg], height=ancho, color=color,
                label=comparacion.TEXTO_ALGORITMO[alg])
    ax.set_yticks(range(len(tabla)), tabla.index, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("nodos explorados")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Dijkstra vs A* vs BFS: nodos explorados (mismo costo para Dijkstra y A*)")
    _guardar(fig, "f3_algoritmos.png")


def f4_acopios() -> None:
    r4 = ubicacion.cargar_precalculado()
    res = ubicacion.resumen_viabilidad(r4["viabilidad"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [1.3, 1]})
    nombres = ["San Miguel", "Puente Arimena", "Los tres"]
    for i, f in enumerate(res.itertuples()):
        a1.plot([f.vpn_p5 / 1e6, f.vpn_p95 / 1e6], [i, i], color=GRIS, lw=3)
        a1.plot(f.vpn_media / 1e6, i, "o", color=AZUL, ms=10)
        a1.text(f.vpn_media / 1e6, i - 0.18, f"VPN > 0 en el {f.pct_vpn_positivo:.0f} % de las corridas",
                fontsize=9, ha="center", va="bottom")
    a1.axvline(0, color=NARANJA, ls="--")
    a1.set_yticks(range(len(res)), nombres)
    a1.set_ylim(len(res) - 0.5, -0.7)
    a1.set_xlabel("VPN a 5 años (millones de COP): media e IC 90 %")
    a1.set_title("¿Vale la pena rehabilitar? (regla: VPN > 0 en ≥ 70 %)")
    codo = [r for r in r4["pmediana"]["resultados"] if r["modo"] == "mover"]
    a2.plot([r["p"] for r in codo], [r["costo_dia"] / 1e6 for r in codo], "o-", color=AZUL)
    a2.axhline(r4["pmediana"]["costo_actuales_dia"] / 1e6, color=GRIS, ls="--", label="los 3 acopios de hoy")
    a2.set_xlabel("número de acopios (p-mediana)")
    a2.set_ylabel("pérdida + viaje (millones COP/día)")
    a2.legend(frameon=False)
    a2.set_title("Curva del codo")
    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
    _guardar(fig, "f4_acopios.png")


def f5_pareto() -> None:
    r5 = frio_bimodal.cargar_precalculado()
    t = r5["portafolios"]
    recomendados = set(r5["meta"]["recomendados"].values())
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.scatter(t["inversion"] / 1e6, t["beneficio_anual"] / 1e6, s=14, color="#c8c8c8", label="combinaciones")
    p = t[t["pareto"]].sort_values("inversion")
    ax.step(p["inversion"] / 1e6, p["beneficio_anual"] / 1e6, where="post", color=AZUL, label="frontera de Pareto")
    ax.scatter(p["inversion"] / 1e6, p["beneficio_anual"] / 1e6, s=30, color=AZUL)
    rec = t[t["portafolio"].isin(recomendados)]
    ax.scatter(rec["inversion"] / 1e6, rec["beneficio_anual"] / 1e6, s=90, color=NARANJA, zorder=3, label="recomendado")
    for f in rec.itertuples():
        ax.annotate(" + ".join(frio_bimodal.describir(frio_bimodal.desde_clave(f.portafolio))),
                    (f.inversion / 1e6, f.beneficio_anual / 1e6), xytext=(8, -12), textcoords="offset points", fontsize=8)
    for b in config.parametro("inversiones.presupuestos_cop"):
        ax.axvline(b / 1e6, color=GRIS, ls=":", lw=1)
    ax.set_xlabel("inversión inicial (millones de COP)")
    ax.set_ylabel("valor salvado al año (millones de COP)")
    ax.set_title("Portafolios I1–I7: inversión vs valor salvado (líneas: presupuestos)")
    ax.legend(frameon=False, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    _guardar(fig, "f5_pareto.png")


def f6_hoy_vs_propuesta() -> None:
    r6 = comparacion.cargar_precalculado()["pescadores"]
    indicadores = [("pct_valor_perdido", "% del valor perdido"), ("kg_perdidos_dia", "kg perdidos al día"),
                   ("horas", "horas hasta la venta")]
    fig, ejes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, (ind, texto) in zip(ejes, indicadores):
        for k, t in enumerate(comparacion.TEMPORADAS):
            tot = comparacion.totales(r6[r6["temporada"] == t])
            ax.bar(k - 0.18, tot.at[ind, "hoy"], width=0.36, color=NARANJA, label="hoy" if k == 0 else None)
            ax.bar(k + 0.18, tot.at[ind, "propuesta"], width=0.36, color=AZUL, label="propuesta" if k == 0 else None)
        ax.set_xticks([0, 1], ["aguas bajas", "aguas altas"])
        ax.set_title(texto)
        ax.spines[["top", "right"]].set_visible(False)
    ejes[0].legend(frameon=False)
    fig.suptitle("Hoy vs propuesta (San Miguel + acopio nuevo, con el recomendador)", y=1.04)
    _guardar(fig, "f6_hoy_vs_propuesta.png")


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for figura in (f1_mapa_red, f2_cascada, f3_algoritmos, f4_acopios, f5_pareto, f6_hoy_vs_propuesta):
        figura()


if __name__ == "__main__":
    main()
