"""Implementación de REFERENCIA de la depuración — independiente del motor.

Escrita directamente desde el Estatuto Tributario, sin importar nada de
`engine/`. Su único propósito es ser una segunda opinión: si esto y
`engine/depuracion.py` producen números distintos para el mismo caso, uno de
los dos está mal y hay que averiguar cuál.

POR QUÉ ESTÁ ESCRITA COMO ESTÁ
──────────────────────────────
Este archivo ya falló una vez, y de la forma en que fallan las segundas
opiniones: se escribió reproduciendo la misma estructura y el mismo
malentendido que el motor, así que la capa diferencial encontró dos
implementaciones de acuerdo — y equivocadas — sobre el tope de la renta
exenta. El error solo lo atrapó un ancla calculada a mano.

Para que sea de verdad una segunda opinión y no una transcripción, acá:

1. **Las constantes están escritas a mano**, no leídas de
   `knowledge/parametros.toml`. Leerlas de ahí haría que una cifra
   equivocada en ese archivo se cancelara entre ambas implementaciones.

2. **La estructura de control es distinta.** El motor evalúa dos
   combinaciones de dependientes con una función interna que recibe los dos
   montos. Acá se ENUMERAN escenarios completos como diccionarios y se
   liquida cada uno de principio a fin con la misma rutina lineal. Es más
   lento y más verboso a propósito: un error de estructura en un lado no
   tiene cómo aparecer igual en el otro.

3. **La depuración es secuencial y literal**, en el orden en que la lee el
   art. 336: ingresos, INCRNGO, costos o exención, deducciones, tope, y
   deducciones fuera del tope.

Fuente de cada constante: Estatuto Tributario, año gravable 2025.
"""

from __future__ import annotations

# --- Constantes AG2025, transcritas a mano desde la norma ---------------
UVT = 49_799                      # Res. DIAN 000193 de 2024

# Art. 241 ET — (desde UVT, hasta UVT o None, tarifa, UVT adicionales)
TARIFA_241 = [
    (0,      1_090,  0.00,      0),
    (1_090,  1_700,  0.19,      0),
    (1_700,  4_100,  0.28,    116),
    (4_100,  8_670,  0.33,    788),
    (8_670, 18_970,  0.35,  2_296),
    (18_970, 31_000, 0.37,  5_901),
    (31_000, None,   0.39, 10_352),
]

TOPE_CONJUNTO_PCT = 0.40          # art. 336 num. 3
TOPE_CONJUNTO_UVT = 1_340         # art. 336 num. 3
EXENTA_PCT = 0.25                 # art. 206 num. 10
# 790 UVT ANUALES. La Ley 2277 de 2022 art. 2 reemplazó el límite mensual de
# 240 UVT (Ley 1607 de 2012) por este. El texto viejo sigue circulando en
# blogs de contadores y sobreestima la exención en 3,6 veces.
EXENTA_TOPE_UVT = 790
DEP_UVT = 72                      # art. 336 num. 3 inciso 2 (Ley 2277/2022 art. 7)
DEP_MAX = 4
DEP_10_PCT = 0.10                 # art. 387
DEP_10_TOPE_UVT = 32 * 12
VIVIENDA_TOPE_UVT = 1_200         # art. 119
PREPAGADA_TOPE_UVT = 16 * 12      # art. 387 inciso 2 lit. a) y b)
VOLUNTARIOS_PCT = 0.30            # arts. 126-1 y 126-4
VOLUNTARIOS_TOPE_UVT = 3_800
GMF_PCT = 0.50                    # art. 115
FE_PCT = 0.01                     # art. 336 num. 5
FE_TOPE_UVT = 240
DONACION_PCT = 0.25               # art. 257
DONACION_TOPE_IMPUESTO_PCT = 0.25 # art. 258


def impuesto(base_pesos: float) -> int:
    """Art. 241 ET. Escrito de la forma más literal posible."""
    if base_pesos <= 0:
        return 0
    base_uvt = base_pesos / UVT
    for desde, hasta, tarifa, adicional in TARIFA_241:
        if hasta is None or base_uvt <= hasta:
            en_uvt = (base_uvt - desde) * tarifa + adicional
            if en_uvt < 0:
                en_uvt = 0
            return round(en_uvt * UVT)
    return 0


def _topar(valor: float, tope: float) -> float:
    return valor if valor < tope else tope


