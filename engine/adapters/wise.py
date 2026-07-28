"""Adaptador Wise — extracto de transacciones (statement CSV).

Wise entrega el extracto con columnas en inglés y una fila por movimiento.
Igual que en Deel, las conversiones entre monedas propias y los retiros a
cuenta bancaria son TRASLADOS, no ingresos: contarlos infla la base.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..ledger import Movimiento
from .generico import (abrir_csv, aviso_de_filas_saltadas,
                       convencion_del_archivo, parse_fecha, parse_monto)

NOMBRE = "Wise"

# "wise" como subcadena reclamaba archivos llamados "otherwise.csv". Se pide
# la palabra completa.
SENALES = {"transferwise", "running balance", "exchange from", "exchange to"}

# El orden importa: gana la PRIMERA que coincide. Los ingresos van antes que
# los traslados porque "Received money from Cliente — converted to COP" trae
# las dos palabras, y clasificarlo como traslado borra un ingreso del ledger.
REGLAS = [
    (("received money from", "incoming payment", "deposit from"), "ingreso_trabajo"),
    (("exchange from", "exchange to", "balance transfer", "converted",
      "sent money to your", "topped up"), "traslado"),
    (("wise charged", "fee for", "transfer fee"), "costo"),
    (("sent money to",), "desconocido"),   # puede ser costo o gasto personal
]


def detecta(cabeceras: list[str], nombre: str = "") -> bool:
    texto = " ".join(c.lower() for c in cabeceras)
    import re as _re

    # (?<![a-z]) en vez de \b: el guion bajo es carácter de palabra, así que
    # \bwise\b no reconoce "wise_statement.csv". Lo que hay que excluir es
    # "otherwise", o sea una letra pegada por delante.
    if _re.search(r"(?<![a-z])wise(?![a-z])", nombre.lower()):
        return True
    tiene_wise = any(s in texto for s in SENALES)
    tiene_forma = "amount" in texto and ("description" in texto or "reference" in texto)
    return tiene_wise and tiene_forma


# Igual que en deel.py: el texto propone y el signo veta. "Received money
# from Cliente" con monto negativo no es un ingreso, y clasificarlo como tal
# mete un ingreso que RESTA de la base gravable.
ENTRANTES = {"ingreso_trabajo", "ingreso_capital"}


def _clasificar(descripcion: str, monto: float = 0.0) -> str:
    blob = descripcion.lower()
    for palabras, categoria in REGLAS:
        if any(p in blob for p in palabras):
            if categoria in ENTRANTES and monto < 0:
                return "desconocido"
            return categoria
    return "desconocido"


def importar(ruta: Path, avisos: list[str] | None = None) -> list[Movimiento]:
    avisos = avisos if avisos is not None else []
    movimientos = []
    with abrir_csv(ruta, avisos) as f:
        lector = csv.DictReader(f)
        campos = {c.lower().strip(): c for c in (lector.fieldnames or [])}

        def col(*nombres):
            for n in nombres:
                if n in campos:
                    return campos[n]
            return None

        c_fecha = col("date", "created on", "finished on")
        c_monto = col("amount", "target amount", "source amount")
        c_moneda = col("currency", "target currency", "source currency")
        c_desc = col("description", "reference", "payer name", "merchant")
        c_parte = col("payer name", "merchant", "recipient name", "payee name")

        if not c_fecha or not c_monto:
            raise ValueError(
                f"El extracto de Wise {ruta.name} no tiene columnas reconocibles. "
                f"Columnas: {lector.fieldnames}"
            )
        if not c_moneda:
            # Mismo guardia que en deel.py, que acá faltaba: suponer USD sobre
            # un archivo en pesos multiplica el ingreso declarado por ~4.000.
            from . import ErrorSinRespaldo

            raise ErrorSinRespaldo(
                f"{ruta.name} se identificó como extracto de Wise pero no trae "
                f"columna de moneda. No se supone USD: agrégala al CSV, o "
                f"renombra el archivo para que lo tome el adaptador genérico."
            )

        filas = list(lector)
        sep, avisos_sep = convencion_del_archivo(
            fila.get(c_monto, "") for fila in filas
        )
        avisos += [f"{ruta.name}: {a}" for a in avisos_sep]

        malas: list[str] = []
        for i, fila in enumerate(filas, start=2):
            crudo = (fila.get(c_fecha) or "").strip()
            if not crudo:
                continue
            moneda = (fila.get(c_moneda) or "USD").strip().upper()
            try:
                fecha = parse_fecha(crudo)
                monto = parse_monto(fila.get(c_monto, "0"), sep, moneda)
            except ValueError as e:
                malas.append(f"línea {i}: {e}")
                continue
            if monto == 0:
                continue
            desc = (fila.get(c_desc) or "").strip() if c_desc else ""
            movimientos.append(Movimiento(
                fecha=fecha,
                descripcion=desc or "movimiento Wise",
                monto_origen=monto,
                moneda=moneda,
                categoria=_clasificar(desc, monto),
                contraparte=((fila.get(c_parte) or "").strip() if c_parte else ""),
                fuente=ruta.name,
            ))
    if malas and not movimientos:
        raise ValueError(f"{ruta.name}: ninguna fila se pudo leer — {malas[0]}")
    if malas:
        avisos.append(aviso_de_filas_saltadas(ruta.name, malas, len(movimientos)))
    return movimientos
