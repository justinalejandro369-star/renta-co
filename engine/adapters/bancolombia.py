"""Adaptador Bancolombia — extracto de cuenta de ahorros / corriente.

Formato colombiano: montos con punto de miles y coma decimal, fechas
dd/mm/aaaa, y una sola columna de valor con signo. Sirve de plantilla para
cualquier banco colombiano — Davivienda, BBVA, Nu, Nequi cambian solo los
nombres de columna.

Todo entra como 'desconocido' salvo señales inequívocas. Un extracto
bancario no tiene información suficiente para saber si una salida fue costo
deducible o gasto personal: eso lo decide el contribuyente.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..ledger import Movimiento
from .generico import (abrir_csv, aviso_de_filas_saltadas,
                       convencion_del_archivo, parse_fecha, parse_monto)

NOMBRE = "Bancolombia"

SENALES = {"bancolombia", "sucursal", "descripcion", "descripción", "documento"}

# Gana la PRIMERA que coincide. Los traslados van de últimos y con frases
# completas: "NEQUI" y "TRASLADO" como subcadenas convertían en traslado
# cualquier pago a un tercero por Nequi, que es como se le paga a medio país.
REGLAS = [
    (("gmf", "4x1000", "4 x 1000", "gravamen movimiento"), "gasto_personal"),
    (("retencion", "retención", "rte fte", "retefuente"), "retencion"),
    (("rendimiento", "intereses ganados", "abono intereses"), "ingreso_capital"),
    # Frases, no subcadenas sueltas: "NEQUI" a secas convertía en traslado
    # cualquier pago a un tercero. Pero tampoco tan literales que dejen de
    # ver los traslados reales — ninguna de estas menciona Nequi.
    (("traslado entre cuentas", "traslado a cuenta", "traslado de cuenta",
      "traslado a ahorro", "traslado de ahorro", "traslado cuenta propia",
      "transferencia a cuenta propia", "transferencia cta propia",
      "transferencia entre cuentas"), "traslado"),
]


def detecta(cabeceras: list[str], nombre: str = "") -> bool:
    texto = " ".join(c.lower() for c in cabeceras)
    if "bancolombia" in nombre.lower():
        return True
    return sum(1 for s in SENALES if s in texto) >= 2


# Igual que en deel.py y wise.py: el texto propone y el signo veta. Un
# "ABONO INTERESES" en negativo es una reversión, no un rendimiento, y
# meterlo como ingreso_capital le resta a la base gravable.
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
    with abrir_csv(ruta) as f:
        lector = csv.DictReader(f)
        campos = {c.lower().strip(): c for c in (lector.fieldnames or [])}

        def col(*nombres):
            for n in nombres:
                if n in campos:
                    return campos[n]
            return None

        c_fecha = col("fecha", "fecha movimiento", "fecha de transaccion")
        c_monto = col("valor", "monto", "valor total", "importe")
        c_desc = col("descripcion", "descripción", "concepto", "detalle")
        c_doc = col("documento", "referencia", "numero documento")

        if not c_fecha or not c_monto:
            raise ValueError(
                f"El extracto {ruta.name} no tiene columnas de fecha y valor "
                f"reconocibles. Columnas: {lector.fieldnames}. Si tu banco usa "
                f"otros nombres, agrégalos a este adaptador y manda el PR."
            )

        # `sep_decimal=","` fijo hacía que "150,000" saliera 150 mientras
        # "2,500,000" salía bien: corrupción parcial dentro del MISMO
        # archivo, que ningún cuadre de totales detecta. La convención la
        # prueba el archivo entero, y en pesos además manda la moneda.
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
            try:
                fecha = parse_fecha(crudo)
                monto = parse_monto(fila.get(c_monto, "0"), sep, "COP")
            except ValueError as e:
                malas.append(f"línea {i}: {e}")
                continue
            if monto == 0:
                continue
            desc = (fila.get(c_desc) or "").strip() if c_desc else ""
            movimientos.append(Movimiento(
                fecha=fecha,
                descripcion=desc or "movimiento bancario",
                monto_origen=monto,
                moneda="COP",
                categoria=_clasificar(desc, monto),
                contraparte=((fila.get(c_doc) or "").strip() if c_doc else ""),
                fuente=ruta.name,
            ))
    if malas and not movimientos:
        raise ValueError(f"{ruta.name}: ninguna fila se pudo leer — {malas[0]}")
    if malas:
        avisos.append(aviso_de_filas_saltadas(ruta.name, malas, len(movimientos)))
    return movimientos
