"""Precalcula los resultados pesados en src/pesca/datos/precalculado/ y outputs/.

Uso: python scripts/correr_todo.py [--solo r2|r4|r5]
"""

from __future__ import annotations

import argparse
import time

from pesca import cadena_actual, ubicacion

# Cada fase registra aqui su funcion de precalculo (r2, r4, r5, resumen).
TAREAS: dict[str, callable] = {"r2": cadena_actual.precalcular, "r4": ubicacion.precalcular}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solo", choices=sorted(TAREAS) or None, help="corre solo esta tarea")
    args = parser.parse_args()
    if not TAREAS:
        print("Nada que precalcular todavia (Fase 0).")
        return
    for nombre, tarea in TAREAS.items():
        if args.solo in (None, nombre):
            print(f"Corriendo {nombre}...")
            inicio = time.perf_counter()
            tarea()
            print(f"{nombre} listo en {time.perf_counter() - inicio:.0f} s")


if __name__ == "__main__":
    main()
