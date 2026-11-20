import pandas as pd
import pytest

from pesca import config

from pesca import asignacion as asg
from pesca import cadena_actual, config, poblacion
from pesca import frio_bimodal as fb
from pesca.escenario import Escenario

BASE = Escenario.base()
POB = cadena_actual.corrida_ejemplo(BASE).poblacion


@pytest.fixture(scope="module")
def solas():
    return fb.tabla_portafolios(BASE, POB, [frozenset(), *fb.medidas_solas()]).set_index("portafolio")


def test_enumeracion_valida():
    portafolios = fb.enumerar_portafolios()
    # I3a, I3b, I6 e I7 (e I4 solo si hay un pueblo nuevo candidato), cada una si o no
    binarias = 5 if fb.acopio_nuevo() else 4
    assert len(portafolios) == len(set(portafolios)) == 3 * 4 * 2**binarias
    assert frozenset() in portafolios
    for pf in portafolios:
        fb.validar(pf)
        assert not ("I2" in pf and "I1" not in pf)
        assert sum(m.startswith("I5:") for m in pf) <= 1


def test_i2_sin_i1_no_es_valido():
    with pytest.raises(ValueError):
        fb.validar(frozenset({"I2"}))
    with pytest.raises(ValueError):
        fb.validar(frozenset({"I5:1", "I5:3"}))


def test_clave_ida_y_vuelta():
    for pf in fb.enumerar_portafolios()[:40]:
        assert fb.desde_clave(fb.clave(pf)) == pf


def test_escenario_con_enciende_cada_medida():
    esc = fb.escenario_con(BASE, frozenset({"I1", "I2", "I3a", "I3b", "I5:3", "I6", "I7"}))
    assert esc.cajas_termicas and esc.hielo_a_bordo and esc.camion_refrigerado
    assert esc.ciclo_camion_dias == 3 and esc.subsidio_motor and esc.desembarque_mejorado
    assert {"A02", "A03"} <= esc.acopios_activos
    assert fb.escenario_con(BASE, frozenset()) == BASE


def test_hoy_no_cambia_con_todo_apagado():
    # Sin medidas el resultado es el mismo de R3/R4: no se rompe el diagnostico
    hoy = asg.problema_transporte(BASE, POB, con_hoy=False)["costo_optimo_dia"]
    assert asg.problema_transporte(fb.escenario_con(BASE, frozenset()), POB, con_hoy=False)["costo_optimo_dia"] == hoy
    assert cadena_actual.escenario_hoy(fb.escenario_con(BASE, frozenset({"I5:1", "I7", "I6"}))) == BASE


def test_camion_mas_seguido_menos_espera():
    esperas = [asg.dias_espera_esperados(BASE.con(ciclo_camion_dias=n)) for n in (1, 3, 7)]
    assert esperas == sorted(esperas)
    assert esperas[-1] < asg.dias_espera_esperados(BASE)


def test_cada_medida_sola_no_empeora(solas):
    # El subsidio de motor (I6) es la excepcion: el pescador pasa de remo a motor y paga la gasolina, y en una
    # poblacion puede perder un poco; en el Monte Carlo de R5 salva valor en promedio.
    sin_motor = solas.drop(index=[i for i in solas.index if "I6" in i])
    assert (sin_motor["valor_salvado_dia"] >= -1e-6).all()
    assert solas.at[fb.HOY, "valor_salvado_dia"] == 0


def test_desembarque_mejorado_sube_el_valor_donde_la_senora():
    o = asg.recomendar("P01@rio", "madera_motor", 20, BASE)
    m = asg.recomendar("P01@rio", "madera_motor", 20, BASE.con(desembarque_mejorado=True))
    senora = next(x for x in o.alternativas if x.destino == BASE.desembarque_senora)
    mejor = next(x for x in m.alternativas if x.destino == BASE.desembarque_senora)
    assert mejor.prob_congelador == 1.0
    assert mejor.cop_kg >= senora.cop_kg


