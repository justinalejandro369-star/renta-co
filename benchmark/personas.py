"""Personas del benchmark — contribuyentes ficticios, año gravable 2025.

Cubren el espacio de casos que la herramienta dice atender, más los bordes
donde suele romperse. Ninguna corresponde a una persona real.

Las llaves usan la notación con punto del perfil.toml.
"""

from __future__ import annotations

UVT = 49_799

PERSONAS: list[dict] = [

    {
        "id": "P01",
        "nombre": "Junior remoto, primer año declarando",
        "descripcion": "Un solo cliente en EE.UU., sin gastos, sin nada más. "
                       "El caso más limpio que existe.",
        "espera": "Gana Ruta B: sin costos, la exención del 25% es gratis.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 90_000_000,
        },
    },

    {
        "id": "P02",
        "nombre": "Freelance con equipo pequeño",
        "descripcion": "Subcontrata a dos personas, cotiza, tiene un dependiente.",
        "espera": "Caso central del proyecto. Ambas rutas cerca.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 200_000_000,
            "ingresos.rentas_capital": 1_500_000,
            "incrngo.aportes_obligatorios_salud_pension": 22_800_000,
            "incrngo.componente_inflacionario": 800_000,
            "costos.pagos_a_contratistas": 62_000_000,
            "costos.comisiones_plataforma": 4_000_000,
            "deducciones.gmf_pagado": 1_600_000,
            "deducciones.dependientes": 1,
            "anticipos.retenciones_practicadas": 120_000,
            "verificaciones.consignaciones_totales_anio": 215_000_000,
        },
    },

    {
        "id": "P03",
        "nombre": "Alto ingreso, tope saturado",
        "descripcion": "400 M sin costos. El tope de 1.340 UVT muerde antes "
                       "que el 40%.",
        "espera": "Se rechaza una parte grande de la renta exenta por el tope.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 400_000_000,
            "deducciones.gmf_pagado": 3_000_000,
            "deducciones.medicina_prepagada": 12_000_000,
        },
    },

    {
        "id": "P04",
        "nombre": "Por debajo del umbral de declarar",
        "descripcion": "60 M de ingreso. No supera las 1.400 UVT.",
        "espera": "El motor debe decir que NO está obligado por los datos dados.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 60_000_000,
        },
    },

    {
        "id": "P05",
        "nombre": "Riesgo de IVA por consignaciones",
        "descripcion": "Ingreso propio modesto, pero por la cuenta pasan 400 M "
                       "de clientes que redistribuye.",
        "espera": "R-01 en rojo aunque el ingreso esté muy por debajo del umbral.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 120_000_000,
            "costos.pagos_a_contratistas": 70_000_000,
            "verificaciones.consignaciones_totales_anio": 400_000_000,
        },
    },

    {
        "id": "P06",
        "nombre": "Cuatro dependientes, tope libre",
        "descripcion": "Mantiene a sus dos papás y dos hermanos.",
        "espera": "Con el tope libre debería ganar la vía del 10% sobre la de "
                  "72 UVT — el motor tiene que calcular las dos.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 180_000_000,
            "deducciones.dependientes": 4,
        },
    },

    {
        "id": "P07",
        "nombre": "Cuatro dependientes, tope saturado",
        "descripcion": "Mismo caso pero con aportes voluntarios al tope.",
        "espera": "Con el tope saturado se invierte: gana la vía de 72 UVT, "
                  "porque queda FUERA del tope.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 180_000_000,
            "deducciones.dependientes": 4,
            "deducciones.aportes_voluntarios": 54_000_000,
            "deducciones.medicina_prepagada": 9_561_408,
        },
    },

    {
        "id": "P08",
        "nombre": "Costos enormes, Ruta A dominante",
        "descripcion": "Agencia de una persona que factura y subcontrata casi todo.",
        "espera": "Gana Ruta A por mucho. Riesgo R-02 abierto.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 350_000_000,
            "costos.pagos_a_contratistas": 210_000_000,
            "costos.comisiones_plataforma": 8_000_000,
            "verificaciones.consignaciones_totales_anio": 360_000_000,
        },
    },

    {
        "id": "P09",
        "nombre": "Donante con certificado",
        "descripcion": "Dona a una entidad del RTE y sí pidió el certificado.",
        "espera": "El descuento se topa al 25% del impuesto, no al 25% del donado.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 150_000_000,
            "descuentos.donaciones_certificadas_rte": 100_000_000,
        },
    },

    {
        "id": "P10",
        "nombre": "Retenciones mayores al impuesto",
        "descripcion": "Le retuvieron más de lo que debe.",
        "espera": "Saldo a FAVOR, no a pagar. El signo tiene que salir bien.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 75_000_000,
            "anticipos.retenciones_practicadas": 8_000_000,
        },
    },

    {
        "id": "P11",
        "nombre": "Borde: exactamente en 1.090 UVT de renta líquida",
        "descripcion": "Frontera del primer tramo del art. 241.",
        "espera": "Impuesto = 0. Un peso más ya paga 19% marginal.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 1_090 * UVT,
        },
    },

    {
        "id": "P12",
        "nombre": "Borde: deducciones mayores que el ingreso",
        "descripcion": "Alguien que carga mal sus datos.",
        "espera": "Renta líquida 0, impuesto 0, sin números negativos.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 50_000_000,
            "costos.otros": 200_000_000,
            "deducciones.medicina_prepagada": 50_000_000,
            "deducciones.dependientes": 4,
        },
    },

    {
        "id": "P13",
        "nombre": "Solo patrimonio, sin ingresos",
        "descripcion": "Año sabático. Vivió de ahorros.",
        "espera": "Impuesto 0, pero obligado a declarar por patrimonio si "
                  "supera 4.500 UVT.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 0,
            "ingresos.rentas_capital": 2_000_000,
        },
        "patrimonio": [("Ahorros", 300_000_000)],
        "pasivos": [("Crédito de vehículo", 48_000_000),
                    ("Tarjeta de crédito a 31-dic", 6_500_000)],
    },

    {
        "id": "P14",
        "nombre": "Tramo alto del art. 241",
        "descripcion": "Consultor senior, 900 M al año.",
        "espera": "Cae en el tramo del 37% o 39%. Verifica los adicionales.",
        "datos": {
            "ingresos.rentas_trabajo_honorarios": 900_000_000,
            "incrngo.aportes_obligatorios_salud_pension": 60_000_000,
            "deducciones.aportes_voluntarios": 189_236_200,
        },
    },
]


