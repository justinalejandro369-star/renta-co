"""Oráculo estructural del formulario 210 — la octava capa.

Por qué esto es un ORÁCULO y no otro test más
─────────────────────────────────────────────
Un oráculo es una fuente de verdad EXTERNA a la implementación. Este
proyecto no tiene ninguno disponible: el Programa Ayuda Renta de la DIAN y
la declaración sugerida del Muisca exigen credenciales y no se pueden correr
en CI, y `benchmark/referencia.py` no cuenta —la ronda 7 midió que
reimplementa la misma lectura de la norma, así que 80.000 perfiles
diferenciales dieron cero divergencias con las dos implementaciones
equivocadas.

Pero hay uno gratis y nadie lo estaba usando: **las ecuaciones entre
casillas impresas en el propio formulario 210**. Son aritmética publicada
por la autoridad, no una interpretación de nadie, y son exactamente lo que
comprueba el validador del Muisca cuando el contribuyente presenta. Si las
cifras que el motor manda transcribir no las satisfacen, la declaración se
rechaza — o peor, pasa y queda descuadrada.

`renglones_al_210()` emitía cuatro casillas y no verificaba ninguna.

Qué encontró
────────────
Las cuatro casillas se aproximaban al múltiplo de mil POR SEPARADO, cada una
desde su cifra al peso. Eso rompe la cadena: quien transcribe la base y
liquida sobre ella —que es lo que el formulario hace— obtiene un impuesto
distinto del que el motor le imprime al lado. Medido sobre las 20 personas:
3 de 40 liquidaciones discrepaban en $1.000.

Poco dinero, mucho problema: es la clase de descuadre que un validador
rechaza y que el contribuyente no sabe explicar, en la única cifra de toda
la herramienta que él va a copiar a mano.

Qué NO comprueba, y hay que decirlo
───────────────────────────────────
Las identidades de acá son las de la CADENA FINAL —base → impuesto →
descuentos → neto → anticipos → saldo—. El 210 tiene alrededor de veinte
casillas más arriba (ingresos brutos, INCRNGO, costos, rentas exentas,
deducciones) que el motor todavía no emite por separado, así que su
aritmética no se puede verificar. Eso está declarado y medido, no
silenciado: `casillas_no_emitidas()` lo cuenta y el informe lo imprime.
"""

from __future__ import annotations

from engine.depuracion import aproximar_577, impuesto_241, liquidar, renglones_al_210

# Casillas de la sección de liquidación privada del 210 que el motor todavía
# NO emite por separado, así que sus ecuaciones no se pueden comprobar.
# Están listadas para que el hueco tenga tamaño: «cubre 6 de ~20» es un dato,
# «el formulario está verificado» sería falso.
NO_EMITIDAS = (
    "Ingresos brutos por rentas de trabajo",
    "Ingresos brutos por rentas de capital",
    "Ingresos brutos por rentas no laborales",
    "Ingresos no constitutivos de renta",
    "Costos y gastos procedentes",
    "Rentas exentas y deducciones imputables",
    "Rentas exentas y deducciones imputables LIMITADAS",
    "Renta líquida cedular",
    "Renta presuntiva",
    "Ganancias ocasionales gravables",
    "Impuesto de ganancias ocasionales",
    "Anticipo del año gravable siguiente",
    "Sanciones",
)


def casillas_no_emitidas() -> tuple[int, int]:
    """(emitidas, total estimado). Para que el hueco tenga tamaño."""
    return len(_ETIQUETAS), len(_ETIQUETAS) + len(NO_EMITIDAS)


_ETIQUETAS = ("Renta líquida gravable", "Impuesto sobre la renta líquida",
              "Descuentos tributarios", "Impuesto neto de renta",
              "Anticipos y retenciones", "Saldo")


def _casillas(L, par) -> dict[str, int]:
    c = dict(renglones_al_210(L, par))
    # El saldo sale con una etiqueta u otra según el signo; acá se normaliza
    # a un solo número con signo para poder escribir la ecuación.
    if "Saldo a favor" in c:
        c["Saldo"] = -c.pop("Saldo a favor")
    else:
        c["Saldo"] = c.pop("Saldo a pagar")
    return c


def correr(par, personas, construir) -> list[str]:
    """Devuelve las violaciones de las ecuaciones del 210."""
    fallos: list[str] = []
    for persona in personas:
        p = construir(persona)
        for ruta in ("A", "B"):
            L = liquidar(p, par, ruta)
            quien = f"{persona['id']}/{ruta}"
            c = _casillas(L, par)

            # (1) Art. 577: toda casilla es múltiplo de mil.
            for etiqueta, valor in c.items():
                if valor % 1000:
                    fallos.append(
                        f"{quien}: «{etiqueta}» = {valor:,} no es múltiplo de "
                        f"mil. El art. 577 lo exige para toda casilla."
                    )

            # (2) El impuesto sale de liquidar la BASE DE LA CASILLA, no la
            #     base al peso. Es la que estaba rota.
            esperado = aproximar_577(impuesto_241(c["Renta líquida gravable"], par))
            if c["Impuesto sobre la renta líquida"] != esperado:
                fallos.append(
                    f"{quien}: quien transcriba la base "
                    f"({c['Renta líquida gravable']:,}) y le aplique el art. "
                    f"241 obtiene {esperado:,}, y la casilla dice "
                    f"{c['Impuesto sobre la renta líquida']:,}. El formulario "
                    f"no reproduce su propia cuenta."
                )

            # (3) Neto = impuesto − descuentos, y nunca negativo (art. 259:
            #     los descuentos no pueden generar saldo por sí solos).
            neto = max(c["Impuesto sobre la renta líquida"]
                       - c["Descuentos tributarios"], 0)
            if c["Impuesto neto de renta"] != neto:
                fallos.append(
                    f"{quien}: impuesto neto {c['Impuesto neto de renta']:,} ≠ "
                    f"{c['Impuesto sobre la renta líquida']:,} − "
                    f"{c['Descuentos tributarios']:,}"
                )
            if c["Impuesto neto de renta"] < 0:
                fallos.append(f"{quien}: impuesto neto negativo")

            # (4) Saldo = neto − anticipos.
            saldo = c["Impuesto neto de renta"] - c["Anticipos y retenciones"]
            if c["Saldo"] != saldo:
                fallos.append(
                    f"{quien}: saldo {c['Saldo']:,} ≠ "
                    f"{c['Impuesto neto de renta']:,} − "
                    f"{c['Anticipos y retenciones']:,}"
                )

            # (5) Coherencia con la liquidación al peso. Las casillas van
            #     redondeadas, así que la tolerancia es media unidad de
            #     redondeo por cada aproximación de la cadena: cuatro.
            if abs(c["Renta líquida gravable"] - L.renta_liquida) > 500:
                fallos.append(
                    f"{quien}: la base de la casilla se separó más de $500 de "
                    f"la base al peso ({L.renta_liquida:,.0f}). El redondeo "
                    f"del art. 577 no puede mover la cifra más que eso."
                )
            if abs(c["Saldo"] - L.saldo) > 4 * 500:
                fallos.append(
                    f"{quien}: el saldo de la casilla ({c['Saldo']:,}) se "
                    f"separó de la liquidación al peso ({L.saldo:,.0f}) más de "
                    f"lo que puede explicar el redondeo de la cadena."
                )
    return fallos
