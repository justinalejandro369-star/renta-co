"""Adaptador genérico: cualquier CSV con fecha, descripción y monto.

Es el que atrapa lo que ningún adaptador específico reconoce. Intenta
adivinar las columnas por nombre; si no lo logra, pide un mapeo explícito.

Todo lo que importa queda en categoría 'desconocido' a propósito: prefiere
que clasifiques a mano antes que adivinar mal el signo de un ingreso.
"""

from __future__ import annotations

import csv
import re
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

# Forma válida de un monto ANTES de normalizar: dígitos ASCII separados por
# un solo punto o una sola coma. Excluye notación científica, nan/inf,
# guiones bajos, separadores repetidos y dígitos no ASCII.
_TOKEN = re.compile(r"[0-9]+(?:[.,][0-9]+)*")

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

    Sin pista, se aplica esta heurística, que tiene un caso ambiguo real:

      "1.234,56"  → ambos separadores: decimal es el último       → 1234.56
      "1,234.56"  → ambos separadores: decimal es el último       → 1234.56
      "1.234.567" → dos o más puntos: son miles                   → 1234567
      "3800.00"   → un punto, 2 dígitos detrás: decimal           → 3800.0
      "1.234"     → un punto, 3 dígitos detrás: se asume MILES    → 1234
      "1,50"      → una coma, 2 dígitos detrás: decimal           → 1.5

    El ambiguo es "1.234": vale 1.234 en USD y 1234 en COP. Se resuelve a
    favor de COP porque es lo que domina en extractos colombianos. Pasa
    `sep_decimal` si tu fuente hace lo contrario.

    VALIDACIÓN — por qué se hace ANTES de tocar los separadores
    ───────────────────────────────────────────────────────────
    Un intento anterior validaba con una expresión regular al final, sobre
    el texto ya normalizado. No servía de nada: la normalización es
    justamente la que fabrica el número creíble. "1.2.3" llegaba al regex
    convertido en "123" y pasaba como ciento veintitrés.

    Acá se valida la ESTRUCTURA del token original: dígitos ASCII separados
    por un solo punto o una sola coma, y los grupos de miles de exactamente
    tres dígitos. Así "1.2.3", "1..2" y "12,34,567" fallan por lo que son —
    montos malformados— y no se convierten en una cifra que después nadie
    puede rastrear en la base gravable.
    """
    original = str(texto)
    t = original.strip().replace("$", "").replace(" ", "").replace("\xa0", "")
    if not t or t in {"-", "—", "N/A", "n/a"}:
        return 0.0

    def malo(motivo):
        return ValueError(f"{original!r} no es un monto reconocible: {motivo}.")

    entre_parentesis = t.startswith("(") and t.endswith(")")
    if entre_parentesis:
        t = t[1:-1]

    negativo = entre_parentesis
    if t.startswith(("-", "+")):
        if entre_parentesis:
            raise malo("tiene paréntesis Y signo, y no se sabe cuál manda")
        negativo = t[0] == "-"
        t = t[1:]

    # [0-9] es ASCII a propósito: float() acepta dígitos árabes y de ancho
    # completo, y "١٢٣" no es un monto que deba entrar callado a un ledger.
    if not _TOKEN.fullmatch(t):
        raise malo("solo se aceptan dígitos separados por un punto o una coma")

    grupos = re.split(r"[.,]", t)
    separadores = [c for c in t if c in ".,"]

    if sep_decimal in (".", ","):
        decimal = sep_decimal in separadores
    elif "," in separadores and "." in separadores:
        decimal = True                       # el último separador es el decimal
    elif len(separadores) == 1:
        # Un solo separador: es decimal salvo que deje exactamente tres
        # dígitos detrás, que es la forma de un grupo de miles.
        decimal = len(grupos[-1]) != 3
    else:
        decimal = False                      # varios separadores iguales: miles

    if sep_decimal in (".", ",") and decimal:
        # Con pista explícita, el decimal es el ÚLTIMO separador de ese tipo.
        corte = t.rfind(sep_decimal)
        entero, fraccion = t[:corte], t[corte + 1:]
    elif decimal:
        corte = max(t.rfind("."), t.rfind(","))
        entero, fraccion = t[:corte], t[corte + 1:]
    else:
        entero, fraccion = t, ""

    partes = [p for p in re.split(r"[.,]", entero) if p != ""] or ["0"]
    if len(partes) > 1:
        if len(partes[0]) > 3:
            raise malo(f"el primer grupo de miles tiene {len(partes[0])} dígitos")
        for p in partes[1:]:
            if len(p) != 3:
                raise malo(f"el grupo de miles {p!r} no tiene tres dígitos")

    valor = float("".join(partes) + ("." + fraccion if fraccion else ""))
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
