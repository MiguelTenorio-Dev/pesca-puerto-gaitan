"""Rutas, vocabulario y carga de los datos del paquete.

Todo numero del modelo vive en datos/parametros.yaml; aqui solo se lee.
"""

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

DIR_PAQUETE = Path(__file__).resolve().parent
DIR_DATOS = DIR_PAQUETE / "datos"
DIR_PRECALCULADO = DIR_DATOS / "precalculado"
DIR_KML = DIR_DATOS / "rutas_kml"
DIR_APP = DIR_PAQUETE / "app"


def _buscar_repo() -> Path | None:
    """Raiz del repositorio si el paquete corre desde el codigo fuente; None si se instalo con pip."""
    candidato = DIR_PAQUETE.parent.parent
    return candidato if (candidato / "docs").is_dir() else None


DIR_REPO = _buscar_repo()

TIPOS_NODO = {"acopio", "desembarque", "comunidad", "zona_pesca", "punto_rio", "confluencia", "punto_via"}
CUENCAS = {"meta", "vichada"}
ETIQUETAS = {"MEDIDO", "DATO", "OFICIAL", "CALIBRADO", "SIMULADO", "CONFIRMAR"}
MODOS = {"rio", "via", "transbordo"}
TEMPORADAS = {"aguas_bajas", "aguas_altas"}

COLUMNAS_NODOS = ["id", "nombre", "tipo", "cuenca", "lat", "lon", "validado", "fuente", "notas"]
COLUMNAS_DISTANCIAS = ["id", "origen", "destino", "modo", "distancia_km", "sentido_rio_origen_a_destino", "fuente", "evidencia"]
COLUMNAS_RIOS = ["traza", "nombre", "cuenca", "orden", "id_nodo", "lat", "lon", "fuente"]
COLUMNAS_VIAS = ["traza", "nombre", "orden", "id_nodo", "lat", "lon", "fuente"]
COLUMNAS_SEPEC =["sitio", "periodo", "toneladas", "fuente"]
COLUMNAS_PRECIOS = ["producto", "mercado", "fecha", "cop_por_kg", "fuente"]


def _validar_columnas(df: pd.DataFrame, columnas: list[str], archivo: str) -> pd.DataFrame:
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise ValueError(f"{archivo}: faltan las columnas {faltan}")
    return df


@cache
def cargar_parametros() -> dict[str, Any]:
    with open(DIR_DATOS / "parametros.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def es_hoja(nodo: Any) -> bool:
    """Un parametro hoja es un dict con la llave 'valor'."""
    return isinstance(nodo, dict) and "valor" in nodo


def hojas_parametros() -> list[tuple[str, dict[str, Any]]]:
    """Lista plana de (ruta.punteada, hoja) para mostrar o validar todos los parametros."""
    salida = []

    def recorrer(nodo: dict[str, Any], prefijo: str) -> None:
        for clave, hijo in nodo.items():
            ruta = f"{prefijo}.{clave}" if prefijo else clave
            if es_hoja(hijo):
                salida.append((ruta, hijo))
            elif isinstance(hijo, dict):
                recorrer(hijo, ruta)

    recorrer(cargar_parametros(), "")
    return salida


def hoja(ruta: str) -> dict[str, Any]:
    """Hoja completa de un parametro, p. ej. hoja('rio.v_minima_kmh')."""
    nodo: Any = cargar_parametros()
    for parte in ruta.split("."):
        if not isinstance(nodo, dict) or parte not in nodo:
            raise KeyError(f"No existe el parametro '{ruta}'")
        nodo = nodo[parte]
    if not es_hoja(nodo):
        raise KeyError(f"'{ruta}' es un grupo, no un parametro")
    return nodo


# Valores que reemplazan a los del yaml dentro de `sobrescribir` (Monte Carlo y pruebas)
_SOBRESCRITOS: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("sobrescritos", default={})


def parametro(ruta: str) -> Any:
    """Valor de un parametro, p. ej. parametro('general.semilla')."""
    sobrescritos = _SOBRESCRITOS.get()
    if ruta in sobrescritos:
        return sobrescritos[ruta]
    return hoja(ruta)["valor"]


@contextlib.contextmanager
def sobrescribir(valores: dict[str, Any]) -> Iterator[None]:
    """Dentro del bloque, parametro(ruta) devuelve valores[ruta] en vez del valor del yaml."""
    for ruta in valores:
        hoja(ruta)  # falla si el parametro no existe
    token = _SOBRESCRITOS.set({**_SOBRESCRITOS.get(), **valores})
    try:
        yield
    finally:
        _SOBRESCRITOS.reset(token)


@cache
def cargar_nodos() -> pd.DataFrame:
    df = pd.read_csv(DIR_DATOS / "nodos.csv", dtype={"validado": str})
    return _validar_columnas(df, COLUMNAS_NODOS, "nodos.csv")


@cache
def cargar_distancias_medidas() -> pd.DataFrame:
    df = pd.read_csv(DIR_DATOS / "distancias_medidas.csv")
    return _validar_columnas(df, COLUMNAS_DISTANCIAS, "distancias_medidas.csv")


@cache
def cargar_rios() -> pd.DataFrame:
    """Trazas de rios y caños, un vertice por fila, de aguas arriba a aguas abajo."""
    df = pd.read_csv(DIR_DATOS / "rios.csv", dtype={"id_nodo": str})
    return _validar_columnas(df, COLUMNAS_RIOS, "rios.csv").sort_values(["traza", "orden"], kind="stable")


@cache
def cargar_vias() -> pd.DataFrame:
    """Trazas de las carreteras, un vertice por fila."""
    df = pd.read_csv(DIR_DATOS / "vias.csv", dtype={"id_nodo": str})
    return _validar_columnas(df, COLUMNAS_VIAS, "vias.csv").sort_values(["traza", "orden"], kind="stable")


@cache
def cargar_sepec() -> pd.DataFrame:
    df = pd.read_csv(DIR_DATOS / "sepec_desembarcos_2022.csv")
    return _validar_columnas(df, COLUMNAS_SEPEC, "sepec_desembarcos_2022.csv")


@cache
def cargar_precios() -> pd.DataFrame:
    df = pd.read_csv(DIR_DATOS / "precios_referencia.csv")
    return _validar_columnas(df, COLUMNAS_PRECIOS, "precios_referencia.csv")


def ruta_evidencia(relativa: str) -> Path | None:
    """Ruta de una captura de docs/evidencias, o None si el repo no esta disponible."""
    if DIR_REPO is None or not isinstance(relativa, str):
        return None
    ruta = DIR_REPO / relativa
    return ruta if ruta.is_file() else None
