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

def _fuente(par: Parametros, ruta_valor: str, respaldo: str) -> str:
    """Cita normativa de un renglón, tomada de knowledge/.

    La cifra sale de `knowledge/<año>/parametros.toml` y la cita salía de un
    literal en Python, así que las dos podían divergir — y divergían. Tres
    ejemplos que encontró la ronda 5, todos con la cita del motor y la del
    knowledge apuntando a normas distintas para el MISMO número:

        medicina prepagada    motor: art. 387 num. 1
                          knowledge: art. 387 inciso 2 lit. a) y b)
        dependientes 72 UVT   motor: art. 336 par.
                          knowledge: art. 336 num. 3 inciso 2
        1% factura elect.     motor: art. 336 par. 4
                          knowledge: art. 336 numeral 5

    La que ve el contador en el CSV es la del motor, así que la del knowledge
    —que es la verificada, la que tiene URL y la que revisa el test de
    fuentes— no servía de nada. Ahora la cita viene del mismo sitio que la
    cifra, y el literal queda solo como respaldo para cuando un año gravable
    todavía no declare esa fuente.
    """
    citada = par.fuente(ruta_valor)
    return respaldo if citada == "sin fuente citada" else citada


def liquidar(p: Perfil, par: Parametros, ruta: str) -> Liquidacion:
    if ruta not in RUTAS:
        raise ValueError(f"Ruta '{ruta}' no válida. Usa 'A' o 'B'.")

    L = Liquidacion(ruta=ruta)
    uvt = par.uvt

    # --- 1. ingresos ---------------------------------------------------
    trabajo = p.get("ingresos.rentas_trabajo_honorarios")
    capital = p.get("ingresos.rentas_capital")
    otras = p.get("ingresos.otras_rentas_no_laborales")

    L._r("Rentas de trabajo (honorarios y compensación por servicios)", trabajo, +1,
         fuente="ET art. 335 y art. 103")
    L._r("Rentas de capital", capital, +1, fuente="ET art. 338")
    L._r("Otras rentas no laborales", otras, +1, fuente="ET art. 340")
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

    # --- 4. deducciones dentro del tope conjunto ------------------------
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

    # --- 5. dependientes: dos vías excluyentes, se toma la mejor --------
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
    ded_fijas = gmf + vivienda + prepagada + voluntarios

    # 1% de compras con factura electrónica — fuera del tope
    fe = min(
        p.get("deducciones.compras_con_factura_electronica")
        * par.exigir("topes.deduccion_1pct_factura_electronica.porcentaje_compras"),
        par.exigir("topes.deduccion_1pct_factura_electronica.tope_uvt") * uvt,
    )

    tope = max(
        min(
            netos * par.exigir("topes.conjunto_deducciones_exentas.porcentaje_ingresos_netos"),
            par.exigir("topes.conjunto_deducciones_exentas.tope_uvt") * uvt,
        ),
        0,
    )

    def evaluar(dep_dentro: float, dep_fuera: float):
        """Liquida una de las dos combinaciones de dependientes.

        La renta exenta se calcula ACÁ ADENTRO y no antes, porque su base
        depende de las deducciones —y las deducciones dependen de qué vía de
        dependientes se tome—.
        """
        ded_limitadas = ded_fijas + dep_dentro

        exenta = 0.0
        if ruta == "B":
            # Art. 206 num. 10 inciso 2: la base de la exención se calcula
            # UNA VEZ SE DETRAIGAN los INCRNGO, las deducciones y las rentas
            # exentas distintas de esta. No es el 25% del ingreso bruto.
            base = trabajo - incrngo - ded_limitadas - dep_fuera - fe
            exenta = min(
                max(base, 0) * par.exigir("topes.renta_exenta_25.porcentaje"),
                par.exigir("topes.renta_exenta_25.tope_anual_uvt") * uvt,
            )

        solicitado = ded_limitadas + exenta
        aplicado = min(solicitado, tope)
        rechazado = solicitado - aplicado
        rl = max(netos - costos - aplicado - dep_fuera - fe, 0)
        return {
            "impuesto": impuesto_241(rl, par),
            "renta_liquida": rl,
            "exenta": exenta,
            "dep_dentro": dep_dentro,
            "dep_fuera": dep_fuera,
            "aplicado": aplicado,
            "rechazado": rechazado,
        }

    opciones = [("72 UVT por dependiente (fuera del tope)", evaluar(0.0, dep_72))]
    if n_dep > 0:
        opciones.append(
            ("10% de la renta de trabajo (dentro del tope)", evaluar(dep_10, 0.0))
        )

    via, e = min(opciones, key=lambda o: o[1]["impuesto"])
    L.dependientes_via = via if n_dep else "sin dependientes"
    renta_liquida = e["renta_liquida"]
    tope_aplicado, rechazado = e["aplicado"], e["rechazado"]

    # --- 6. renglones de deducciones -----------------------------------
    # Se emiten SIEMPRE los mismos renglones, en el mismo orden, aunque
    # valgan cero. El comparativo imprime las dos rutas lado a lado por
    # posición: un renglón condicional desalinea la columna entera y hace
    # que un número aparezca bajo la etiqueta de otro.
    L._r("− Renta exenta 25%", e["exenta"], -1,
         nota=("Base = rentas de trabajo − INCRNGO − deducciones (art. 206 "
               "num. 10 inciso 2). Tope 790 UVT ANUALES —no 240 UVT/mes, que "
               "es el texto derogado— y además compite dentro del tope "
               "conjunto del 40%." if ruta == "B"
               else "No aplica en Ruta A: es excluyente con los costos."),
         fuente="ET art. 206 num. 10, mod. Ley 2277 de 2022 art. 2")
    L._r("− GMF deducible (50% del 4x1000 pagado)", gmf, -1,
         fuente=_fuente(par, "topes.gmf.porcentaje_deducible", "ET art. 115"))
    L._r("− Intereses de vivienda", vivienda, -1,
         fuente=_fuente(par, "topes.intereses_vivienda.tope_uvt", "ET art. 119"))
    L._r("− Medicina prepagada", prepagada, -1,
         fuente=_fuente(par, "topes.medicina_prepagada.tope_mensual_uvt",
                        "ET art. 387"))
    L._r("− Aportes voluntarios AFP / AFC", voluntarios, -1,
         fuente=_fuente(par, "topes.aportes_voluntarios.tope_uvt",
                        "ET arts. 126-1 y 126-4"))
    L._r("− Dependientes (10% renta de trabajo)", e["dep_dentro"], -1,
         nota="Excluyente con la de 72 UVT. Consume el tope del 40%.",
         fuente=_fuente(par, "topes.dependientes_10pct.tope_mensual_uvt",
                        "ET art. 387"))

    L._r("  [tope conjunto 40% / 1.340 UVT]", tope, 0,
         nota="Lo que exceda este tope se pierde.",
         fuente=_fuente(par, "topes.conjunto_deducciones_exentas.tope_uvt",
                        "ET art. 336 num. 3"))
    L._r("  [rechazado por el tope]", rechazado, 0,
         nota="Deducciones y rentas exentas solicitadas que el tope no dejó pasar.")
    L.tope_conjunto = tope
    L.rechazado_por_tope = rechazado

    L._r("− Dependientes (72 UVT c/u — FUERA del tope)", e["dep_fuera"], -1,
         nota="No consume el tope del 40% y no exige factura: solo acreditar "
              "la condición. Excluyente con la del 10%.",
         fuente=_fuente(par, "topes.dependientes_72uvt.uvt_por_dependiente",
                        "ET art. 336 num. 3 inciso 2, Ley 2277 de 2022 art. 7"))
    L._r("− Deducción 1% compras con factura electrónica", fe, -1,
         nota="Exige factura electrónica a tu NIT/cédula y pago electrónico.",
         fuente=_fuente(par, "topes.deduccion_1pct_factura_electronica.tope_uvt",
                        "ET art. 336 num. 5"))

    # --- 8. impuesto ---------------------------------------------------
    L.renta_liquida = renta_liquida
    L._r("= RENTA LÍQUIDA GRAVABLE", renta_liquida)

    L.impuesto = impuesto_241(renta_liquida, par)
    L._r("IMPUESTO SOBRE LA RENTA", L.impuesto, +1,
         fuente=_fuente(par, "tarifa.rangos", "ET art. 241"))

    donado = p.get("descuentos.donaciones_certificadas_rte")
    descuento = min(
        donado * par.exigir("topes.descuento_donaciones.porcentaje_descuento"),
        L.impuesto * par.exigir("topes.descuento_donaciones.tope_porcentaje_impuesto"),
    )
    L._r("− Descuento por donaciones", descuento, -1,
         nota="Solo con certificado de entidad del Régimen Tributario Especial "
              "firmado por representante legal y contador o revisor fiscal.",
         fuente=_fuente(par, "topes.descuento_donaciones.porcentaje_descuento",
                        "ET art. 257"))

    L.impuesto_neto = max(L.impuesto - descuento, 0)
    L._r("= Impuesto neto de renta", L.impuesto_neto)

    retenciones = p.get("anticipos.retenciones_practicadas")
    saldo_favor_ant = p.get("anticipos.saldo_a_favor_anio_anterior")
    L._r("− Retenciones practicadas en el año", retenciones, -1,
         nota="Lo que terceros ya le giraron a la DIAN por cuenta tuya. Se "
              "imputa al impuesto, no a la base. Suma de los certificados de "
              "retención de cada pagador.",
         fuente="ET art. 373")
    L._r("− Saldo a favor del año anterior", saldo_favor_ant, -1,
         nota="Solo si no lo pediste en devolución ni lo imputaste ya.",
         fuente="ET art. 815")

    L.saldo = L.impuesto_neto - retenciones - saldo_favor_ant
    L._r("= SALDO A PAGAR" if L.saldo >= 0 else "= SALDO A FAVOR", abs(L.saldo))

    return L


