"""Rutas, vocabulario y carga de los datos del paquete.

Todo numero del modelo vive en datos/parametros.yaml; aqui solo se lee.
"""

from __future__ import annotations

import contextlib
import contextvars
import xml.etree.ElementTree as ET
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
COLUMNAS_PUNTOS_KML = ["nombre_kml", "uso", "id", "nombre", "notas"]
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


COLUMNAS_KML = ["nombre_kml", "lat", "lon", "archivo"]


def leer_puntos_kml(ruta: Path) -> pd.DataFrame:
    """Placemark con Point de un KML de Google Earth: nombre (sin espacios sobrantes), lat, lon."""
    filas = []
    for marca in ET.parse(ruta).iter():
        if not marca.tag.endswith("Placemark"):
            continue
        nombre = next((e.text or "" for e in marca if e.tag.endswith("name")), "").strip()
        for punto in marca.iter():
            if punto.tag.endswith("Point"):
                texto = next(e.text for e in punto.iter() if e.tag.endswith("coordinates"))
                lon, lat, *_ = (float(x) for x in texto.split(","))
                filas.append({"nombre_kml": nombre, "lat": lat, "lon": lon, "archivo": ruta.name})
    return pd.DataFrame(filas, columns=COLUMNAS_KML)


@cache
def cargar_puntos_kml() -> pd.DataFrame:
    """Puntos medidos por el equipo en los KML de rutas_kml/, con su uso segun puntos_kml.csv.

    uso = nodo (corrige la coordenada de un nodo), referencia (fuera del grafo) o descartado.
    Un punto que no este en puntos_kml.csv es un error: hay que decidir su uso.
    """
    mapa = _validar_columnas(pd.read_csv(DIR_DATOS / "puntos_kml.csv"), COLUMNAS_PUNTOS_KML, "puntos_kml.csv")
    leidos = [leer_puntos_kml(r) for r in sorted(DIR_KML.glob("*.kml"))]
    puntos = pd.concat(leidos, ignore_index=True) if leidos else pd.DataFrame(columns=COLUMNAS_KML)
    sin_uso = set(puntos["nombre_kml"]) - set(mapa["nombre_kml"])
    if sin_uso:
        raise ValueError(f"Puntos KML sin uso definido en puntos_kml.csv: {sorted(sin_uso)}")
    return puntos.merge(mapa, on="nombre_kml")


def _con_coordenadas_kml(df: pd.DataFrame, col_id: str) -> pd.DataFrame:
    """Prioridad de coordenadas: punto KML medido > coordenada estimada del CSV."""
    kml = cargar_puntos_kml()
    kml = kml[kml["uso"] == "nodo"].set_index("id")
    df = df.copy()
    medido = df[col_id].isin(kml.index)
    ids = df.loc[medido, col_id]
    df.loc[medido, "lat"] = ids.map(kml["lat"]).to_numpy()
    df.loc[medido, "lon"] = ids.map(kml["lon"]).to_numpy()
    df.loc[medido, "fuente"] = ids.map(lambda i: f"KML medido ({kml.at[i, 'archivo'].strip()})").to_numpy()
    if "validado" in df:
        df.loc[medido, "validado"] = "si"
    return df


@cache
def cargar_nodos() -> pd.DataFrame:
    df = pd.read_csv(DIR_DATOS / "nodos.csv", dtype={"validado": str})
    return _con_coordenadas_kml(_validar_columnas(df, COLUMNAS_NODOS, "nodos.csv"), "id")


def puntos_referencia() -> pd.DataFrame:
    """Mercados de referencia medidos en KML que no entran al grafo (Villavicencio, Bogota)."""
    kml = cargar_puntos_kml()
    return kml.loc[kml["uso"] == "referencia", ["id", "nombre", "lat", "lon", "archivo", "notas"]].reset_index(drop=True)


@cache
def cargar_distancias_medidas() -> pd.DataFrame:
    df = pd.read_csv(DIR_DATOS / "distancias_medidas.csv")
    return _validar_columnas(df, COLUMNAS_DISTANCIAS, "distancias_medidas.csv")


@cache
def cargar_rios() -> pd.DataFrame:
    """Trazas de rios y caños, un vertice por fila, de aguas arriba a aguas abajo."""
    df = pd.read_csv(DIR_DATOS / "rios.csv", dtype={"id_nodo": str})
    df = _con_coordenadas_kml(_validar_columnas(df, COLUMNAS_RIOS, "rios.csv"), "id_nodo")
    return df.sort_values(["traza", "orden"], kind="stable")


@cache
def cargar_vias() -> pd.DataFrame:
    """Trazas de las carreteras, un vertice por fila."""
    df = pd.read_csv(DIR_DATOS / "vias.csv", dtype={"id_nodo": str})
    df = _con_coordenadas_kml(_validar_columnas(df, COLUMNAS_VIAS, "vias.csv"), "id_nodo")
    return df.sort_values(["traza", "orden"], kind="stable")


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
