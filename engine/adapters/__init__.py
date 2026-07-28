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


class ErrorSinRespaldo(ValueError):
    """Fallo que NO se debe reintentar con el adaptador genérico.

    El genérico asigna COP por defecto cuando no hay columna de moneda. Para
    un archivo que otro adaptador reconoció como export en dólares, ese
    respaldo silencioso convierte 3.800 USD en 3.800 COP: un error de ~4.000×
    presentado como una importación exitosa. Cuando el adaptador específico
    falla precisamente por no poder determinar la moneda, hay que parar y
    preguntar.
    """

    sin_respaldo = True


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
    """Importa un archivo con el adaptador que lo reconozca.

    Si un adaptador específico reclama el archivo y después falla al leerlo,
    se reintenta con el genérico antes de darse por vencido. Sin ese respaldo,
    una detección demasiado entusiasta dejaba el archivo inutilizable con un
    mensaje engañoso ("El archivo de Deel X no tiene columnas...") cuando el
    genérico lo habría leído perfecto.
    """
    adaptador = elegir(ruta)
    if adaptador is None:
        raise ValueError(
            f"Ningún adaptador reconoce {ruta.name}. Columnas encontradas: "
            f"{leer_cabeceras(ruta)}. Usa el adaptador genérico con un mapeo "
            f"explícito, o escribe uno nuevo — son ~40 líneas, ver "
            f"engine/adapters/generico.py."
        )
    try:
        return adaptador.importar(ruta), adaptador.NOMBRE
    except ValueError as e:
        if adaptador is generico or getattr(e, "sin_respaldo", False):
            raise
        try:
            movs = generico.importar(ruta)
        except ValueError:
            raise e from None
        return movs, f"{generico.NOMBRE} (respaldo: {adaptador.NOMBRE} falló)"