def test_subsidio_cambia_solo_botes_a_remo():
    sub = poblacion.aplicar_subsidio_motor(POB)
    cambiados = sub["embarcacion"] != POB["embarcacion"]
    assert (POB.loc[cambiados, "embarcacion"] == "madera_remo").all()
    assert (sub.loc[cambiados, "embarcacion"] == "madera_motor").all()
    assert sub.equals(poblacion.aplicar_subsidio_motor(POB))  # misma semilla, mismo resultado


def test_costos_del_camion_bajan_con_n():
    ops = [fb.costos(frozenset({f"I5:{n}"}), fb.escenario_con(BASE, frozenset({f"I5:{n}"})), POB)["operacion_anual"]
           for n in (1, 3, 7)]
    assert ops == sorted(ops, reverse=True)
    assert fb.km_ruta_camion(BASE.con(ciclo_camion_dias=1)) > 0


def test_frontera_de_pareto_a_mano():
    t = pd.DataFrame({"inversion": [0, 10, 10, 20, 30], "beneficio_anual": [0, 5, 3, 5, 9]})
    assert list(fb.frontera_pareto(t)) == [True, True, False, False, True]


def test_recomendado_no_excede_el_presupuesto():
    t = pd.DataFrame({"portafolio": ["hoy", "a", "b", "c"], "inversion": [0, 50, 120, 300], "vpn": [0, 10, 40, 90]})
    for presupuesto, esperado in ((100, "a"), (150, "b"), (500, "c"), (0, "hoy")):
        r = fb.recomendado(t, presupuesto)
        assert r["inversion"] <= presupuesto and r["portafolio"] == esperado


def test_precalculado_respeta_los_presupuestos():
    datos = fb.cargar_precalculado()
    if datos is None:
        pytest.skip("Falta el precalculado de R5")
    tabla = datos["portafolios"].set_index("portafolio")
    assert len(tabla) == len(fb.enumerar_portafolios())
    for presupuesto, pf in datos["meta"]["recomendados"].items():
        assert tabla.at[pf, "inversion"] <= float(presupuesto)
        caben = tabla[tabla["inversion"] <= float(presupuesto)]
        assert tabla.at[pf, "vpn"] == caben["vpn"].max()


def test_pasos_combinados_suman_el_portafolio(solas):
    pf = frozenset({"I3a", "I6", "I7"})
    subtabla = fb.tabla_portafolios(BASE, POB, [frozenset(s) for n in range(1, 4) for s in _subconjuntos(pf, n)])
    tabla = pd.concat([solas.reset_index(), subtabla]).drop_duplicates("portafolio")
    pasos = fb.pasos_combinados(tabla, pf)
    assert len(pasos) == 3
    assert pasos[-1]["portafolio"] == fb.clave(pf)


def _subconjuntos(pf, n):
    import itertools
    return itertools.combinations(sorted(pf), n)


def test_montecarlo_reproducible():
    pfs = [frozenset(), frozenset({"I7"})]
    with config.sobrescribir({}):
        a = fb.montecarlo_portafolios(pfs, n=2, semilla=7)
        b = fb.montecarlo_portafolios(pfs, n=2, semilla=7)
    pd.testing.assert_frame_equal(a, b)
    assert set(fb.resumen_montecarlo(a)["portafolio"]) == {"hoy", "I7"}


def test_acopio_nuevo_solo_en_un_centro_poblado():
    """I4 va en el mejor pueblo que todavia no es acopio; hoy los tres candidatos ya lo son, asi que no esta."""
    if fb.pueblo_nuevo() is None:
        assert fb.acopio_nuevo() is None
        assert not any("I4" in pf for pf in fb.enumerar_portafolios())
        with pytest.raises(ValueError, match="I4"):
            fb.validar(frozenset({"I4"}))
        assert "No disponible" in fb.texto_acopio_nuevo()
    else:
        assert fb.pueblo_nuevo() in set(config.cargar_centros_poblados()["id"])
