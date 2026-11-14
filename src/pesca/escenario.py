"""Escenario compartido por todas las pantallas (lo controla la barra lateral)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from pesca import config, red


@dataclass(frozen=True)
class Escenario:
    acopios_activos: frozenset[str]
    desembarque_senora: str
    temporada: str
    hielo_a_bordo: bool
    camion_refrigerado: bool
    inversiones: frozenset[str] = field(default_factory=frozenset)
    semilla: int = 0
    acopios_nuevos: frozenset[str] = field(default_factory=frozenset)  # puntos del rio (p-mediana de R4)

    def __post_init__(self) -> None:
        nodos = config.cargar_nodos().set_index("id")
        acopios = set(nodos.index[nodos["tipo"] == "acopio"])
        invalidos = set(self.acopios_activos) - acopios
        if invalidos:
            raise ValueError(f"Acopios desconocidos: {sorted(invalidos)}")
        if not self.acopios_activos:
            raise ValueError("Debe haber al menos un acopio activo")
        candidatas = config.parametro("cadena_actual.candidatas_desembarque_senora")
        if self.desembarque_senora not in candidatas:
            raise ValueError(f"'{self.desembarque_senora}' no es una candidata del desembarque: {candidatas}")
        if self.temporada not in config.TEMPORADAS:
            raise ValueError(f"Temporada desconocida: {self.temporada}")
        grafo = red.construir_red()
        fuera = [a for a in self.acopios_nuevos if red.clave(a, red.CAPA_RIO) not in grafo]
        if fuera:
            raise ValueError(f"Los acopios nuevos deben ser puntos del río: {sorted(fuera)}")
        # Acepta listas o sets y los congela para que el escenario sea hashable
        object.__setattr__(self, "acopios_activos", frozenset(self.acopios_activos))
        object.__setattr__(self, "inversiones", frozenset(self.inversiones))
        object.__setattr__(self, "acopios_nuevos", frozenset(self.acopios_nuevos))

    @classmethod
    def base(cls) -> Escenario:
        p = config.parametro
        return cls(
            acopios_activos=frozenset(p("escenario_base.acopios_activos")),
            desembarque_senora=p("escenario_base.desembarque_senora"),
            temporada=p("escenario_base.temporada"),
            hielo_a_bordo=p("escenario_base.hielo_a_bordo"),
            camion_refrigerado=p("escenario_base.camion_refrigerado"),
            semilla=p("general.semilla"),
        )

    def con(self, **cambios) -> Escenario:
        """Copia del escenario con algunos campos cambiados."""
        return replace(self, **cambios)

    def corriente_kmh(self) -> float:
        return config.parametro(f"rio.corriente_{self.temporada}_kmh")
