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
                       convencion_del_archivo, convencion_de_fecha,
                       moneda_de, parse_fecha, parse_monto)

NOMBRE = "Bancolombia"

SENALES = {"bancolombia", "sucursal", "descripcion", "descripción", "documento"}

# Gana la PRIMERA que coincide. Los traslados van de últimos y con frases
# completas: "NEQUI" y "TRASLADO" como subcadenas convertían en traslado
# cualquier pago a un tercero por Nequi, que es como se le paga a medio país.
REGLAS = [
    (("gmf", "4x1000", "4 x 1000", "gravamen movimiento"), "gasto_personal"),
    # `retencion` a secas se llevaba a este renglón cualquier descripción
    # que mencionara la palabra: "PAGO A PROVEEDOR RETENCION APLICADA" (un
    # costo) y "PAGO PSE RETENCION ICA" (un impuesto municipal, que NO es
    # acreditable en renta). Y esta categoría no resta de la base: resta del
    # IMPUESTO, peso por peso, contra un renglón que la DIAN cruza con los
    # certificados de cada agente retenedor. Fabricar crédito acá es de lo
    # más caro que puede hacer la herramienta.
    #
    # Se piden frases de retención EN LA FUENTE. Lo demás va a revisión.
    (("retencion en la fuente", "retención en la fuente", "rte fte",
      "retefuente", "rte.fte", "retencion fuente", "retención fuente"),
     "retencion"),
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
    with abrir_csv(ruta, avisos) as f:
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
        # La moneda se LEE si el archivo la trae. Estaba cableada a "COP", y
        # Bancolombia sí tiene cuentas en dólares y de compensación: un
        # extracto en USD reclamado por este adaptador salía como pesos, o
        # sea dividido por la TRM. Factor ~4.000 de subdeclaración, en
        # silencio y con código de salida 0. Sin columna, COP es correcto:
        # es un banco colombiano.
        c_moneda = col("moneda", "currency", "divisa", "ccy")

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
        conv_fecha, avisos_fecha = convencion_de_fecha(
            fila.get(c_fecha, "") for fila in filas
        )
        avisos += [f"{ruta.name}: {a}" for a in avisos_sep + avisos_fecha]

        malas: list[str] = []
        for i, fila in enumerate(filas, start=2):
            crudo = (fila.get(c_fecha) or "").strip()
            if not crudo:
                continue
            try:
                moneda = moneda_de(fila, c_moneda, "COP")
                fecha = parse_fecha(crudo, conv_fecha)
                monto = parse_monto(fila.get(c_monto, "0"), sep, moneda)
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
                moneda=moneda,
                categoria=_clasificar(desc, monto),
                contraparte=((fila.get(c_doc) or "").strip() if c_doc else ""),
                fuente=ruta.name,
            ))
    if malas and not movimientos:
        raise ValueError(f"{ruta.name}: ninguna fila se pudo leer — {malas[0]}")
    if malas:
        avisos.append(aviso_de_filas_saltadas(ruta.name, malas, len(movimientos)))
    return movimientos
