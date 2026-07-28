"""Adaptador genérico: cualquier CSV con fecha, descripción y monto.

Es el que atrapa lo que ningún adaptador específico reconoce. Intenta
adivinar las columnas por nombre; si no lo logra, pide un mapeo explícito.

Todo lo que importa queda en categoría 'desconocido' a propósito: prefiere
que clasifiques a mano antes que adivinar mal el signo de un ingreso.
"""

from __future__ import annotations

import csv
import math
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

    La decisión la toma la ESTRUCTURA del número, no una pista externa:

        Un separador seguido de exactamente TRES dígitos es de miles.
        Un separador seguido de uno, dos o cuatro o más dígitos es decimal.
        El decimal solo puede ser el último separador, y solo puede haber uno.

    Con eso, todo se resuelve sin ambigüedad y en las dos convenciones:

        "1.234.567"    → 1234567      tres y tres: miles
        "1.234.567,89" → 1234567.89   miles, miles, decimal
        "1,234,567.89" → 1234567.89   igual al revés
        "3800.00"      → 3800.0       dos dígitos detrás: decimal
        "1,50"         → 1.5
        "0.00"         → 0.0
        "1.2.3"        → error        el primer separador sería decimal y no es el último
        "12,34,567"    → error        mismo motivo
        "1..2"         → error

    El único caso genuinamente ambiguo —"1.234", que vale mil doscientos
    treinta y cuatro en Colombia y uno coma doscientos treinta y cuatro en
    inglés— se resuelve como MILES. Un monto con tres decimales es rarísimo
    en dinero; un grupo de miles es lo normal.

    `sep_decimal` queda como pista informativa y ya no decide nada. Antes sí
    decidía, y ahí estaba el problema: con `sep_decimal="."` —que es lo que
    pasan los adaptadores de Deel y Wise— "1.234.567" se partía por el
    último punto y salía 1234.567. Un CSV colombiano en pesos reclamado por
    esos adaptadores perdía un factor de mil, en silencio. La estructura no
    se deja engañar así.

    Validación: dígitos ASCII únicamente. `float()` acepta dígitos árabes y
    de ancho completo, y notación científica; nada de eso es un monto que
    deba entrar callado a un ledger.
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

    if not _TOKEN.fullmatch(t):
        raise malo("solo se aceptan dígitos separados por un punto o una coma")

    grupos = re.split(r"[.,]", t)
    seps = [c for c in t if c in ".,"]

    # Clasificar cada separador por el tamaño del grupo que le sigue.
    decimales = [i for i, g in enumerate(grupos[1:]) if len(g) != 3]
    if len(decimales) > 1:
        raise malo("hay más de un separador decimal")
    if decimales and decimales[0] != len(seps) - 1:
        raise malo(
            f"el separador {seps[decimales[0]]!r} parece decimal pero no es el "
            f"último: los grupos de miles llevan exactamente tres dígitos"
        )

    if decimales:
        entero_grupos, fraccion = grupos[:-1], grupos[-1]
        seps_miles = seps[:-1]
    else:
        entero_grupos, fraccion = grupos, ""
        seps_miles = seps

    if seps_miles and len(set(seps_miles)) > 1:
        raise malo("mezcla puntos y comas como separadores de miles")
    if len(entero_grupos) > 1 and len(entero_grupos[0]) > 3:
        raise malo(f"el primer grupo de miles tiene {len(entero_grupos[0])} dígitos")

    valor = float("".join(entero_grupos) + ("." + fraccion if fraccion else ""))
    if not math.isfinite(valor):
        raise malo("el número es tan grande que no cabe en un float")
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