# ---------------------------------------------------------------------
# Sensibilidad — cuánto vale cada palanca, en pesos
# ---------------------------------------------------------------------

# Qué le cuesta al contribuyente activar cada palanca. La tabla se ordena
# por ahorro, pero sin esta distinción es engañosa: "donar $5.400.000 para
# ahorrar $1.350.000" aparecía como palanca al lado de "pedir un certificado
# gratis", y son cosas opuestas.
PAPEL = "papel"            # conseguir un documento. No cuesta plata
CONDICION = "condicion"    # depende de un hecho que se cumple o no
DESEMBOLSO = "desembolso"  # exige sacar plata del bolsillo


@dataclass
class Palanca:
    etiqueta: str
    ahorro_a: float
    ahorro_b: float
    solo_ruta: str | None
    nota: str
    tipo: str = PAPEL
    costo: float = 0.0        # plata que hay que desembolsar, si aplica

    @property
    def ahorro_max(self) -> float:
        return max(self.ahorro_a, self.ahorro_b)

    @property
    def neto(self) -> float:
        """Ahorro menos lo que hay que desembolsar para conseguirlo."""
        return self.ahorro_max - self.costo

    @property
    def conviene(self) -> bool:
        """Un desembolso solo conviene si el ahorro supera lo desembolsado.

        Casi nunca pasa con donaciones (descuento del 25%) ni con prepagada.
        Sí pasa con los aportes voluntarios cuando la tarifa marginal es alta,
        porque la plata no se pierde: cambia de bolsillo.
        """
        return self.tipo != DESEMBOLSO or self.neto > 0


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

    def probar(etiqueta, cambios, nota, solo_ruta=None, tipo=PAPEL, costo=0.0):
        alt = p.copia_con(**cambios)
        pa, pb = _saldo(alt, par, "A"), _saldo(alt, par, "B")
        palancas.append(
            Palanca(etiqueta, base_a - pa, base_b - pb, solo_ruta, nota, tipo, costo)
        )

    # --- dependientes ---------------------------------------------------
    # Una sola fila, no una por cada cantidad. Como el motor elige entre la
    # vía de 72 UVT y la del 10% —y la del 10% no depende del número—, con
    # frecuencia el 2º, 3º y 4º dependiente valen exactamente lo mismo que el
    # primero. Cuatro filas con la misma cifra en una tabla titulada "cuánto
    # vale cada palanca" invitan a sumarlas, y el valor marginal es cero.
    actuales = int(p.get("deducciones.dependientes"))
    max_dep = par.exigir("topes.dependientes_72uvt.maximo_dependientes")
    if actuales < max_dep:
        por_cantidad = {}
        for n in range(actuales + 1, max_dep + 1):
            alt = p.copia_con(deducciones__dependientes=n)
            por_cantidad[n] = max(base_a - _saldo(alt, par, "A"),
                                  base_b - _saldo(alt, par, "B"))
        mejor_ahorro = max(por_cantidad.values())
        # La cantidad MÍNIMA que alcanza el máximo: perseguir soportes de más
        # no aporta nada y cuesta trámites.
        suficientes = min(n for n, v in por_cantidad.items() if v == mejor_ahorro)

        # El motivo por el que sobran depende del caso, y decir el equivocado
        # es peor que no decir ninguno: de esa explicación el usuario deduce
        # qué esperar el año siguiente.
        alt = p.copia_con(deducciones__dependientes=suficientes)
        # La vía se consulta en la ruta que da el ahorro que se está
        # reportando. Mirar siempre la A daba una razón que contradecía la
        # cifra cuando ganaba la B.
        ahorro_a = base_a - _saldo(alt, par, "A")
        ruta_del_ahorro = "A" if ahorro_a >= base_b - _saldo(alt, par, "B") else "B"
        via = liquidar(alt, par, ruta_del_ahorro).dependientes_via
        if suficientes < max_dep:
            motivo = ("la vía que gana en tu caso es la del 10% de la renta de "
                      "trabajo (art. 387), que no depende de cuántos sean"
                      if "10%" in via
                      else "tu base gravable ya llegó al tramo de tarifa 0%, así "
                           "que restar más no cambia el impuesto")
            extra = f" Acreditar más de {suficientes} no agrega nada: {motivo}."
        else:
            # Con la vía de 72 UVT cada dependiente vale por separado. Quien
            # solo pueda acreditar uno necesita saber cuánto vale ESE uno, no
            # solo el total de cuatro.
            primero = por_cantidad[actuales + 1]
            extra = (f" Cada dependiente cuenta por separado: el primero vale "
                     f"{_cop(primero)} y los {suficientes - actuales} juntos, "
                     f"{_cop(mejor_ahorro)}."
                     if suficientes > actuales + 1 else "")
        probar(
            f"Acreditar {suficientes} dependiente(s) — hoy tienes {actuales}",
            {"deducciones__dependientes": suficientes},
            "FUERA del tope del 40%. No exige factura ni desembolso: se acredita "
            "la condición. Padres y hermanos con ingresos anuales < 260 UVT "
            "cuentan; hijos estudiando, hasta los 25 (Ley 2411 de 2024)." + extra,
            tipo=CONDICION,
        )

    # --- seguridad social ------------------------------------------------
    if not p.get("incrngo.aportes_obligatorios_salud_pension"):
        # base de cotización del independiente: 40% del ingreso, tarifa ~28,5%
        estimado = round(ingreso * 0.40 * 0.285)
        probar(
            f"Aportes obligatorios salud+pensión del año (~{_cop(estimado)})",
            {"incrngo__aportes_obligatorios_salud_pension": estimado},
            "Es INCRNGO, no deducción: resta ANTES del tope del 40% y no lo "
            "consume. Exige planillas PILA pagadas. Si ya cotizaste, es solo "
            "conseguir el papel; si no, es un desembolso que además cierra tu "
            "exposición ante la UGPP.",
            tipo=CONDICION,
        )

    # --- aportes voluntarios ----------------------------------------------
    if not p.get("deducciones.aportes_voluntarios"):
        techo = min(ingreso * 0.30, par.exigir("topes.aportes_voluntarios.tope_uvt") * uvt)
        probar(
            f"Aportes voluntarios AFP/AFC al tope (~{_cop(techo)})",
            {"deducciones__aportes_voluntarios": round(techo)},
            "⚠ Solo sirve si se hicieron ANTES del 31 de diciembre del año "
            "gravable. Si el año ya cerró, este número es tu costo de "
            "oportunidad para el año en curso. Es un desembolso, pero la plata "
            "no se pierde: queda en tu fondo, inmovilizada bajo las reglas de "
            "los arts. 126-1 y 126-4.",
            tipo=DESEMBOLSO, costo=round(techo),
        )

    # --- medicina prepagada -------------------------------------------------
    if not p.get("deducciones.medicina_prepagada"):
        techo = (par.exigir("topes.medicina_prepagada.tope_mensual_uvt")
                 * par.get("topes.medicina_prepagada.meses", 12) * uvt)
        probar(
            f"Medicina prepagada al tope ({_cop(techo)})",
            {"deducciones__medicina_prepagada": round(techo)},
            "Dentro del tope del 40%: en Ruta B compite contra la renta exenta y "
            "puede no agregar nada. Si YA la pagas, es solo pedir el "
            "certificado; contratarla para ahorrar impuesto casi nunca sale a "
            "cuenta.",
            tipo=DESEMBOLSO, costo=round(techo),
        )

    # --- intereses de vivienda ----------------------------------------------
    if not p.get("deducciones.intereses_vivienda"):
        techo = min(par.exigir("topes.intereses_vivienda.tope_uvt") * uvt, ingreso * 0.15)
        probar(
            f"Intereses de crédito de vivienda (~{_cop(techo)})",
            {"deducciones__intereses_vivienda": round(techo)},
            "Solo aplica si YA tienes crédito de vivienda: es pedirle el "
            "certificado al banco. Nadie se endeuda para deducir intereses.",
            tipo=CONDICION,
        )

    # --- costos, solo ruta A --------------------------------------------------
    if p.total_costos == 0:
        estimado = round(ingreso * 0.30)
        probar(
            f"Costos y gastos soportados (~{_cop(estimado)})",
            {"costos__otros": estimado},
            "SOLO RUTA A, y solo con costos que YA existen y estén soportados. "
            "Cada peso exige factura electrónica o documento soporte, y los "
            "pagos a contratistas exigen verificar sus aportes. Esto NO es una "
            "invitación a inventar gastos: si no ocurrieron, no van.",
            solo_ruta="A", tipo=CONDICION,
        )

    # --- factura electrónica ---------------------------------------------------
    if not p.get("deducciones.compras_con_factura_electronica"):
        compras = round(ingreso * 0.20)
        probar(
            f"Compras con factura electrónica a tu cédula (~{_cop(compras)})",
            {"deducciones__compras_con_factura_electronica": compras},
            "Deduce el 1%, tope 240 UVT, FUERA del tope del 40%. Sobre compras "
            "que ya hiciste: se trata de pedir la factura a tu NIT/cédula y "
            "pagar por medio electrónico, no de comprar más.",
            tipo=CONDICION,
        )

    # --- donaciones ------------------------------------------------------------
    if not p.get("descuentos.donaciones_certificadas_rte"):
        monto = round(ingreso * 0.03)
        probar(
            f"Donaciones certificadas a entidad del RTE (~{_cop(monto)})",
            {"descuentos__donaciones_certificadas_rte": monto},
            "Es DESCUENTO del 25% sobre el impuesto, no deducción. Ojo con la "
            "aritmética: donar $100 ahorra $25, así que como jugada fiscal "
            "SIEMPRE pierdes plata. Tiene sentido si ibas a donar de todas "
            "formas — y entonces lo que importa es exigir el certificado de "
            "una entidad del RTE, sin el cual la donación vale $0.",
            tipo=DESEMBOLSO, costo=monto,
        )

    # Primero lo que solo exige un papel o una condición ya cumplida, y
    # dentro de cada grupo por ahorro. Un desembolso que pierde plata en neto
    # se manda al final: se muestra para que se entienda por qué no conviene,
    # no como recomendación.
    orden = {PAPEL: 0, CONDICION: 0, DESEMBOLSO: 1}
    palancas.sort(key=lambda x: (orden[x.tipo], not x.conviene, -x.ahorro_max))
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

    # Con el perfil a medias, "NO obligado" es el titular más peligroso que
    # puede dar esta herramienta: alguien lo lee, no declara, y la sanción por
    # extemporaneidad corre. Solo se afirma si están los tres insumos que el
    # perfil sí modela; los otros dos umbrales (consumos con tarjeta y compras
    # totales) no están en el perfil y por eso el mensaje los nombra aparte.
    faltan_insumos = [
        etiqueta for valor, etiqueta in (
            (p.ingresos_brutos, "ingresos"),
            (p.patrimonio_bruto, "patrimonio bruto"),
            (consig, "consignaciones"),
        ) if not valor
    ]

    if disparadores:
        estado = "SÍ"
        detalle = "Se cumple: " + "; ".join(disparadores)
        severidad = "info"
    elif faltan_insumos:
        estado = "NO SE PUEDE AFIRMAR TODAVÍA"
        detalle = (
            f"Ningún umbral se supera con lo cargado, pero falta(n) "
            f"{', '.join(faltan_insumos)}. Con el perfil a medias esto NO "
            f"significa que no tengas que declarar. Basta con superar UNO de "
            f"los cinco umbrales —ingresos, patrimonio, consignaciones, "
            f"consumos con tarjeta de crédito o compras totales, todos de "
            f"1.400 UVT salvo patrimonio, que es 4.500— y los dos últimos ni "
            f"siquiera están en el perfil. Complétalo antes de concluir."
        )
        severidad = "media"
    else:
        estado = "NO por los datos cargados"
        detalle = (
            "Ningún umbral superado. Verifica igual tus consumos con tarjeta de "
            "crédito y tus compras totales del año: son dos umbrales de 1.400 "
            "UVT que este motor no modela y que bastan por sí solos."
        )
        severidad = "info"

    checks.append({
        "id": "OBL-01",
        "titulo": "¿Obligado a declarar renta?",
        "estado": estado,
        "detalle": detalle,
        "severidad": severidad,
        "fuente": u.get("fuente", ""),
    })

    # ¿pierde la calidad de no responsable de IVA?
    #
    # El art. 437 par. 3 num. 6 no mide "todo lo que entró": mide las
    # consignaciones PROVENIENTES DE ACTIVIDADES GRAVADAS CON IVA. Omitir ese
    # calificador convierte una advertencia útil en una alarma falsa que
    # puede empujar a alguien a inscribirse como responsable de IVA sin que
    # le corresponda.
    iva = par.get("umbrales.no_responsable_iva", {})
    tope_iva = iva.get("consignaciones_uvt", 3500) * uvt
    tope_estado = iva.get("consignaciones_uvt_contratistas_del_estado", 4000) * uvt

    calificador = (
        "El campo consignaciones_totales_anio debe traer SOLO las "
        "consignaciones provenientes de actividades gravadas con IVA. Los "
        "traslados entre cuentas propias, los préstamos y el dinero de "
        "terceros en tránsito no cuentan. Si tu actividad es exportación de "
        "servicios (art. 481 lit. c) o está excluida, esa cifra puede ser cero "
        "aunque por tus cuentas pasen cientos de millones."
    )

    if consig == 0:
        estado, sev = "SIN CUANTIFICAR", "media"
        detalle = (
            f"No has cuantificado las consignaciones gravadas del año. El umbral "
            f"es {_cop(tope_iva)} ({_cop(tope_estado)} si tus ingresos vienen de "
            f"contratos con el Estado, par. 5). Se mide sobre consignaciones y "
            f"no sobre tu ingreso propio, así que quien recibe plata de clientes "
            f"y la redistribuye puede superarlo sin que su ingreso se acerque. "
            f"{calificador}"
        )
    elif consig > tope_iva:
        estado, sev = "UMBRAL SUPERADO", "alta"
        detalle = (
            f"Consignaciones gravadas {_cop(consig)} > {_cop(tope_iva)}. Si la "
            f"cifra está bien construida, pierdes la calidad de no responsable "
            f"de IVA: inscripción, facturación, declaraciones de IVA por período "
            f"y sanción por no declarar (art. 643 ET, no el 641, si nunca las "
            f"presentaste). Antes de aceptarlo, verifica dos cosas: que no estés "
            f"contando el mismo dinero dos veces —el giro en la plataforma y su "
            f"abono en el banco son un solo hecho— y que todo lo sumado provenga "
            f"de actividad gravada. {calificador} Resuélvelo con tu contador "
            f"ANTES de presentar renta."
        )
    else:
        margen = tope_iva - consig
        estado, sev = "DENTRO DEL UMBRAL", "info"
        detalle = (f"Consignaciones gravadas {_cop(consig)}, margen de "
                   f"{_cop(margen)}. {calificador}")

    checks.append({
        "id": "R-01",
        "titulo": "Calidad de no responsable de IVA (consignaciones gravadas)",
        "estado": estado,
        "detalle": detalle,
        "severidad": sev,
        "fuente": iva.get("fuente", "ET art. 437 par. 3 num. 6"),
    })

    # ¿supera el tope indicativo de costos del art. 336-1?
    tope_ind = par.get("topes.tope_indicativo_costos.porcentaje_ingresos_brutos", 0.60)
    if p.total_costos > p.ingresos_brutos * tope_ind and p.ingresos_brutos:
        checks.append({
            "id": "R-09",
            "titulo": "Costos por encima del tope indicativo del 60%",
            "estado": f"{p.total_costos / p.ingresos_brutos:.0%} de los ingresos brutos",
            "detalle": (
                f"Los costos ({_cop(p.total_costos)}) superan el 60% de los "
                f"ingresos brutos que el art. 336-1 ET fija como tope indicativo. "
                f"Superarlo es legítimo, pero obliga a indicarlo EXPRESAMENTE en "
                f"la declaración marcando la casilla informativa; no hacerlo "
                f"acarrea la sanción del art. 651 num. 1 lit. d). Además esos "
                f"costos deben estar soportados con factura electrónica, nómina "
                f"electrónica o documento equivalente ELECTRÓNICO — lo que choca "
                f"con la estrategia de documento soporte en físico. Míralo con tu "
                f"contador antes de decidir la Ruta A."
            ),
            "severidad": "alta",
            "fuente": "ET art. 336-1, adicionado por Ley 2277 de 2022 art. 60",
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
    pagos_contratistas = p.get("costos.pagos_a_contratistas")
    if pagos_contratistas > 0 and not p.get("verificaciones.contratistas_con_pila_verificada"):
        checks.append({
            "id": "R-02",
            "titulo": "Costos por pagos a contratistas sin verificar aportes",
            "estado": "SIN VERIFICAR",
            "detalle": (
                f"Tienes {_cop(pagos_contratistas)} en pagos a contratistas. El "
                f"art. 108 par. 2 ET exige "
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