def _liquidar_escenario(c: dict, ruta: str, escenario: dict) -> dict:
    """Depuración completa, de arriba abajo, para UN escenario ya fijado.

    `escenario` dice cuánto de dependientes va dentro del tope conjunto y
    cuánto queda fuera. Acá no se decide nada: se liquida lo que llega.
    """
    def v(clave):
        return c.get(clave, 0)

    # 1. Ingresos de la cédula general.
    trabajo = v("ingresos.rentas_trabajo_honorarios")
    ingresos = (trabajo
                + v("ingresos.rentas_capital")
                + v("ingresos.otras_rentas_no_laborales"))

    # 2. Ingresos no constitutivos de renta.
    incrngo = (v("incrngo.aportes_obligatorios_salud_pension")
               + v("incrngo.componente_inflacionario")
               + v("incrngo.otros"))
    netos = ingresos - incrngo

    # 3. Costos y gastos — solo en la ruta que los eligió.
    #
    #    Y topados POR TIPO DE RENTA: el Decreto 1625 art. 1.2.1.20.5 inciso
    #    final no deja que el costo de un tipo se reste de otro. Se escribe
    #    acá otra vez, de arriba abajo, para que el diferencial pueda ver una
    #    diferencia con el motor: si esta implementación llamara a la del
    #    motor, comparar las dos no probaría nada.
    if ruta == "A":
        campos = ("pagos_a_contratistas", "comisiones_plataforma",
                  "equipo_tecnologico", "internet_software",
                  "arriendo_oficina", "otros")
        atribucion = c.get("costos.atribucion", {}) or {}

        # Techo de cada tipo: sus ingresos menos sus INCRNGO.
        techo = {
            "rentas_trabajo_honorarios":
                trabajo - v("incrngo.aportes_obligatorios_salud_pension"),
            "rentas_capital":
                v("ingresos.rentas_capital") - v("incrngo.componente_inflacionario"),
            "otras_rentas_no_laborales":
                v("ingresos.otras_rentas_no_laborales"),
        }
        # `incrngo.otros` no tiene tipo propio: solo se imputa cuando hay un
        # único tipo con ingresos.
        con_ingresos = [t for t in techo if v(f"ingresos.{t}") > 0]
        if len(con_ingresos) == 1:
            techo[con_ingresos[0]] -= v("incrngo.otros")
        for t in techo:
            if techo[t] < 0:
                techo[t] = 0.0

        # Atribución por defecto: la única ACTIVIDAD con ingresos. La renta
        # de capital no es una actividad.
        actividad = [t for t in ("rentas_trabajo_honorarios",
                                 "otras_rentas_no_laborales")
                     if v(f"ingresos.{t}") > 0]
        if len(actividad) == 1:
            defecto = actividad[0]
        elif actividad:
            defecto = None
        else:
            defecto = con_ingresos[0] if len(con_ingresos) == 1 else None

        pedido = {t: 0.0 for t in techo}
        costos = 0.0                       # lo que no se pudo atribuir no se topa
        for campo in campos:
            monto = v(f"costos.{campo}")
            if not monto:
                continue
            tipo = atribucion.get(campo) or defecto
            if tipo in pedido:
                pedido[tipo] += monto
            else:
                costos += monto
        for t, monto in pedido.items():
            costos += monto if monto < techo[t] else techo[t]
    else:
        costos = 0

    # 4. Deducciones con tope individual.
    deducciones = 0.0
    deducciones += v("deducciones.gmf_pagado") * GMF_PCT
    deducciones += _topar(v("deducciones.intereses_vivienda"), VIVIENDA_TOPE_UVT * UVT)
    deducciones += _topar(v("deducciones.medicina_prepagada"), PREPAGADA_TOPE_UVT * UVT)
    voluntarios = v("deducciones.aportes_voluntarios")
    voluntarios = _topar(voluntarios, ingresos * VOLUNTARIOS_PCT)
    voluntarios = _topar(voluntarios, VOLUNTARIOS_TOPE_UVT * UVT)
    deducciones += voluntarios
    deducciones += escenario["dependientes_dentro"]

    # 5. Deducciones que quedan FUERA del tope conjunto.
    fuera = escenario["dependientes_fuera"]
    fuera += _topar(v("deducciones.compras_con_factura_electronica") * FE_PCT,
                    FE_TOPE_UVT * UVT)

    # 6. Renta exenta del 25%, solo en la ruta B.
    #    Art. 206 num. 10 inciso 2: se calcula «una vez se detraiga del valor
    #    total de los pagos laborales los ingresos no constitutivos de renta,
    #    las deducciones y las rentas exentas diferentes a la establecida en
    #    el presente numeral».
    if ruta == "B":
        base_exenta = trabajo - incrngo - deducciones - fuera
        if base_exenta < 0:
            base_exenta = 0
        exenta = _topar(base_exenta * EXENTA_PCT, EXENTA_TOPE_UVT * UVT)
    else:
        exenta = 0.0

    # 7. Tope conjunto del art. 336 num. 3.
    tope = _topar(netos * TOPE_CONJUNTO_PCT, TOPE_CONJUNTO_UVT * UVT)
    if tope < 0:
        tope = 0.0
    solicitado = deducciones + exenta
    aplicado = _topar(solicitado, tope)

    # 8. Renta líquida gravable.
    renta_liquida = netos - costos - aplicado - fuera
    if renta_liquida < 0:
        renta_liquida = 0.0

    # 9. Impuesto y descuentos.
    imp = impuesto(renta_liquida)
    descuento = _topar(
        v("descuentos.donaciones_certificadas_rte") * DONACION_PCT,
        imp * DONACION_TOPE_IMPUESTO_PCT,
    )
    neto = imp - descuento
    if neto < 0:
        neto = 0.0

    saldo = (neto
             - v("anticipos.retenciones_practicadas")
             - v("anticipos.saldo_a_favor_anio_anterior"))

    return {
        "ingresos_brutos": ingresos,
        "ingresos_netos": netos,
        "costos": costos,
        "renta_exenta_aplicada": exenta,
        "tope_conjunto": tope,
        "aplicado": aplicado,
        "rechazado": solicitado - aplicado,
        "renta_liquida": round(renta_liquida),
        "impuesto": imp,
        "descuento_donaciones": round(descuento),
        "impuesto_neto": round(neto),
        "saldo": round(saldo),
        "via_dependientes": escenario["via"],
    }


