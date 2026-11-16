import pytest

from pesca import asignacion as asg, config, poblacion, red
from pesca.escenario import Escenario

G = red.construir_red()
BASE = Escenario.base()
CON_SAN_MIGUEL = BASE.con(acopios_activos={"A01", "A02"})


def _ubicaciones(zonas):
    return sorted({n for z in zonas for n in poblacion._ubicaciones_cercanas(G, z)})


# ---------------------------------------------------------------- recomendador


@pytest.mark.parametrize("temporada", sorted(config.TEMPORADAS))
def test_prueba_de_sentido(temporada):
    # Con San Miguel activo, un pescador del Meta bajo a remo y sin hielo nunca va por rio a Puerto Gaitan
    esc = CON_SAN_MIGUEL.con(temporada=temporada)
    for origen in _ubicaciones(["P02", "P12"]):
        rec = asg.recomendar(origen, "madera_remo", 20, esc, "sin_hielo")
        assert rec.mejor is not None, origen
        assert rec.mejor.tipo != "plaza", origen
        assert rec.mejor.destino == "A02", origen


def test_ejemplo_meta_bajo():
    hoy = asg.recomendar("P02@rio", "madera_remo", 20, BASE, "sin_hielo")
    assert all(o.cop_total == 0 for o in hoy.alternativas)
    assert "ninguna opción salva" in hoy.explicacion
    con_camion = asg.recomendar("P02@rio", "madera_remo", 20, CON_SAN_MIGUEL.con(camion_refrigerado=True), "sin_hielo")
    assert con_camion.mejor.destino == "A02"
    assert con_camion.mejor.cop_total == pytest.approx(144_700, rel=0.02)
    con_carro = asg.recomendar("P02@rio", "madera_remo", 20, CON_SAN_MIGUEL, "sin_hielo")
    assert con_carro.mejor.cop_total == pytest.approx(82_700, rel=0.02)


def test_explicacion_menciona_corriente_y_transbordo():
    bimodal = asg.recomendar("P02@rio", "madera_remo", 20, CON_SAN_MIGUEL, "sin_hielo")
    assert bimodal.mejor.bimodal
    assert "corriente" in bimodal.explicacion and "transbordo" in bimodal.explicacion
    por_rio = asg.recomendar("P01@rio", "madera_motor", 20, BASE, "buena")
    assert por_rio.mejor.tipo == "plaza"
    assert "corriente" in por_rio.explicacion


def test_remo_en_aguas_altas_no_sube():
    rec = asg.recomendar("P02@rio", "madera_remo", 20, CON_SAN_MIGUEL.con(temporada="aguas_altas"), "sin_hielo")
    rio_arriba = [o for o in rec.alternativas if o.destino in ("D_MALECON", BASE.desembarque_senora)]
    assert rio_arriba and all(not o.factible and "corriente" in o.motivo for o in rio_arriba)


def test_otra_cuenca():
    rec = asg.recomendar("P07@rio", "madera_motor", 20, BASE, "buena")
    plaza = next(o for o in rec.alternativas if o.tipo == "plaza")
    assert not plaza.factible and "cuenca" in plaza.motivo
    assert rec.mejor is not None and rec.mejor.destino == "V01"


@pytest.mark.parametrize("origen", ["P01@rio", "P02@rio", "P03@rio", "P06@rio", "C01@rio"])
def test_opciones_coherentes(origen):
    rec = asg.recomendar(origen, "madera_motor", 30, CON_SAN_MIGUEL, "deteriorada")
    factibles = [o for o in rec.alternativas if o.factible]
    assert factibles
    assert [o.cop_neto for o in factibles] == sorted((o.cop_neto for o in factibles), reverse=True)
    horas_faena = config.parametro("degradacion.horas_faena")
    for o in factibles:
        assert 0 <= o.calidad <= 1
        assert o.km_rio + o.km_via == pytest.approx(o.tramos["km"].sum())
        assert o.horas_viaje == pytest.approx(horas_faena + o.tramos["horas"].sum())
        assert o.horas_hasta_venta == pytest.approx(o.horas_viaje + o.horas_espera)
        assert o.ruta[0] == origen and o.ruta[-1] == asg.PLAZA
        assert o.cop_total + sum(o.cop_perdidos_por_etapa.values()) == pytest.approx(30 * asg.dg.precio_base())
        assert o.cop_neto == pytest.approx(o.cop_total - o.costo_viaje)
        assert o.costo_viaje > 0


def test_acopio_y_camion_no_empeoran():
    origen, emb = "P02@rio", "madera_motor"
    hoy = asg.recomendar(origen, emb, 20, BASE, "deteriorada").mejor
    sm = asg.recomendar(origen, emb, 20, CON_SAN_MIGUEL, "deteriorada")
    camion = asg.recomendar(origen, emb, 20, CON_SAN_MIGUEL.con(camion_refrigerado=True), "deteriorada")
    assert sm.mejor.cop_neto >= hoy.cop_neto
    assert camion.mejor.cop_neto >= sm.mejor.cop_neto
    acopio_sm = next(o for o in sm.alternativas if o.tipo == "acopio")
    acopio_camion = next(o for o in camion.alternativas if o.tipo == "acopio")
    assert acopio_camion.calidad > acopio_sm.calidad


