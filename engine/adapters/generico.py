"""Adaptador genérico: cualquier CSV con fecha, descripción y monto.

Es el que atrapa lo que ningún adaptador específico reconoce. Intenta
adivinar las columnas por nombre; si no lo logra, pide un mapeo explícito.

Todo lo que importa queda en categoría 'desconocido' a propósito: prefiere
que clasifiques a mano antes que adivinar mal el signo de un ingreso.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from ..ledger import Movimiento

NOMBRE = "Genérico (CSV)"

ALIAS = {
    "fecha": ["fecha", "date", "fecha_operacion", "fecha operación", "fecha movimiento",
              "transaction date", "posting date", "fecha de transaccion"],
    "descripcion": ["descripcion", "descripción", "description", "concepto",
                    "detalle", "narrative", "memo", "referencia"],
    "monto": ["monto", "valor", "amount", "importe", "debito_credito", "value",
              "monto_total", "total"],
    "moneda": ["moneda", "currency", "divisa", "ccy"],
    "contraparte": ["contraparte", "beneficiario", "counterparty", "payee",
                    "tercero", "nombre"],
}

FORMATOS_FECHA = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d",
    "%d/%m/%y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
]


def _norm(s: str) -> str:
    return s.strip().lower().replace("_", " ")


def _mapear(cabeceras: list[str]) -> dict[str, str]:
    mapa = {}
    normalizadas = {_norm(c): c for c in cabeceras}
    for campo, alias in ALIAS.items():
        for a in alias:
            if a in normalizadas:
                mapa[campo] = normalizadas[a]
                break
    return mapa


def parse_fecha(texto: str):
    texto = texto.strip()
    for fmt in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto[:19] if " " in texto or "T" in texto else texto, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha no reconocida: {texto!r}")


def parse_monto(texto: str, sep_decimal: str | None = None) -> float:
    """Convierte un monto a float. Formato colombiano y anglosajón.

    `sep_decimal` ('.' o ',') elimina la ambigüedad y los adaptadores que
    conocen su fuente deberían pasarlo siempre. Bancolombia escribe
    "1.234.567,89"; Deel y Wise escriben "1234567.89".

    Sin pista, se aplica esta heurística — documentada porque tiene un caso
    ambiguo real:

      "1.234,56"  → ambos separadores: decimal es el último       → 1234.56
      "1,234.56"  → ambos separadores: decimal es el último       → 1234.56
      "1.234.567" → dos o más puntos: son miles                   → 1234567
      "3800.00"   → un punto, 2 dígitos detrás: decimal           → 3800.0
      "1.234"     → un punto, 3 dígitos detrás: se asume MILES    → 1234
      "1,50"      → una coma, 2 dígitos detrás: decimal           → 1.5

    El caso ambiguo es "1.234": vale 1.234 en USD y 1234 en COP. Se resuelve
    a favor de COP porque es lo que domina en extractos colombianos. Pasa
    `sep_decimal` si tu fuente hace lo contrario.
    """
    t = str(texto).strip().replace("$", "").replace(" ", "").replace("\xa0", "")
    if not t or t in {"-", "—", "N/A", "n/a"}:
        return 0.0

    negativo = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if t.startswith("-"):
        negativo, t = True, t[1:]
    t = t.replace("+", "")

    if sep_decimal == ",":
        t = t.replace(".", "").replace(",", ".")
    elif sep_decimal == ".":
        t = t.replace(",", "")
    elif "," in t and "." in t:
        t = (t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".")
             else t.replace(",", ""))
    elif "," in t:
        entero, _, dec = t.rpartition(",")
        t = f"{entero.replace('.', '')}.{dec}" if len(dec) <= 2 else t.replace(",", "")
    elif "." in t:
        if t.count(".") > 1 or len(t.rpartition(".")[2]) == 3:
            t = t.replace(".", "")

    if not t or t == ".":
        return 0.0
    valor = float(t)
    return -valor if negativo else valor


def detecta(cabeceras: list[str], nombre: str = "") -> bool:
    mapa = _mapear(cabeceras)
    return "fecha" in mapa and "monto" in mapa


def importar(ruta: Path, mapa: dict[str, str] | None = None) -> list[Movimiento]:
    with open(ruta, newline="", encoding="utf-8-sig", errors="replace") as f:
        lector = csv.DictReader(f)
        cols = mapa or _mapear(lector.fieldnames or [])
        if "fecha" not in cols or "monto" not in cols:
            raise ValueError(
                f"No pude identificar las columnas de fecha y monto en {ruta.name}. "
                f"Columnas: {lector.fieldnames}. Pasa un mapeo explícito: "
                f"importar(ruta, {{'fecha': 'MiColumnaFecha', 'monto': 'MiColumnaValor'}})"
            )
        movimientos = []
        for i, fila in enumerate(lector, start=2):
            crudo = (fila.get(cols["fecha"]) or "").strip()
            if not crudo:
                continue
            try:
                fecha = parse_fecha(crudo)
                monto = parse_monto(fila.get(cols["monto"], "0"))
            except ValueError as e:
                raise ValueError(f"{ruta.name} línea {i}: {e}") from e
            if monto == 0:
                continue
            movimientos.append(Movimiento(
                fecha=fecha,
                descripcion=(fila.get(cols.get("descripcion", ""), "") or "").strip(),
                monto_origen=monto,
                moneda=(fila.get(cols.get("moneda", ""), "") or "COP").strip().upper() or "COP",
                contraparte=(fila.get(cols.get("contraparte", ""), "") or "").strip(),
                categoria="desconocido",
                fuente=ruta.name,
            ))
    return movimientos
