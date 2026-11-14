import numpy as np
import pytest

from pesca import config, montecarlo


def test_muestras_dentro_del_rango():
    rng = np.random.default_rng(1)
    for _ in range(20):
        muestra = montecarlo.muestrear(rng)
        for ruta, h in config.hojas_parametros():
            if "rango" in h:
                minimo, maximo = h["rango"]
                assert minimo <= muestra[ruta] <= maximo, ruta
                if isinstance(h["valor"], int):
                    assert isinstance(muestra[ruta], int), ruta


def test_mezcla_de_flota_suma_uno():
    mezcla = montecarlo.muestrear_mezcla(np.random.default_rng(3))
    assert sum(mezcla.values()) == pytest.approx(1.0)
    assert all(v >= 0 for v in mezcla.values())


def test_sobrescribir_restaura():
    original = config.parametro("volumen.factor_subregistro")
    with config.sobrescribir({"volumen.factor_subregistro": 2.7}):
        assert config.parametro("volumen.factor_subregistro") == 2.7
    assert config.parametro("volumen.factor_subregistro") == original


def test_sobrescribir_rechaza_parametros_inexistentes():
    with pytest.raises(KeyError):
        with config.sobrescribir({"rio.no_existe": 1}):
            pass


def test_generadores_reproducibles():
    a = [g.random() for g in montecarlo.generadores(3, 42)]
    b = [g.random() for g in montecarlo.generadores(3, 42)]
    assert a == b and len(set(a)) == 3


def test_resumir():
    r = montecarlo.resumir(np.arange(101))
    assert r == {"media": 50.0, "p5": 5.0, "p95": 95.0}
