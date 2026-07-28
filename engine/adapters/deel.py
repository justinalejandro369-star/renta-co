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
from .generico import (_saltar_preambulo, abrir_csv, aviso_de_filas_saltadas,
                       convencion_del_archivo, convencion_de_fecha,
                       moneda_de, parse_fecha, parse_monto)

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
    # Los traslados a TU PROPIA cuenta van primero, y solo con frases que no
    # dejan duda ("to bank", "to your bank"). Un retiro trae con frecuencia
    # el número de la factura que lo originó —"Invoice INV-001 payout to bank
    # account"— y con los ingresos primero eso volvía a contar como ingreso
    # el dinero que ya se había contado. Base gravable al doble.
    (("payout to bank", "payout to your bank", "to your bank account",
      "transfer to bank", "bank transfer out", "withdraw", "retiro"),
     "traslado"),
    (("internal transfer", "balance transfer", "move funds", "transferencia interna"),
     "traslado"),
    # Los pagos SALIENTES a terceros, antes que los ingresos: "Payment to
    # contractor for milestone 2" trae "milestone", y es dinero que sale.
    (("contractor payment", "payout to contractor", "payment to contractor",
      "pago a contratista"), "costo_contratista"),
    (("payment to", "pago a"), "costo"),
    (("invoice", "payment received", "salary", "milestone", "bonus", "payment from",
      "contract payment", "pago recibido"), "ingreso_trabajo"),
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


# Categorías cuyo signo esperado es una ENTRADA. Si el texto dice ingreso y
# el monto es negativo, el texto y el signo se contradicen.
ENTRANTES = {"ingreso_trabajo", "ingreso_capital"}


# El campo `Type` de Deel es ESTRUCTURADO: lo escribe la plataforma, no una
# persona. La descripción es texto libre. Cuando los dos hablan, manda el
# estructurado — y no lo hacía: `blob = f"{tipo} {descripcion}"` los mezclaba
# en una sola cadena y ganaba la primera regla que coincidiera con
# cualquiera de los dos.
#
# El resultado, en un reporte de payouts (montos sin signo + columna de
# tipo, que es su forma normal):
#
#     Type=Withdrawal · "Invoice INV-001 payout to bank account"
#         → la palabra "invoice" gana → ingreso_trabajo
#
# O sea el retiro del dinero que ya se había contado como ingreso se cuenta
# OTRA VEZ como ingreso. Base gravable al doble, sin un solo aviso, y sin
# que el veto por signo pueda hacer nada porque el monto viene positivo.
TIPOS = [
    # `payout` NO está acá a propósito: en Deel significa tanto "payout to
    # your bank" (traslado) como "payout to contractor" (costo). Se deja que
    # decida la descripción, donde las frases de banco van primero.
    (("withdrawal", "withdraw", "retiro", "cash out"), "traslado"),
    (("exchange", "conversion", "conversión"), "traslado"),
    (("payment", "invoice", "salary", "bonus", "milestone", "deposit",
      "pago", "factura", "payout", "transfer", "transferencia", "fee",
      "charge"), None),   # ambiguo por sí solo: decide la descripción
]


def _por_tipo(tipo: str) -> str | None:
    """Categoría que impone el campo estructurado, si impone alguna."""
    t = tipo.strip().lower()
    if not t:
        return None
    for palabras, categoria in TIPOS:
        if any(p in t for p in palabras):
            return categoria
    return None


def _clasificar(tipo: str, descripcion: str, monto: float) -> str:
    """Categoría tributaria de un movimiento de Deel.

    El texto manda, pero el SIGNO tiene voto de veto. El reordenamiento de
    las reglas —los ingresos primero, para que "Invoice #002, platform fee
    deducted" no se fuera a costo— arregló ese caso y abrió cuatro: "Payment
    to contractor for milestone 2", "Payment to Juan - salary March", "Bonus
    payment to contractor Ana" y "Withdrawal - invoice #002 payout" son
    pagos SALIENTES que caen en la primera regla por traer "milestone",
    "salary", "bonus" e "invoice".

    Entraban como `ingreso_trabajo` con monto negativo, o sea un ingreso que
    RESTA de la base gravable. Y no lo atrapaba nada más: `avisos_de_signo`
    solo miraba costos y retenciones, así que 10.000.000 + (−3.000.000) daba
    7.000.000 y `validar()` devolvía lista vacía.

    Un ingreso no puede ser una salida de dinero. Cuando el texto dice
    ingreso y el signo dice lo contrario, no se elige uno de los dos: se
    manda a `desconocido`, que es lo que obliga al usuario a mirarlo.

    Y por encima de todo eso manda el campo estructurado `Type`. Ver TIPOS:
    un `Withdrawal` es un traslado aunque su descripción diga "invoice", y
    esa era la vía por la que el retiro del dinero ya contado como ingreso
    se volvía a contar como ingreso.
    """
    # 1. El campo estructurado, cuando dice algo inequívoco.
    impuesta = _por_tipo(tipo)
    if impuesta is not None:
        if impuesta in ENTRANTES and monto < 0:
            return "desconocido"
        return impuesta

    # 2. Si no, el texto libre, con el signo de veto.
    blob = f"{tipo} {descripcion}".lower()
    for palabras, categoria in REGLAS:
        if any(p in blob for p in palabras):
            if categoria in ENTRANTES and monto < 0:
                return "desconocido"
            return categoria
    # Sin señal textual no se adivina por el signo: se marca para revisión.
    return "desconocido"


def importar(ruta: Path, avisos: list[str] | None = None) -> list[Movimiento]:
    avisos = avisos if avisos is not None else []
    movimientos = []
    with abrir_csv(ruta, avisos) as f:
        _saltar_preambulo(f)
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

        # La convención de separadores es del ARCHIVO, no del adaptador. Con
        # `sep_decimal="."` fijo, un export reguardado desde Excel en locale
        # español declaraba "82.000" USD como 82 USD.
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
                moneda = moneda_de(fila, c_moneda, "USD")
                fecha = parse_fecha(crudo, conv_fecha)
                monto = parse_monto(fila.get(c_monto, "0"), sep, moneda)
            except ValueError as e:
                malas.append(f"línea {i}: {e}")
                continue
            if monto == 0:
                continue
            tipo = (fila.get(c_tipo) or "").strip() if c_tipo else ""
            desc = (fila.get(c_desc) or "").strip() if c_desc else ""
            movimientos.append(Movimiento(
                fecha=fecha,
                descripcion=(desc or tipo or "movimiento Deel"),
                monto_origen=monto,
                moneda=moneda,
                categoria=_clasificar(tipo, desc, monto),
                contraparte=((fila.get(c_parte) or "").strip() if c_parte else ""),
                fuente=ruta.name,
            ))
    if malas and not movimientos:
        raise ValueError(f"{ruta.name}: ninguna fila se pudo leer — {malas[0]}")
    if malas:
        avisos.append(aviso_de_filas_saltadas(ruta.name, malas, len(movimientos)))
    return movimientos