def test_entradas_invalidas():
    with pytest.raises(ValueError):
        asg.recomendar("A01@via", "madera_remo", 20, BASE)
    with pytest.raises(ValueError):
        asg.recomendar("P01@rio", "madera_remo", 0, BASE)
    with pytest.raises(ValueError):
        asg.recomendar("P01@rio", "madera_remo", 10, BASE, "nevera_magica")


def test_nodo_rio_mas_cercano():
    a = G.nodes["P02@rio"]
    assert red.nodo_rio_mas_cercano(a["lat"], a["lon"], G) == "P02@rio"
    n = red.nodo_rio_mas_cercano(4.3, -72.0, G)
    assert G.nodes[n]["capa"] == red.CAPA_RIO


def test_espera_esperada():
    assert asg.dias_espera_esperados() == pytest.approx(6.0)
    assert asg.horas_falla_esperadas(10) == pytest.approx(10 * 0.10 * 1.8)


# ---------------------------------------------------------------- problema de transporte


def test_caso_2x2_a_mano():
    # a y b ofrecen 10 kg cada uno. X cabe 10 kg; Y sin limite.
    # a→X 1, a→Y 5, b→X 2, b→Y 3 (COP/kg). A mano: a→X y b→Y = 10 + 30 = 40 (la otra opcion cuesta 70)
    flujos, costo = asg.resolver_flujo(
        {"a": 10, "b": 10},
        {("a", "X"): 1, ("a", "Y"): 5, ("b", "X"): 2, ("b", "Y"): 3},
        {"X": 10, "Y": None},
        {"a": 100, "b": 100},
    )
    assert flujos == {("a", "X"): 10, ("b", "Y"): 10}
    assert costo == pytest.approx(40)


def test_sin_capacidad_va_a_sin_destino():
    flujos, costo = asg.resolver_flujo({"a": 5}, {("a", "X"): 1}, {"X": 0}, {"a": 100})
    assert flujos == {("a", asg.SIN_DESTINO): 5}
    assert costo == pytest.approx(500)


@pytest.mark.parametrize("escenario", [BASE, CON_SAN_MIGUEL, CON_SAN_MIGUEL.con(camion_refrigerado=True)])
def test_conservacion_y_capacidades(escenario):
    r = asg.problema_transporte(escenario)
    _, oferta = asg._poblacion_y_oferta(escenario)
    por_pescador = r["flujos"].groupby("pescador")["kg_dia"].sum()
    for pescador, kg in oferta.items():
        assert por_pescador[pescador] == pytest.approx(kg, abs=1 / asg.ESCALA_KG)
    assert r["flujos"]["kg_dia"].sum() == pytest.approx(r["kg_dia"], abs=len(oferta) / asg.ESCALA_KG)
    con_tope = r["uso"].dropna(subset=["capacidad_kg_dia"])
    assert (con_tope["kg_dia"] <= con_tope["capacidad_kg_dia"] + 1 / asg.ESCALA_KG).all()
    assert r["costo_optimo_dia"] <= r["costo_hoy_dia"] + 1


def test_capacidades_en_cero():
    ceros = {"acopios.capacidad_plaza_kg_dia": 0.0, "acopios.capacidad_san_miguel_kg": 0.0, "cadena_actual.n_congeladores": 0}
    with config.sobrescribir(ceros):
        r = asg.problema_transporte(CON_SAN_MIGUEL)
    usados = set(r["flujos"].loc[r["flujos"]["kg_dia"] > 0, "destino"])
    assert not any(d.startswith(("plaza:", "acopio:A02")) or d.endswith(":congelador") for d in usados)
    assert r["flujos"]["kg_dia"].sum() == pytest.approx(r["kg_dia"], abs=1)


def test_costo_del_viaje():
    p = config.parametro
    remo = asg.costo_viaje(10, 4, "madera_remo")
    motor = asg.costo_viaje(10, 1, "madera_motor")
    assert remo == pytest.approx(p("pescador.factor_regreso") * 4 * p("pescador.cop_por_hora"))
    assert motor == pytest.approx(p("pescador.factor_regreso") * (10 * p("pescador.cop_por_km_motor") + p("pescador.cop_por_hora")))
    assert asg.costo_viaje(0, 0, "madera_motor") == 0


def test_el_viaje_largo_puede_no_convenir():
    # Si el tiempo del pescador valiera muchisimo, ganaria la opcion con menos horas de rio
    with config.sobrescribir({"pescador.cop_por_hora": 1e7}):
        rec = asg.recomendar("P02@rio", "madera_remo", 20, BASE, "buena")
    horas = [o.tramos.loc[o.tramos["modo"] == red.CAPA_RIO, "horas"].sum() for o in rec.alternativas if o.factible]
    mejor = rec.mejor.tramos.loc[rec.mejor.tramos["modo"] == red.CAPA_RIO, "horas"].sum()
    assert mejor == pytest.approx(min(horas))


def test_explicacion_cuando_salvarlo_no_compensa_el_viaje():
    # Con nevera deteriorada, subir a la plaza salva el pescado, pero 14 h de remo ida y vuelta cuestan mas
    rec = asg.recomendar("P02@rio", "madera_remo", 20, BASE, "deteriorada")
    assert rec.mejor.cop_total == 0
    assert "solo se salva si lo llevas" in rec.explicacion
    assert "te quedarían" in rec.explicacion
