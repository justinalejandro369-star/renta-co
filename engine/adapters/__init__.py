"""Adaptadores de importación: archivo de una fuente → lista de Movimiento.

Cada adaptador expone:

    NOMBRE      str, para reportes
    detecta(cabeceras: list[str], nombre: str = "") -> bool
    importar(ruta: Path) -> list[Movimiento]

Agregar un banco o plataforma nueva son ~40 líneas. Copia `generico.py`,
ajusta el mapeo de columnas, regístralo abajo y manda el PR. Incluye siempre
un CSV de muestra ANONIMIZADO en engine/tests/muestras/.
"""

from __future__ import annotations

import csv
from pathlib import Path

from . import bancolombia, deel, generico, wise

REGISTRO = [deel, wise, bancolombia, generico]   # generico siempre de último


def leer_cabeceras(ruta: Path) -> list[str]:
    with open(ruta, newline="", encoding="utf-8-sig", errors="replace") as f:
        for fila in csv.reader(f):
            if fila and any(c.strip() for c in fila):
                return [c.strip() for c in fila]
    return []


def elegir(ruta: Path):
    """Devuelve el adaptador que reconoce el archivo, o None."""
    cabeceras = leer_cabeceras(ruta)
    if not cabeceras:
        return None
    for adaptador in REGISTRO:
        try:
            if adaptador.detecta(cabeceras, ruta.name):
                return adaptador
        except Exception:
            continue
    return None


def importar(ruta: Path):
    """Importa un archivo con el adaptador que lo reconozca."""
    adaptador = elegir(ruta)
    if adaptador is None:
        raise ValueError(
            f"Ningún adaptador reconoce {ruta.name}. Columnas encontradas: "
            f"{leer_cabeceras(ruta)}. Usa el adaptador genérico con un mapeo "
            f"explícito, o escribe uno nuevo — son ~40 líneas, ver "
            f"engine/adapters/generico.py."
        )
    return adaptador.importar(ruta), adaptador.NOMBRE