def _escenarios(c: dict) -> list[dict]:
    """Las combinaciones de dependientes que la norma permite.

    La exclusividad es POR DEPENDIENTE: el Decreto 1625 art. 1.2.1.20.3 dice
    «un mismo dependiente solo dará lugar a una de estas dos deducciones».
    No dice que el contribuyente tenga que escoger una sola.

    Así que hay tres combinaciones, no dos:

      · 72 UVT (art. 336 num. 3 inciso 2, fuera del tope) por hasta 4;
      · el 10% de la renta de trabajo (art. 387, dentro del tope) por uno —
        esa deducción no depende de cuántos sean, así que gastar más de un
        dependiente en ella es tirarlos;
      · el 10% por uno Y 72 UVT por cada uno de los demás, que es la que
        casi siempre gana cuando el tope conjunto no está saturado.

    Se enumeran como escenarios completos y después se elige; el motor lo
    resuelve con otra estructura.
    """
    n = int(c.get("deducciones.dependientes", 0))
    if n <= 0:
        return [{"via": "sin", "dependientes_dentro": 0.0, "dependientes_fuera": 0.0}]

    trabajo = c.get("ingresos.rentas_trabajo_honorarios", 0)
    por_72 = min(n, DEP_MAX) * DEP_UVT * UVT
    por_10 = _topar(trabajo * DEP_10_PCT, DEP_10_TOPE_UVT * UVT)
    # Las 72 UVT que quedan cuando uno de los dependientes se gasta en el 10%.
    resto_72 = min(n - 1, DEP_MAX) * DEP_UVT * UVT

    # Las dos vías aplican ÚNICAMENTE sobre rentas de trabajo: el art. 336
    # num. 3 inciso 2 dice «el TRABAJADOR podrá deducir» y el Decreto 1625
    # art. 1.2.1.20.3 es explícito.
    if trabajo <= 0:
        por_72 = resto_72 = 0.0

    escenarios = [
        {"via": "72", "dependientes_dentro": 0.0, "dependientes_fuera": por_72},
    ]
    if resto_72 > 0:
        escenarios.append(
            {"via": "mixto", "dependientes_dentro": por_10,
             "dependientes_fuera": resto_72}
        )
    else:
        escenarios.append(
            {"via": "10", "dependientes_dentro": por_10, "dependientes_fuera": 0.0}
        )
    return escenarios


def liquidar(caso: dict, ruta: str) -> dict:
    """Liquida todos los escenarios y devuelve el de menor impuesto."""
    resultados = [_liquidar_escenario(caso, ruta, e) for e in _escenarios(caso)]
    # Lexicográfico: menor impuesto y, empatando, menor base declarada. Con
    # la clave sobre el impuesto a secas el empate lo resolvía el orden de la
    # lista, y esta referencia tenía los escenarios EN EL MISMO ORDEN que el
    # motor. Por eso el diferencial daba cero divergencias sobre 80.000
    # perfiles con las dos implementaciones equivocadas: la independencia era
    # aritmética, no de criterio. Es el resultado que midieron Knight y
    # Leveson en 1986 y que este archivo ya reprodujo dos veces.
    return min(resultados, key=lambda r: (r["impuesto"], r["renta_liquida"]))


def comparar(caso: dict) -> dict:
    a = liquidar(caso, "A")
    b = liquidar(caso, "B")
    return {
        "A": a,
        "B": b,
        "mejor": "A" if a["saldo"] <= b["saldo"] else "B",
        "diferencia": abs(a["saldo"] - b["saldo"]),
    }
