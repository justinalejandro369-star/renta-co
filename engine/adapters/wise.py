"""Adaptador Wise — extracto de transacciones (statement CSV).

Wise entrega el extracto con columnas en inglés y una fila por movimiento.
Igual que en Deel, las conversiones entre monedas propias y los retiros a
cuenta bancaria son TRASLADOS, no ingresos: contarlos infla la base.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..ledger import Movimiento
from .generico import parse_fecha, parse_monto

NOMBRE = "Wise"

SENALES = {"wise", "transferwise", "running balance", "exchange from", "exchange to"}

REGLAS = [
    (("converted", "exchange from", "exchange to", "balance transfer",
      "sent money to your", "topped up"), "traslado"),
    (("fee", "wise charged"), "costo"),
    (("received money from", "incoming", "deposit"), "ingreso_trabajo"),
    (("sent money to",), "desconocido"),   # puede ser costo o gasto personal
]


def detecta(cabeceras: list[str], nombre: str = "") -> bool:
    texto = " ".join(c.lower() for c in cabeceras)
    if "wise" in nombre.lower():
        return True
    tiene_wise = any(s in texto for s in SENALES)
    tiene_forma = "amount" in texto and ("description" in texto or "reference" in texto)
    return tiene_wise and tiene_forma


def _clasificar(descripcion: str) -> str:
    blob = descripcion.lower()
    for palabras, categoria in REGLAS:
        if any(p in blob for p in palabras):
            return categoria
    return "desconocido"


def importar(ruta: Path) -> list[Movimiento]:
    movimientos = []
    with open(ruta, newline="", encoding="utf-8-sig", errors="replace") as f:
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

        for i, fila in enumerate(lector, start=2):
            crudo = (fila.get(c_fecha) or "").strip()
            if not crudo:
                continue
            try:
                fecha = parse_fecha(crudo)
                monto = parse_monto(fila.get(c_monto, "0"), sep_decimal=".")
            except ValueError as e:
                raise ValueError(f"{ruta.name} línea {i}: {e}") from e
            if monto == 0:
                continue
            desc = (fila.get(c_desc) or "").strip() if c_desc else ""
            movimientos.append(Movimiento(
                fecha=fecha,
                descripcion=desc or "movimiento Wise",
                monto_origen=monto,
                moneda=((fila.get(c_moneda) or "USD").strip().upper() if c_moneda else "USD"),
                categoria=_clasificar(desc),
                contraparte=((fila.get(c_parte) or "").strip() if c_parte else ""),
                fuente=ruta.name,
            ))
    return movimientos