# --- Anclas calculadas A MANO con la norma, no con ninguna de las dos
#     implementaciones. Si el motor y la referencia coinciden pero ambos
#     se apartan de esto, el error está en los dos.
ANCLAS = [
    {
        "id": "P11",
        "ruta": "B",
        "campo": "impuesto",
        "esperado": 0,
        "razon": "1.090 UVT es el techo del tramo a tarifa 0% del art. 241. "
                 "En Ruta B la renta líquida baja aún más por la exención, "
                 "así que sigue en 0.",
    },
    {
        "id": "P11",
        "ruta": "A",
        "campo": "renta_liquida",
        "esperado": 1_090 * UVT,
        "razon": "Sin costos ni deducciones, la renta líquida es el ingreso: "
                 "1.090 × 49.799 = 54.280.910.",
    },
    {
        "id": "P01",
        "ruta": "A",
        "campo": "impuesto",
        "esperado": 7_272_360,
        "razon": "Base 90.000.000 = 1.807,265206 UVT. Tramo 1.700–4.100 al 28% "
                 "con 116 UVT adicionales: (1.807,265206 − 1.700) × 0,28 + 116 "
                 "= 146,034258 UVT × 49.799 = 7.272.360.",
    },
    {
        "id": "P01",
        "ruta": "B",
        "campo": "renta_liquida",
        "esperado": 67_500_000,
        "razon": "Sin INCRNGO ni deducciones, la base de la exención es el "
                 "ingreso: 25% de 90.000.000 = 22.500.000. Queda por debajo "
                 "del tope anual de 790 UVT (39.341.210) y del tope conjunto "
                 "(40% de 90 M = 36 M). 90 M − 22,5 M = 67,5 M.",
    },
    {
        "id": "P03",
        "ruta": "B",
        "campo": "renta_liquida",
        "esperado": 349_597_382,
        "razon": "Fija las dos correcciones del art. 206 num. 10 a la vez. "
                 "Deducciones: GMF 3.000.000 × 50% = 1.500.000, más prepagada "
                 "capada en 192 UVT = 9.561.408, total 11.061.408. Base de la "
                 "exención = 400.000.000 − 11.061.408 = 388.938.592 (inciso 2: "
                 "se detraen las deducciones, no es el 25% del bruto). El 25% "
                 "de eso son 97.234.648, pero el tope ANUAL de 790 UVT lo "
                 "recorta a 39.341.210 — con el tope derogado de 240 UVT/mes "
                 "habrían pasado los 97 M completos. Solicitado 11.061.408 + "
                 "39.341.210 = 50.402.618, por debajo del tope conjunto de "
                 "66.730.660, así que se aplica entero. "
                 "400.000.000 − 50.402.618 = 349.597.382.",
    },
    {
        "id": "P06",
        "ruta": "A",
        "campo": "via_dependientes",
        "esperado": "10",
        "razon": "Con 180 M de renta de trabajo y el tope libre: la vía del 10% "
                 "da min(18.000.000; 384 UVT = 19.122.816) = 18.000.000, contra "
                 "4 × 72 UVT = 14.342.112 de la otra. Gana el 10%.",
    },
    {
        "id": "P07",
        "ruta": "A",
        "campo": "via_dependientes",
        "esperado": "72",
        "razon": "Con el tope saturado por los aportes voluntarios, la vía del "
                 "10% no agrega nada porque cae dentro del tope. Las 72 UVT "
                 "quedan fuera, así que restan completas.",
    },
]
