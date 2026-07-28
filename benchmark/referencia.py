"""Implementación de REFERENCIA de la depuración — independiente del motor.

Escrita directamente desde el Estatuto Tributario, sin importar nada de
`engine/`, con estilo deliberadamente literal y sin optimizaciones. Su único
propósito es servir de segunda opinión: si `engine/depuracion.py` y este
archivo producen números distintos para el mismo caso, uno de los dos está
mal y hay que averiguar cuál.

Esto es *differential testing*. Vale más que un test que compara la salida
del motor contra una constante que salió del propio motor: para que un error
pase desapercibido tendría que aparecer idéntico en dos implementaciones
escritas por separado.

Las constantes están escritas a mano acá A PROPÓSITO. No se leen de
knowledge/parametros.toml: si ese archivo tuviera una cifra equivocada, leerla
desde ambos lados haría que el error se cancelara y el test pasara.

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
DEP_UVT = 72                      # art. 336 par. (Ley 2277/2022 art. 7)
DEP_MAX = 4
DEP_10_PCT = 0.10                 # art. 387
DEP_10_TOPE_UVT = 32 * 12
VIVIENDA_TOPE_UVT = 1_200         # art. 119
PREPAGADA_TOPE_UVT = 16 * 12      # art. 387 num. 1
VOLUNTARIOS_PCT = 0.30            # arts. 126-1 y 126-4
VOLUNTARIOS_TOPE_UVT = 3_800
GMF_PCT = 0.50                    # art. 115
FE_PCT = 0.01                     # art. 336 par. 4
FE_TOPE_UVT = 240
DONACION_PCT = 0.25               # art. 257
DONACION_TOPE_IMPUESTO_PCT = 0.25


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


def liquidar(caso: dict, ruta: str) -> dict:
    """Depuración de la cédula general. `caso` usa las mismas llaves que el
    perfil.toml del motor, aplanadas con punto."""

    def v(clave, defecto=0):
        return caso.get(clave, defecto)

    trabajo = v("ingresos.rentas_trabajo_honorarios")
    capital = v("ingresos.rentas_capital")
    otras = v("ingresos.otras_rentas_no_laborales")
    brutos = trabajo + capital + otras

    incrngo = (v("incrngo.aportes_obligatorios_salud_pension")
               + v("incrngo.componente_inflacionario")
               + v("incrngo.otros"))

    netos = brutos - incrngo

    costos = 0
    if ruta == "A":
        costos = (v("costos.pagos_a_contratistas")
                  + v("costos.comisiones_plataforma")
                  + v("costos.equipo_tecnologico")
                  + v("costos.internet_software")
                  + v("costos.arriendo_oficina")
                  + v("costos.otros"))

    gmf = v("deducciones.gmf_pagado") * GMF_PCT
    vivienda = min(v("deducciones.intereses_vivienda"), VIVIENDA_TOPE_UVT * UVT)
    prepagada = min(v("deducciones.medicina_prepagada"), PREPAGADA_TOPE_UVT * UVT)
    voluntarios = min(v("deducciones.aportes_voluntarios"),
                      brutos * VOLUNTARIOS_PCT,
                      VOLUNTARIOS_TOPE_UVT * UVT)
    dentro_fijo = gmf + vivienda + prepagada + voluntarios

    fe = min(v("deducciones.compras_con_factura_electronica") * FE_PCT,
             FE_TOPE_UVT * UVT)

    n_dep = int(v("deducciones.dependientes"))
    dep_72 = min(n_dep, DEP_MAX) * DEP_UVT * UVT
    dep_10 = 0.0
    if n_dep > 0:
        dep_10 = min(trabajo * DEP_10_PCT, DEP_10_TOPE_UVT * UVT)

    tope = max(min(netos * TOPE_CONJUNTO_PCT, TOPE_CONJUNTO_UVT * UVT), 0)

    def evaluar(extra_dentro: float, extra_fuera: float):
        deducciones = dentro_fijo + extra_dentro

        # Art. 206 num. 10 inciso 2: la base de la exención se obtiene «una
        # vez se detraiga del valor total de los pagos laborales los ingresos
        # no constitutivos de renta, las deducciones y las rentas exentas
        # diferentes a la establecida en el presente numeral».
        exenta = 0.0
        if ruta == "B":
            base = trabajo - incrngo - deducciones - extra_fuera - fe
            if base < 0:
                base = 0
            exenta = min(base * EXENTA_PCT, EXENTA_TOPE_UVT * UVT)

        solicitado = deducciones + exenta
        aplicado = min(solicitado, tope)
        rl = netos - costos - aplicado - extra_fuera - fe
        if rl < 0:
            rl = 0
        return rl, impuesto(rl), solicitado - aplicado, aplicado, exenta

    if n_dep > 0:
        via_72 = evaluar(0.0, dep_72)
        via_10 = evaluar(dep_10, 0.0)
        elegida, via = (via_72, "72") if via_72[1] <= via_10[1] else (via_10, "10")
    else:
        elegida, via = evaluar(0.0, 0.0), "sin"

    renta_liquida, imp, rechazado, aplicado, exenta = elegida

    donado = v("descuentos.donaciones_certificadas_rte")
    descuento = min(donado * DONACION_PCT, imp * DONACION_TOPE_IMPUESTO_PCT)
    neto = imp - descuento
    if neto < 0:
        neto = 0

    saldo = (neto
             - v("anticipos.retenciones_practicadas")
             - v("anticipos.saldo_a_favor_anio_anterior"))

    return {
        "ingresos_brutos": brutos,
        "ingresos_netos": netos,
        "costos": costos,
        "tope_conjunto": tope,
        "aplicado": aplicado,
        "rechazado": rechazado,
        "renta_exenta_aplicada": exenta,
        "renta_liquida": round(renta_liquida),
        "impuesto": imp,
        "descuento_donaciones": round(descuento),
        "impuesto_neto": round(neto),
        "saldo": round(saldo),
        "via_dependientes": via,
    }


def comparar(caso: dict) -> dict:
    a = liquidar(caso, "A")
    b = liquidar(caso, "B")
    return {
        "A": a,
        "B": b,
        "mejor": "A" if a["saldo"] <= b["saldo"] else "B",
        "diferencia": abs(a["saldo"] - b["saldo"]),
    }
