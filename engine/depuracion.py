"""Motor de depuración de la cédula general — persona natural residente.

Compara las dos rutas EXCLUYENTES del art. 336 num. 4 ET:

    RUTA A → restar costos y gastos procedentes
    RUTA B → restar la renta exenta del 25% (art. 206 num. 10 + par. 5)

y produce una tabla de sensibilidad que dice, en pesos, cuánto ahorra cada
palanca disponible. Determinista y sin dependencias externas: el mismo
perfil produce siempre el mismo resultado, y se puede recalcular a mano.

    from engine import perfil, parametros, depuracion
    p = perfil.cargar("./expediente")
    par = parametros.cargar(p.anio_gravable)
    resultado = depuracion.comparar(p, par)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .parametros import Parametros
from .perfil import Perfil

RUTAS = {
    "A": "Costos y gastos (art. 336 num. 4)",
    "B": "Renta exenta 25% (art. 206 num. 10)",
}


# ---------------------------------------------------------------------
# Tarifa
# ---------------------------------------------------------------------

def impuesto_241(base_cop: float, par: Parametros) -> float:
    """Impuesto del art. 241 sobre una base en pesos."""
    if base_cop <= 0:
        return 0.0
    base_uvt = base_cop / par.uvt
    for rango in par.exigir("tarifa.rangos"):
        hasta = rango["hasta_uvt"]
        if hasta == 0 or base_uvt <= hasta:
            uvt = (base_uvt - rango["desde_uvt"]) * rango["tarifa"] + rango["adicional_uvt"]
            return round(max(uvt, 0) * par.uvt)
    return 0.0


def tarifa_marginal(base_cop: float, par: Parametros) -> float:
    base_uvt = base_cop / par.uvt if par.uvt else 0
    for rango in par.exigir("tarifa.rangos"):
        hasta = rango["hasta_uvt"]
        if hasta == 0 or base_uvt <= hasta:
            return rango["tarifa"]
    return 0.0


# ---------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------

@dataclass
class Renglon:
    concepto: str
    valor: float
    signo: int = 0        # -1 resta, +1 suma, 0 subtotal
    nota: str = ""
    fuente: str = ""


@dataclass
class Liquidacion:
    ruta: str
    renglones: list[Renglon] = field(default_factory=list)
    renta_liquida: float = 0
    impuesto: float = 0
    impuesto_neto: float = 0
    saldo: float = 0            # >0 a pagar, <0 a favor
    tope_conjunto: float = 0
    rechazado_por_tope: float = 0
    dependientes_via: str = ""

    def _r(self, concepto, valor, signo=0, nota="", fuente=""):
        self.renglones.append(Renglon(concepto, round(valor), signo, nota, fuente))
        return valor


# ---------------------------------------------------------------------
# Depuración de una ruta
# ---------------------------------------------------------------------

def liquidar(p: Perfil, par: Parametros, ruta: str) -> Liquidacion:
    if ruta not in RUTAS:
        raise ValueError(f"Ruta '{ruta}' no válida. Usa 'A' o 'B'.")

    L = Liquidacion(ruta=ruta)
    uvt = par.uvt

    # --- 1. ingresos ---------------------------------------------------
    trabajo = p.get("ingresos.rentas_trabajo_honorarios")
    capital = p.get("ingresos.rentas_capital")
    otras = p.get("ingresos.otras_rentas_no_laborales")

    L._r("Rentas de trabajo (honorarios y compensación por servicios)", trabajo, +1)
    L._r("Rentas de capital", capital, +1)
    L._r("Otras rentas no laborales", otras, +1)
    brutos = trabajo + capital + otras
    L._r("= Total ingresos brutos cédula general", brutos)

    # --- 2. INCRNGO ----------------------------------------------------
    incrngo = p.total_incrngo
    L._r(
        "− Ingresos no constitutivos de renta (INCRNGO)", incrngo, -1,
        nota="Aportes obligatorios de salud y pensión + componente inflacionario. "
             "Restan ANTES del tope del 40%: no lo consumen.",
        fuente="ET arts. 55 y 56",
    )
    netos = brutos - incrngo
    L._r("= Ingresos netos (base del límite del 40%)", netos)

    # --- 3. costos, solo ruta A ----------------------------------------
    costos = p.total_costos if ruta == "A" else 0
    L._r(
        "− Costos y gastos procedentes", costos, -1,
        nota=("Sin tope, pero cada uno exige factura o documento soporte, y los "
              "pagos a contratistas exigen verificar sus aportes a seguridad social "
              "(art. 108 par. 2 ET)." if ruta == "A"
              else "No aplica en Ruta B: son excluyentes con la renta exenta."),
        fuente="ET art. 336 num. 4",
    )

    # --- 4. renta exenta 25%, solo ruta B ------------------------------
    renta_exenta = 0.0
    if ruta == "B":
        pct = par.exigir("topes.renta_exenta_25.porcentaje")
        tope_mes = par.exigir("topes.renta_exenta_25.tope_mensual_uvt")
        meses = par.get("topes.renta_exenta_25.meses", 12)
        # base: rentas de trabajo depuradas de INCRNGO y deducciones imputables
        base_exenta = max(trabajo - incrngo, 0)
        renta_exenta = min(base_exenta * pct, tope_mes * meses * uvt)

    # --- 5. deducciones dentro del tope conjunto ------------------------
    gmf = p.get("deducciones.gmf_pagado") * par.exigir("topes.gmf.porcentaje_deducible")
    vivienda = min(
        p.get("deducciones.intereses_vivienda"),
        par.exigir("topes.intereses_vivienda.tope_uvt") * uvt,
    )
    prepagada = min(
        p.get("deducciones.medicina_prepagada"),
        par.exigir("topes.medicina_prepagada.tope_mensual_uvt")
        * par.get("topes.medicina_prepagada.meses", 12)
        * uvt,
    )
    voluntarios = min(
        p.get("deducciones.aportes_voluntarios"),
        brutos * par.exigir("topes.aportes_voluntarios.porcentaje_ingreso"),
        par.exigir("topes.aportes_voluntarios.tope_uvt") * uvt,
    )

    # --- 6. dependientes: dos vías excluyentes, se toma la mejor --------
    n_dep = int(p.get("deducciones.dependientes"))
    max_dep = par.exigir("topes.dependientes_72uvt.maximo_dependientes")
    dep_72 = min(n_dep, max_dep) * par.exigir("topes.dependientes_72uvt.uvt_por_dependiente") * uvt

    dep_10 = 0.0
    if n_dep > 0:
        dep_10 = min(
            trabajo * par.exigir("topes.dependientes_10pct.porcentaje_renta_trabajo"),
            par.exigir("topes.dependientes_10pct.tope_mensual_uvt")
            * par.get("topes.dependientes_10pct.meses", 12)
            * uvt,
        )

    # La de 72 UVT queda FUERA del tope conjunto; la del 10% queda DENTRO.
    # Se evalúan las dos combinaciones completas y se toma la de menor impuesto.
    ded_limitadas_base = gmf + vivienda + prepagada + voluntarios

    def _aplicar_tope(ded_limitadas: float, exenta: float):
        tope = min(
            netos * par.exigir("topes.conjunto_deducciones_exentas.porcentaje_ingresos_netos"),
            par.exigir("topes.conjunto_deducciones_exentas.tope_uvt") * uvt,
        )
        solicitado = ded_limitadas + exenta
        aplicado = min(solicitado, tope)
        return tope, aplicado, solicitado - aplicado

    # 1% de compras con factura electrónica — fuera del tope
    fe = min(
        p.get("deducciones.compras_con_factura_electronica")
        * par.exigir("topes.deduccion_1pct_factura_electronica.porcentaje_compras"),
        par.exigir("topes.deduccion_1pct_factura_electronica.tope_uvt") * uvt,
    )

    opciones = []
    for via, dentro, fuera in (
        ("72 UVT por dependiente (fuera del tope)", 0.0, dep_72),
        ("10% de la renta de trabajo (dentro del tope)", dep_10, 0.0),
    ):
        tope, aplicado, rechazado = _aplicar_tope(ded_limitadas_base + dentro, renta_exenta)
        rl = max(netos - costos - aplicado - fuera - fe, 0)
        opciones.append((impuesto_241(rl, par), via, dentro, fuera, tope, aplicado, rechazado, rl))

    if n_dep == 0:
        opciones = opciones[:1]

    (_, via, dep_dentro, dep_fuera, tope, aplicado, rechazado, renta_liquida) = min(
        opciones, key=lambda o: o[0]
    )
    L.dependientes_via = via if n_dep else "sin dependientes"
    ded_limitadas = ded_limitadas_base + dep_dentro

    # --- 7. renglones de deducciones -----------------------------------
    L._r("− Renta exenta 25%", renta_exenta, -1,
         nota=("Tope 240 UVT/mes Y además compite dentro del tope conjunto del 40%."
               if ruta == "B" else "No aplica en Ruta A."),
         fuente="ET art. 206 num. 10")
    L._r("− GMF deducible (50% del 4x1000 pagado)", gmf, -1, fuente="ET art. 115")
    L._r("− Intereses de vivienda", vivienda, -1, fuente="ET art. 119")
    L._r("− Medicina prepagada", prepagada, -1, fuente="ET art. 387 num. 1")
    L._r("− Aportes voluntarios AFP / AFC", voluntarios, -1, fuente="ET arts. 126-1 y 126-4")
    if dep_dentro:
        L._r("− Dependientes (10% renta de trabajo)", dep_dentro, -1, fuente="ET art. 387")

    L._r("  [tope conjunto 40% / 1.340 UVT]", tope, 0,
         nota="Lo que exceda este tope se pierde.",
         fuente="ET art. 336 num. 3")
    L._r("  [rechazado por el tope]", rechazado, 0,
         nota="Deducciones y rentas exentas solicitadas que el tope no dejó pasar.")
    L.tope_conjunto = tope
    L.rechazado_por_tope = rechazado

    if dep_fuera:
        L._r("− Dependientes (72 UVT c/u — FUERA del tope)", dep_fuera, -1,
             nota="No consume el tope del 40% y no exige factura: solo acreditar la condición.",
             fuente="ET art. 336 par., Ley 2277 de 2022 art. 7")
    L._r("− Deducción 1% compras con factura electrónica", fe, -1,
         nota="Exige factura electrónica a tu NIT/cédula y pago electrónico.",
         fuente="ET art. 336 par. 4")

    # --- 8. impuesto ---------------------------------------------------
    L.renta_liquida = renta_liquida
    L._r("= RENTA LÍQUIDA GRAVABLE", renta_liquida)

    L.impuesto = impuesto_241(renta_liquida, par)
    L._r("IMPUESTO SOBRE LA RENTA", L.impuesto, +1, fuente="ET art. 241")

    donado = p.get("descuentos.donaciones_certificadas_rte")
    descuento = min(
        donado * par.exigir("topes.descuento_donaciones.porcentaje_descuento"),
        L.impuesto * par.exigir("topes.descuento_donaciones.tope_porcentaje_impuesto"),
    )
    L._r("− Descuento por donaciones", descuento, -1,
         nota="Solo con certificado de entidad del Régimen Tributario Especial "
              "firmado por representante legal y contador o revisor fiscal.",
         fuente="ET art. 257")

    L.impuesto_neto = max(L.impuesto - descuento, 0)
    L._r("= Impuesto neto de renta", L.impuesto_neto)

    retenciones = p.get("anticipos.retenciones_practicadas")
    saldo_favor_ant = p.get("anticipos.saldo_a_favor_anio_anterior")
    L._r("− Retenciones practicadas en el año", retenciones, -1)
    L._r("− Saldo a favor del año anterior", saldo_favor_ant, -1)

    L.saldo = L.impuesto_neto - retenciones - saldo_favor_ant
    L._r("= SALDO A PAGAR" if L.saldo >= 0 else "= SALDO A FAVOR", abs(L.saldo))

    return L


# ---------------------------------------------------------------------
# Sensibilidad — cuánto vale cada palanca, en pesos
# ---------------------------------------------------------------------

@dataclass
class Palanca:
    etiqueta: str
    ahorro_a: float
    ahorro_b: float
    solo_ruta: str | None
    nota: str

    @property
    def ahorro_max(self) -> float:
        return max(self.ahorro_a, self.ahorro_b)


def _saldo(p: Perfil, par: Parametros, ruta: str) -> float:
    return liquidar(p, par, ruta).saldo


def sensibilidad(p: Perfil, par: Parametros) -> list[Palanca]:
    """Perturba una variable a la vez y mide el impuesto que ahorra.

    Las magnitudes de prueba se escalan al tamaño del contribuyente, para que
    la tabla sea informativa tanto para quien factura 50 M como para quien
    factura 500 M.
    """
    uvt = par.uvt
    base_a = _saldo(p, par, "A")
    base_b = _saldo(p, par, "B")
    ingreso = max(p.ingresos_brutos, 1)
    palancas: list[Palanca] = []

    def probar(etiqueta, cambios, nota, solo_ruta=None):
        alt = p.copia_con(**cambios)
        pa, pb = _saldo(alt, par, "A"), _saldo(alt, par, "B")
        palancas.append(
            Palanca(etiqueta, base_a - pa, base_b - pb, solo_ruta, nota)
        )

    # --- dependientes ---------------------------------------------------
    actuales = int(p.get("deducciones.dependientes"))
    max_dep = par.exigir("topes.dependientes_72uvt.maximo_dependientes")
    for n in range(actuales + 1, max_dep + 1):
        probar(
            f"Acreditar {n} dependiente(s) — hoy tienes {actuales}",
            {"deducciones__dependientes": n},
            "FUERA del tope del 40%. No exige factura ni desembolso: se acredita "
            "la condición. Padres y hermanos con ingresos anuales < 260 UVT cuentan.",
        )

    # --- seguridad social ------------------------------------------------
    if not p.get("incrngo.aportes_obligatorios_salud_pension"):
        # base de cotización del independiente: 40% del ingreso, tarifa ~28,5%
        estimado = round(ingreso * 0.40 * 0.285)
        probar(
            f"Aportes obligatorios salud+pensión del año (~{_cop(estimado)})",
            {"incrngo__aportes_obligatorios_salud_pension": estimado},
            "Es INCRNGO, no deducción: resta ANTES del tope del 40% y no lo consume. "
            "Exige planillas PILA pagadas. También reduce tu exposición ante la UGPP.",
        )

    # --- aportes voluntarios ----------------------------------------------
    if not p.get("deducciones.aportes_voluntarios"):
        techo = min(ingreso * 0.30, par.exigir("topes.aportes_voluntarios.tope_uvt") * uvt)
        probar(
            f"Aportes voluntarios AFP/AFC al tope (~{_cop(techo)})",
            {"deducciones__aportes_voluntarios": round(techo)},
            "⚠ Solo sirve si se hicieron ANTES del 31 de diciembre del año gravable. "
            "Si el año ya cerró, este número es tu costo de oportunidad — planéalo "
            "para el año en curso.",
        )

    # --- medicina prepagada -------------------------------------------------
    if not p.get("deducciones.medicina_prepagada"):
        techo = par.exigir("topes.medicina_prepagada.tope_mensual_uvt") * 12 * uvt
        probar(
            f"Medicina prepagada al tope ({_cop(techo)})",
            {"deducciones__medicina_prepagada": round(techo)},
            "Dentro del tope del 40%: en Ruta B compite contra la renta exenta y "
            "puede no agregar nada. Exige certificado de la aseguradora.",
        )

    # --- intereses de vivienda ----------------------------------------------
    if not p.get("deducciones.intereses_vivienda"):
        techo = min(par.exigir("topes.intereses_vivienda.tope_uvt") * uvt, ingreso * 0.15)
        probar(
            f"Intereses de crédito de vivienda (~{_cop(techo)})",
            {"deducciones__intereses_vivienda": round(techo)},
            "Certificado anual del banco. Dentro del tope del 40%.",
        )

    # --- costos, solo ruta A --------------------------------------------------
    if p.total_costos == 0:
        estimado = round(ingreso * 0.30)
        probar(
            f"Costos y gastos soportados (~{_cop(estimado)})",
            {"costos__otros": estimado},
            "SOLO RUTA A. Sin tope, pero cada peso exige factura electrónica o "
            "documento soporte, y los pagos a contratistas exigen verificar sus "
            "aportes a seguridad social.",
            solo_ruta="A",
        )

    # --- factura electrónica ---------------------------------------------------
    if not p.get("deducciones.compras_con_factura_electronica"):
        compras = round(ingreso * 0.20)
        probar(
            f"Compras con factura electrónica a tu cédula (~{_cop(compras)})",
            {"deducciones__compras_con_factura_electronica": compras},
            "Deduce el 1%, tope 240 UVT, FUERA del tope del 40%. Exige que la "
            "factura salga a tu NIT/cédula y que el pago sea electrónico.",
        )

    # --- donaciones ------------------------------------------------------------
    if not p.get("descuentos.donaciones_certificadas_rte"):
        monto = round(ingreso * 0.03)
        probar(
            f"Donaciones certificadas a entidad del RTE (~{_cop(monto)})",
            {"descuentos__donaciones_certificadas_rte": monto},
            "Es DESCUENTO del 25% sobre el impuesto, no deducción. Exige "
            "certificación firmada. Una transferencia a una persona o colecta vale $0.",
        )

    palancas.sort(key=lambda x: x.ahorro_max, reverse=True)
    return [x for x in palancas if x.ahorro_max > 0]


# ---------------------------------------------------------------------
# Verificaciones de obligación y riesgo
# ---------------------------------------------------------------------

def verificar_obligaciones(p: Perfil, par: Parametros) -> list[dict]:
    """Chequeos de umbral que no dependen del cálculo del impuesto."""
    uvt = par.uvt
    checks = []

    # ¿obligado a declarar?
    u = par.get("umbrales.obligado_a_declarar", {})
    disparadores = []
    if p.ingresos_brutos >= u.get("ingresos_brutos_uvt", 1400) * uvt:
        disparadores.append("ingresos brutos ≥ 1.400 UVT")
    if p.patrimonio_bruto >= u.get("patrimonio_bruto_uvt", 4500) * uvt:
        disparadores.append("patrimonio bruto ≥ 4.500 UVT")
    consig = p.get("verificaciones.consignaciones_totales_anio")
    if consig >= u.get("consignaciones_uvt", 1400) * uvt:
        disparadores.append("consignaciones ≥ 1.400 UVT")

    checks.append({
        "id": "OBL-01",
        "titulo": "¿Obligado a declarar renta?",
        "estado": "SÍ" if disparadores else "NO por los datos cargados",
        "detalle": ("Se cumple: " + "; ".join(disparadores)) if disparadores
                   else "Ningún umbral superado con los datos actuales. Verifica "
                        "también consumos con tarjeta de crédito y compras totales.",
        "severidad": "info",
        "fuente": u.get("fuente", ""),
    })

    # ¿pierde la calidad de no responsable de IVA?
    iva = par.get("umbrales.no_responsable_iva", {})
    tope_iva = iva.get("consignaciones_uvt", 3500) * uvt
    if consig == 0:
        estado, sev = "SIN CUANTIFICAR", "alta"
        detalle = (
            f"No has cargado el total de consignaciones del año. El umbral es "
            f"{_cop(tope_iva)} y se mide sobre TODO lo que entró a tus cuentas, "
            f"no sobre tu ingreso propio. Súmalo de los extractos de todas tus "
            f"cuentas antes de presentar."
        )
    elif consig > tope_iva:
        estado, sev = "UMBRAL SUPERADO", "alta"
        detalle = (
            f"Consignaciones {_cop(consig)} > {_cop(tope_iva)}. Pierdes la calidad "
            f"de no responsable de IVA: obligación de inscribirte, facturar y "
            f"declarar IVA, más sanciones por cada declaración omitida. Evalúa si "
            f"tu actividad califica como exportación de servicios exenta "
            f"(art. 481 lit. c ET). Resuélvelo ANTES de presentar renta."
        )
    else:
        margen = tope_iva - consig
        estado, sev = "DENTRO DEL UMBRAL", "info"
        detalle = f"Consignaciones {_cop(consig)}, margen de {_cop(margen)}."

    checks.append({
        "id": "R-01",
        "titulo": "Calidad de no responsable de IVA (umbral de consignaciones)",
        "estado": estado,
        "detalle": detalle,
        "severidad": sev,
        "fuente": iva.get("fuente", "ET art. 437 par. 3"),
    })

    # ¿agente de retención?
    ar = par.get("umbrales.agente_retencion_persona_natural", {})
    checks.append({
        "id": "OBL-02",
        "titulo": "¿Era agente de retención en la fuente?",
        "estado": "NO (perfil de servicios profesionales)",
        "detalle": (
            "El art. 368-2 ET exige DOS condiciones concurrentes: tener calidad de "
            "COMERCIANTE, y superar 30.000 UVT de patrimonio o ingresos del año "
            "anterior. Quien presta servicios profesionales no es comerciante en el "
            "sentido del art. 20 C.Co., así que no es agente de retención sin "
            "importar el monto. Si vendes bienes o ejerces actos de comercio, "
            "revísalo con tu contador."
        ),
        "severidad": "info",
        "fuente": ar.get("fuente", "ET art. 368-2"),
    })

    # costos sin verificación de aportes
    if p.total_costos > 0 and not p.get("verificaciones.contratistas_con_pila_verificada"):
        checks.append({
            "id": "R-02",
            "titulo": "Costos por pagos a contratistas sin verificar aportes",
            "estado": "SIN VERIFICAR",
            "detalle": (
                f"Tienes {_cop(p.total_costos)} en costos. El art. 108 par. 2 ET exige "
                f"verificar la afiliación y el pago de aportes a seguridad social de "
                f"cada contratista. Si no cotizaron, la DIAN puede rechazar la "
                f"totalidad del costo y la Ruta A pierde su fundamento. Pide la "
                f"planilla PILA de cada persona."
            ),
            "severidad": "alta",
            "fuente": "ET art. 108 par. 2",
        })

    return checks


# ---------------------------------------------------------------------
# Comparación completa
# ---------------------------------------------------------------------

def comparar(p: Perfil, par: Parametros) -> dict:
    a = liquidar(p, par, "A")
    b = liquidar(p, par, "B")
    mejor = "A" if a.saldo <= b.saldo else "B"

    return {
        "anio_gravable": p.anio_gravable,
        "uvt": par.uvt,
        "rutas": {"A": a, "B": b},
        "mejor_ruta": mejor,
        "diferencia_entre_rutas": abs(a.saldo - b.saldo),
        "sensibilidad": sensibilidad(p, par),
        "verificaciones": verificar_obligaciones(p, par),
        "patrimonio_bruto": p.patrimonio_bruto,
        "pasivos": p.pasivos,
        "patrimonio_liquido": p.patrimonio_bruto - p.pasivos,
        "tarifa_marginal": tarifa_marginal(
            (a if mejor == "A" else b).renta_liquida, par
        ),
        "supuestos": p.supuestos,
        "faltantes": p.faltantes,
        "advertencias_parametros": par.advertencias(),
    }


def _cop(x: float) -> str:
    return f"${x:,.0f}".replace(",", ".")
