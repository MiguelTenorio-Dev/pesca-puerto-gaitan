import pytest

from pesca import config


def test_semilla_fija():
    assert config.parametro("general.semilla") == 42


def test_cada_hoja_tiene_valor_y_etiqueta_valida():
    hojas = config.hojas_parametros()
    assert len(hojas) > 30
    for ruta, h in hojas:
        assert "valor" in h, ruta
        assert h.get("etiqueta") in config.ETIQUETAS, ruta


def test_valor_dentro_del_rango():
    for ruta, h in config.hojas_parametros():
        if "rango" in h:
            minimo, maximo = h["rango"]
            assert minimo <= h["valor"] <= maximo, ruta


def test_uniformes_bien_formados():
    for ruta in ["cadena_actual.ciclo_comprador_dias", "cadena_actual.horas_corte"]:
        v = config.parametro(ruta)
        assert v["min"] < v["max"]
    assert config.parametro("cadena_actual.ciclo_comprador_dias") == {"min": 7, "max": 15}


def test_escalones_de_precio_bajan_con_la_calidad():
    escalones = config.parametro("precio_calidad.escalones")
    umbrales = [e["calidad_min"] for e in escalones]
    factores = [e["factor"] for e in escalones]
    assert umbrales == sorted(umbrales, reverse=True)
    assert factores == sorted(factores, reverse=True)
    assert all(0 <= f <= 1 for f in factores)
    assert umbrales[-1] == 0 and factores[-1] == 0


def test_mezcla_de_flota_suma_uno():
    assert sum(config.parametro("flota.mezcla").values()) == pytest.approx(1.0)


def test_parametro_inexistente_lanza_error():
    with pytest.raises(KeyError):
        config.parametro("rio.no_existe")
    with pytest.raises(KeyError):
        config.parametro("rio")


def test_nodos_validos():
    nodos = config.cargar_nodos()
    assert nodos["id"].is_unique
    assert set(nodos["tipo"]) <= config.TIPOS_NODO
    assert set(nodos["cuenca"]) <= config.CUENCAS
    assert nodos["lat"].between(3.5, 5.0).all()
    assert nodos["lon"].between(-73.0, -70.5).all()
    assert (nodos["validado"] == "no").all()


def test_nodos_esperados():
    nodos = config.cargar_nodos().set_index("id")
    assert set(nodos.index[nodos["tipo"] == "acopio"]) == {"A01", "A02", "A03"}
    assert nodos.at["C01", "tipo"] == "comunidad"
    assert nodos.at["A03", "cuenca"] == "vichada"
    assert {f"P{i:02d}" for i in range(1, 13)} <= set(nodos.index)
    candidatas = config.parametro("cadena_actual.candidatas_desembarque_senora")
    assert 3 <= len(candidatas) <= 4
    assert all(nodos.at[c, "tipo"] == "desembarque" for c in candidatas)


def test_san_miguel_rio_abajo_al_noreste():
    # El Meta corre hacia el noreste: San Miguel queda al norte y al este de Puerto Gaitan
    nodos = config.cargar_nodos().set_index("id")
    assert nodos.at["A02", "lat"] > nodos.at["A01", "lat"]
    assert nodos.at["A02", "lon"] > nodos.at["A01", "lon"]


def test_distancias_medidas():
    dist = config.cargar_distancias_medidas().set_index("id")
    assert dist["distancia_km"].to_dict() == {"M01": 15.14, "M02": 17.38, "M03": 38.9, "M04": 41.65}
    assert dist.at["M04", "sentido_rio_origen_a_destino"] == "aguas_arriba"
    assert set(dist["modo"]) <= config.MODOS


def test_sepec_totales():
    sepec = config.cargar_sepec()
    total = sepec.groupby("sitio")["toneladas"].sum()
    assert total["malecon_puerto_gaitan"] == pytest.approx(24.2)
    assert total["san_miguel_puerto_gaitan"] == pytest.approx(5.5)


def test_precios_oficiales():
    precios = config.cargar_precios().set_index("producto")["cop_por_kg"]
    assert precios["cachama_fresca"] == 11833
    assert precios["bagre_rayado_entero_fresco"] == 14000
    assert config.parametro("precios.cachama_cop_kg") == 11833
    assert config.parametro("precios.bagre_rayado_cop_kg") == 14000
