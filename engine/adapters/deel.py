"""Adaptador Deel — reporte de transacciones.

Deel es la plataforma más común entre freelancers colombianos con clientes
del exterior. Su export mezcla, en un solo archivo:

  - pagos recibidos del cliente          → ingreso_trabajo
  - retiros a cuenta bancaria propia     → traslado (NO es gasto)
  - transferencias entre saldos propios  → traslado (NO es ingreso)
  - pagos salientes a contratistas       → costo (solo Ruta A, y exige PILA)
  - comisiones de la plataforma          → costo

Confundir un retiro con un ingreso duplica la base gravable. Es el error
más frecuente al importar Deel a mano, y por eso la clasificación acá es
explícita en vez de heurística sobre el signo.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..ledger import Movimiento
from .generico import abrir_csv, parse_fecha, parse_monto

NOMBRE = "Deel"

# Señales explícitas: si aparecen, es Deel sin duda.
SENALES_FUERTES = {"deel", "payment id", "contract id", "worker id", "payout id"}

# Forma del export de Deel cuando el archivo no se llama "deel-algo.csv":
# una columna de tipo de transacción + moneda + contraparte, que un extracto
# bancario colombiano nunca trae junto.
COLUMNAS_FORMA = [
    {"date", "fecha"},
    {"amount", "monto", "total"},
    {"currency", "moneda"},
    {"type", "transaction type", "tipo"},
    {"counterparty", "worker", "contractor", "client", "payee"},
]

# Palabras del campo tipo/descripción → categoría tributaria
# Gana la PRIMERA que coincide, así que el orden es la regla. Los ingresos
# van primero: "Invoice #002, platform fee deducted" trae la palabra "fee",
# y clasificarlo como costo borra el ingreso del ledger Y lo suma como gasto
# deducible — doble error, los dos a favor del contribuyente.
REGLAS = [
    (("invoice", "payment received", "salary", "milestone", "bonus", "payment from",
      "contract payment", "pago recibido"), "ingreso_trabajo"),
    (("withdraw", "retiro", "payout to bank", "bank transfer out", "transfer to bank"),
     "traslado"),
    (("internal transfer", "balance transfer", "move funds", "transferencia interna"),
     "traslado"),
    (("payment to", "contractor payment", "pago a", "payout to contractor"), "costo"),
    (("platform fee", "service charge", "wise charged", "transfer fee",
      "comision", "comisión"), "costo"),
]


def detecta(cabeceras: list[str], nombre: str = "") -> bool:
    """Reconoce un export de Deel.

    Regla de seguridad: **nunca reclamar un archivo sin columna de moneda**,
    salvo que el nombre del archivo diga Deel.

    Un CSV colombiano de Mercado Pago o PayU trae "Payment ID" y montos en
    pesos con punto de miles ("500.000"). Si este adaptador se lo quedaba, lo
    parseaba con separador decimal anglosajón (500.000 → 500,00) y le asignaba
    USD por defecto: dos errores compuestos y silenciosos que multiplicaban el
    ingreso declarado por ~4. Exigir la columna de moneda cierra las dos
    puertas a la vez, porque sin ella no hay nada que convertir.
    """
    normalizadas = {c.strip().lower() for c in cabeceras}
    texto = " ".join(normalizadas)

    if "deel" in nombre.lower():
        return True

    tiene_moneda = bool(normalizadas & {"currency", "moneda", "ccy"})
    if not tiene_moneda:
        return False

    if any(s in texto for s in SENALES_FUERTES):
        return True
    return all(normalizadas & alias for alias in COLUMNAS_FORMA)


def _clasificar(tipo: str, descripcion: str, monto: float) -> str:
    blob = f"{tipo} {descripcion}".lower()
    for palabras, categoria in REGLAS:
        if any(p in blob for p in palabras):
            return categoria
    # Sin señal textual no se adivina por el signo: se marca para revisión.
    return "desconocido"


def importar(ruta: Path) -> list[Movimiento]:
    movimientos = []
    with abrir_csv(ruta) as f:
        lector = csv.DictReader(f)
        campos = {c.lower().strip(): c for c in (lector.fieldnames or [])}

        def col(*nombres):
            for n in nombres:
                if n in campos:
                    return campos[n]
            return None

        c_fecha = col("date", "fecha", "created at", "payment date", "transaction date")
        c_monto = col("amount", "total", "monto", "value", "net amount")
        c_moneda = col("currency", "moneda", "ccy")
        c_tipo = col("type", "transaction type", "tipo", "category", "status")
        c_desc = col("description", "descripcion", "details", "memo", "note")
        c_parte = col("counterparty", "worker", "contractor", "client", "payee", "name")

        if not c_fecha or not c_monto:
            raise ValueError(
                f"El archivo de Deel {ruta.name} no tiene columnas de fecha y monto "
                f"reconocibles. Columnas: {lector.fieldnames}"
            )
        if not c_moneda:
            # Solo puede pasar si el archivo se llama "deel-algo.csv" y no trae
            # columna de moneda. Suponer USD acá cambiaría el ingreso por un
            # factor de ~4.000, y dejar que el genérico lo tome como COP hace
            # lo mismo al revés. Se corta el respaldo: hay que preguntar.
            from . import ErrorSinRespaldo

            raise ErrorSinRespaldo(
                f"{ruta.name} se identificó como export de Deel pero no trae "
                f"columna de moneda. No se supone USD: agrégala al CSV, o "
                f"renombra el archivo para que lo tome el adaptador genérico."
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
            tipo = (fila.get(c_tipo) or "").strip() if c_tipo else ""
            desc = (fila.get(c_desc) or "").strip() if c_desc else ""
            movimientos.append(Movimiento(
                fecha=fecha,
                descripcion=(desc or tipo or "movimiento Deel"),
                monto_origen=monto,
                moneda=(fila.get(c_moneda) or "USD").strip().upper(),
                categoria=_clasificar(tipo, desc, monto),
                contraparte=((fila.get(c_parte) or "").strip() if c_parte else ""),
                fuente=ruta.name,
            ))
    return movimientos
