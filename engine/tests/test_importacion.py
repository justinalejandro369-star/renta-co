"""Tests de la capa de importación: montos, signo y filas ilegibles.

Por qué existe este archivo
───────────────────────────
La ronda 5 midió 28 de 49 mutaciones detectadas y dio veredicto de NO LISTO.
El núcleo tributario estaba bien; lo que rodea al núcleo podía producir el
número equivocado en silencio. Tres hallazgos de confianza ALTA vivían acá:

  · `parse_monto` decidiendo el caso ambiguo con una constante del adaptador
    (`sep_decimal="."`), o sea un factor de mil según quién leyera el archivo.
  · `_clasificar` de Deel ignorando el signo, y metiendo pagos SALIENTES como
    `ingreso_trabajo` — un ingreso negativo que RESTA de la base gravable.
  · Una celda mala abortando el archivo entero, o saltándose en silencio.

Los tres se escriben acá contra la CLASE, no contra el caso: la lección de
cinco rondas es que la aserción escrita para el caso recién arreglado no
atrapa al hermano de al lado.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from engine import adapters
from engine.adapters import bancolombia, deel, generico, wise
from engine.adapters.generico import (convencion_de_fecha,
                                      convencion_del_archivo, parse_monto)


def csv_temporal(nombre: str, contenido: str) -> Path:
    ruta = Path(tempfile.mkdtemp()) / nombre
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


# ---------------------------------------------------------------------
# 1. El ×1000, contra la clase
# ---------------------------------------------------------------------

def formatear(valor: float, sep_miles: str, sep_dec: str, decimales: int) -> str:
    """Escribe un monto en una convención dada. Oráculo independiente.

    No usa nada del motor: compone la cadena a mano desde el entero y la
    fracción, que es lo que hace una hoja de cálculo al exportar.
    """
    negativo = valor < 0
    v = abs(valor)
    entero = int(v)
    fraccion = round((v - entero) * (10 ** decimales))
    if fraccion >= 10 ** decimales:      # el redondeo se llevó una unidad
        entero += 1
        fraccion = 0
    texto = f"{entero:,}".replace(",", "\x00").replace("\x00", sep_miles)
    if decimales:
        texto += sep_dec + str(fraccion).zfill(decimales)
    return ("-" if negativo else "") + texto


CONVENCIONES = [
    (".", ",", 0),   # colombiana sin centavos:  1.234.567
    (".", ",", 2),   # colombiana con centavos:  1.234.567,89
    (",", ".", 0),   # anglosajona sin centavos: 1,234,567
    (",", ".", 2),   # anglosajona con centavos: 1,234,567.89
    ("", ".", 2),    # sin separador de miles:   1234567.89
    ("", "", 0),     # entero pelado:            1234567
]

# Magnitudes reales de un extracto: desde una comisión de mil pesos hasta un
# giro de cien millones, pasando por TODO lo que cae bajo el millón, que es
# la forma donde vive la ambigüedad.
VALORES = [
    1_234, 8_500, 12_500, 54_937, 82_000, 150_000, 500_000, 897_681,
    1_000_000, 1_234_567, 2_500_000, 12_345_678, 100_000_000,
    1_234.56, 82_000.50, 150_000.99, 3_800.00, 12_500.75,
]


class TestMontoRoundTrip(unittest.TestCase):
    """La propiedad que cierra la clase, no el caso.

    Si un archivo PRUEBA su convención —y todo archivo real de más de dos
    filas la prueba—, entonces cada monto tiene que volver exactamente al
    número que lo generó. Un factor de mil en cualquier fila rompe esto.
    """

    def test_todo_monto_vuelve_a_su_valor_en_toda_convencion(self):
        for sep_miles, sep_dec, decimales in CONVENCIONES:
            valores = [v for v in VALORES if decimales or v == int(v)]
            textos = [formatear(v, sep_miles, sep_dec, decimales) for v in valores]
            sep, _ = convencion_del_archivo(textos)
            for esperado, texto in zip(valores, textos):
                for moneda in ("COP", "USD"):
                    obtenido = parse_monto(texto, sep, moneda)
                    self.assertAlmostEqual(
                        obtenido, esperado, places=2,
                        msg=(f"{texto!r} en convención miles={sep_miles!r} "
                             f"dec={sep_dec!r} moneda={moneda} dio {obtenido}, "
                             f"se esperaba {esperado}"),
                    )

    def test_ningun_monto_se_desvia_por_un_factor_de_mil(self):
        """El error específico que apareció dos veces en el historial.

        Se afirma aparte del round-trip porque un fallo de ×1000 es el único
        que produce un número creíble: 82.000 en vez de 82.000.000 pasa
        cualquier revisión de vista.
        """
        for sep_miles, sep_dec, decimales in CONVENCIONES:
            valores = [v for v in VALORES if decimales or v == int(v)]
            textos = [formatear(v, sep_miles, sep_dec, decimales) for v in valores]
            sep, _ = convencion_del_archivo(textos)
            for esperado, texto in zip(valores, textos):
                obtenido = parse_monto(texto, sep, "COP")
                for factor in (1000, 0.001):
                    self.assertNotAlmostEqual(
                        obtenido, esperado * factor, places=2,
                        msg=f"{texto!r} salió con factor {factor} ({obtenido})",
                    )


class TestConvencionDelArchivo(unittest.TestCase):
    """La señal que la ronda 5 encontró sin usar: el archivo completo."""

    def test_una_fila_con_dos_separadores_prueba_que_son_miles(self):
        """'2,500,000' en el mismo archivo dice que '150,000' son 150 mil.

        Este es el caso reproducido de Bancolombia: '150,000' salía 150
        mientras '2,500,000' salía bien. Corrupción PARCIAL dentro del mismo
        archivo, que ningún cuadre de totales detecta.
        """
        sep, _ = convencion_del_archivo(["2,500,000", "150,000"])
        self.assertIsNone(sep)
        self.assertEqual(parse_monto("150,000", sep, "COP"), 150_000)

    def test_una_fila_con_dos_decimales_prueba_el_separador_decimal(self):
        sep, avisos = convencion_del_archivo(["3800.00", "150.000"])
        self.assertEqual(sep, ".")
        self.assertEqual(parse_monto("150.000", sep, "USD"), 150.0)
        self.assertTrue(any("DECIMALES" in a for a in avisos),
                        "una lectura de ×1000 no puede ser silenciosa")

    def test_un_archivo_sin_evidencia_avisa_en_vez_de_callar(self):
        sep, avisos = convencion_del_archivo(["82.000", "3.500"])
        self.assertIsNone(sep)
        self.assertTrue(any("MILES" in a for a in avisos))

    def test_convenciones_contradictorias_no_inventan_una(self):
        sep, avisos = convencion_del_archivo(["1.234,56", "1,234.56"])
        self.assertIsNone(sep)
        self.assertTrue(avisos)

    def test_los_tokens_malformados_no_votan(self):
        """'1.2.3' no es un monto y no puede decidir la convención del archivo."""
        sep, _ = convencion_del_archivo(["1.2.3", "3800.00"])
        self.assertEqual(sep, ".")


class TestBandaDeMoneda(unittest.TestCase):
    """Un movimiento en pesos de '1,234' no son un peso con veintitrés
    centavos. Es la misma idea que TRM_MINIMA/TRM_MAXIMA en trm.py."""

    def test_en_pesos_el_caso_ambiguo_es_siempre_de_miles(self):
        for texto, esperado in (("150,000", 150_000), ("150.000", 150_000),
                                ("1.234", 1_234), ("82.000", 82_000)):
            for pista in (None, ".", ","):
                self.assertEqual(
                    parse_monto(texto, pista, "COP"), esperado,
                    f"{texto!r} con pista {pista!r} no dio {esperado}",
                )

    def test_en_moneda_extranjera_la_pista_del_archivo_sigue_mandando(self):
        """No se extiende la banda a todo: 1.234 USD es una comisión real."""
        self.assertEqual(parse_monto("1.234", ".", "USD"), 1.234)
        self.assertEqual(parse_monto("1.234", None, "USD"), 1_234)

    def test_la_estructura_sigue_ganandole_a_la_moneda(self):
        """'0.500' y '12500.750' son decimales por forma, en cualquier moneda."""
        for moneda in ("COP", "USD", None):
            self.assertEqual(parse_monto("0.500", ".", moneda), 0.5)
            self.assertEqual(parse_monto("12500.750", ".", moneda), 12500.75)


class TestCerosDeRelleno(unittest.TestCase):
    """La excepción con el predicado demasiado ancho, del historial.

    `entero == "0"` distingue el cero SOLO —que sí delata un decimal, porque
    ningún grupo de miles empieza en cero— de un cero de RELLENO, que los
    extractos traen. Escrito como `startswith("0")`, "054.937" se leía como
    55 pesos: un factor de mil, y en la dirección que hace que el número se
    vea razonable.

    Ninguna aserción lo cubría porque los montos de prueba no tenían ceros
    de relleno, que es exactamente la forma del dato real.
    """

    def test_un_cero_de_relleno_no_convierte_el_monto_en_decimal(self):
        for texto, esperado in (("054.937", 54_937), ("0054.937", 54_937),
                                ("007.500", 7_500), ("0123.456", 123_456)):
            for pista in (None, ".", ","):
                for moneda in ("COP", "USD", None):
                    self.assertEqual(
                        parse_monto(texto, pista, moneda), esperado,
                        f"{texto!r} con pista {pista!r} y moneda {moneda} "
                        f"no dio {esperado}",
                    )

    def test_el_cero_solo_si_delata_un_decimal(self):
        """Nadie escribe quinientos como '0.500'."""
        self.assertEqual(parse_monto("0.500", None, "USD"), 0.5)
        self.assertEqual(parse_monto("0,500", None, "USD"), 0.5)

    def test_un_archivo_con_ceros_de_relleno_no_prueba_una_convencion_falsa(self):
        """'054.937' no puede votar como si el punto fuera decimal: si lo
        hiciera, contaminaría la lectura del resto del archivo."""
        sep, _ = convencion_del_archivo(["054.937", "150.000", "2.500.000"])
        self.assertIsNone(sep)
        self.assertEqual(parse_monto("150.000", sep, "COP"), 150_000)


class TestNingunAdaptadorSuponeLaConvencion(unittest.TestCase):
    """La causa raíz: una constante del adaptador decidiendo el factor de mil.

    Se prueba por comportamiento y en los CUATRO adaptadores, no en el que se
    acaba de tocar. Cinco de cinco rondas encontraron que el arreglo aplicado
    a un solo archivo hermano es el hallazgo más grave de la siguiente.
    """

    def test_deel_no_divide_por_mil_un_export_reguardado_desde_excel(self):
        ruta = csv_temporal("deel-marzo.csv",
                            "Date,Type,Amount,Currency,Counterparty,Description\n"
                            "2025-03-14,invoice,82.000,USD,Cliente,Payment received\n"
                            "2025-04-14,invoice,55.500,USD,Cliente,Payment received\n")
        movs = deel.importar(ruta)
        self.assertEqual([m.monto_origen for m in movs], [82_000, 55_500])

    def test_wise_no_divide_por_mil_un_extracto_en_pesos(self):
        ruta = csv_temporal("wise-statement.csv",
                            "Date,Amount,Currency,Description\n"
                            "2025-03-14,4.500.000,COP,Received money from Cliente\n"
                            "2025-03-20,150.000,COP,Received money from Cliente\n")
        movs = wise.importar(ruta)
        self.assertEqual([m.monto_origen for m in movs], [4_500_000, 150_000])

    def test_bancolombia_lee_igual_las_filas_grandes_y_las_pequenas(self):
        ruta = csv_temporal("bancolombia.csv",
                            "Fecha,Descripcion,Valor,Documento\n"
                            "14/03/2025,ABONO,\"2,500,000\",1\n"
                            "15/03/2025,PAGO,\"150,000\",2\n")
        movs = bancolombia.importar(ruta)
        self.assertEqual([m.monto_origen for m in movs], [2_500_000, 150_000])

    def test_generico_hace_lo_mismo(self):
        ruta = csv_temporal("otro-banco.csv",
                            "fecha,descripcion,valor\n"
                            "14/03/2025,ABONO,2.500.000\n"
                            "15/03/2025,PAGO,150.000\n")
        movs = generico.importar(ruta)
        self.assertEqual([m.monto_origen for m in movs], [2_500_000, 150_000])


# ---------------------------------------------------------------------
# 2. El signo
# ---------------------------------------------------------------------

# Las 30 descripciones típicas de un export de Deel, con la categoría que
# les corresponde. Las cuatro que el reordenamiento de la ronda 4 rompió van
# marcadas: son pagos SALIENTES cuyo texto trae una palabra de ingreso.
CASOS_DEEL = [
    # (tipo, descripción, monto, categoría esperada)
    ("invoice", "Invoice #001 paid by client", 5000, "ingreso_trabajo"),
    ("payment", "Payment received from Acme", 4000, "ingreso_trabajo"),
    ("invoice", "Invoice #002, platform fee deducted", 3800, "ingreso_trabajo"),
    ("payment", "Contract payment for March", 4200, "ingreso_trabajo"),
    ("payment", "Payment from Cliente SAS", 3000, "ingreso_trabajo"),
    ("salary", "Salary March", 2500, "ingreso_trabajo"),
    ("milestone", "Milestone 3 released", 1500, "ingreso_trabajo"),
    ("bonus", "Bonus for Q1", 800, "ingreso_trabajo"),
    ("payment", "Pago recibido de cliente", 2000, "ingreso_trabajo"),
    ("withdrawal", "Withdraw to bank account", -3000, "traslado"),
    ("withdrawal", "Retiro a cuenta Bancolombia", -2000, "traslado"),
    ("payout", "Payout to bank", -1800, "traslado"),
    ("transfer", "Bank transfer out", -1200, "traslado"),
    ("transfer", "Transfer to bank", -900, "traslado"),
    ("transfer", "Internal transfer USD to COP", -500, "traslado"),
    ("transfer", "Balance transfer", -400, "traslado"),
    ("transfer", "Move funds to COP balance", -300, "traslado"),
    ("transfer", "Transferencia interna", -250, "traslado"),
    ("payment", "Payment to contractor Ana", -1000, "costo_contratista"),
    ("payment", "Contractor payment October", -1100, "costo_contratista"),
    ("payment", "Pago a proveedor", -700, "costo"),
    ("payout", "Payout to contractor Luis", -650, "costo_contratista"),
    ("fee", "Platform fee", -100, "costo"),
    ("fee", "Service charge", -50, "costo"),
    ("fee", "Wise charged a fee", -40, "costo"),
    ("fee", "Transfer fee", -30, "costo"),
    ("fee", "Comision de la plataforma", -20, "costo"),
    # Los cuatro que abrió el reordenamiento de la ronda 4: texto de ingreso,
    # dinero que SALE. Los pagos a terceros son COSTO —que es lo correcto, no
    # solo 'no ingreso'— desde que las reglas de salida van antes que las de
    # ingreso; el retiro es un traslado.
    ("payment", "Payment to contractor for milestone 2", -1000, "costo_contratista"),
    ("payment", "Payment to Juan - salary March", -900, "costo"),
    ("payment", "Bonus payment to contractor Ana", -600, "costo_contratista"),
    # Un retiro es un traslado aunque su descripción traiga el número de la
    # factura que lo originó. Antes salía `ingreso_trabajo` —el dinero ya
    # contado como ingreso, contado otra vez— y el arreglo por signo lo
    # dejaba en `desconocido`, que era mejor pero seguía sin ser correcto.
    ("withdrawal", "Withdrawal - invoice #002 payout", -1500, "traslado"),
]


class TestSignoEnLaClasificacion(unittest.TestCase):
    def test_las_treinta_descripciones_tipicas_de_deel(self):
        malas = [
            (desc, esperada, deel._clasificar(tipo, desc, monto))
            for tipo, desc, monto, esperada in CASOS_DEEL
            if deel._clasificar(tipo, desc, monto) != esperada
        ]
        self.assertEqual(malas, [], f"{len(malas)} de {len(CASOS_DEEL)} mal clasificadas")

    def test_ninguna_categoria_de_ingreso_acepta_un_monto_negativo(self):
        """La CLASE, en los tres adaptadores que clasifican por texto.

        Un ingreso no puede ser una salida de dinero. Da igual qué diga la
        descripción: si el texto y el signo se contradicen, va a revisión
        manual, que es lo único que no produce un número equivocado.
        """
        for modulo, llamar in (
            (deel, lambda d, m: deel._clasificar("", d, m)),
            (wise, lambda d, m: wise._clasificar(d, m)),
            (bancolombia, lambda d, m: bancolombia._clasificar(d, m)),
        ):
            for palabras, categoria in modulo.REGLAS:
                if categoria not in {"ingreso_trabajo", "ingreso_capital"}:
                    continue
                for palabra in palabras:
                    self.assertNotIn(
                        llamar(palabra, -1000),
                        {"ingreso_trabajo", "ingreso_capital"},
                        f"{modulo.NOMBRE}: {palabra!r} en negativo entró como ingreso",
                    )

    def test_el_campo_type_le_gana_a_la_descripcion(self):
        """`Type` lo escribe Deel; la descripción la escribe una persona.
        Un `Withdrawal` cuya descripción solo dice "Invoice INV-001" es el
        retiro del dinero que YA se contó como ingreso: contarlo otra vez
        duplica la base, y no hay signo que lo delate porque un reporte de
        payouts trae los montos en positivo."""
        for tipo in ("Withdrawal", "withdraw", "Retiro", "Cash out"):
            self.assertEqual(
                deel._clasificar(tipo, "Invoice INV-001", 9800),
                "traslado",
                f"Type={tipo!r} no le ganó a la palabra 'invoice'",
            )
        for tipo in ("Exchange", "Conversion"):
            self.assertEqual(deel._clasificar(tipo, "Salary March", 9800), "traslado")

    def test_pero_un_type_ambiguo_deja_decidir_a_la_descripcion(self):
        """`Payout` en Deel es tanto "payout to your bank" (traslado) como
        "payout to contractor" (costo). No puede imponer nada."""
        self.assertEqual(
            deel._clasificar("Payout", "Payout to contractor Luis", -650),
            "costo_contratista")
        self.assertEqual(
            deel._clasificar("Payout", "Milestone 2 payout to your bank", 9800),
            "traslado")

    def test_bancolombia_no_manda_a_retencion_cualquier_mencion(self):
        """`retencion` como subcadena se llevaba a este renglón un pago a
        proveedor y una ReteICA. Y esta categoría no resta de la base: resta
        del IMPUESTO, peso por peso, contra un renglón que la DIAN cruza con
        los certificados de cada agente retenedor."""
        for desc, esperada in (
            ("RETENCION EN LA FUENTE", "retencion"),
            ("RTE FTE HONORARIOS", "retencion"),
            ("RETEFUENTE MARZO", "retencion"),
            ("PAGO A PROVEEDOR RETENCION APLICADA", "desconocido"),
            ("PAGO PSE RETENCION ICA", "desconocido"),
            ("TRASLADO RETENCION ICA MUNICIPIO", "desconocido"),
        ):
            self.assertEqual(
                bancolombia._clasificar(desc, -1_000_000), esperada,
                f"{desc!r} se clasificó mal",
            )

    def test_wise_no_cuenta_como_ingreso_fondear_tu_propia_cuenta(self):
        """Wise escribe "Received money from <tu nombre> ... top up" cuando
        te fondeas desde tu banco. En positivo, así que ningún veto de signo
        lo toca, y contar un traslado como ingreso duplica la base."""
        self.assertEqual(
            wise._clasificar("Received money from Justin Diaz with reference top up",
                             3000),
            "traslado")

    def test_pero_un_pago_de_cliente_convertido_sigue_siendo_ingreso(self):
        """El arreglo anterior no puede tragarse el caso de la ronda 2."""
        self.assertEqual(
            wise._clasificar("Received money from Cliente SAS, converted to COP", 5000),
            "ingreso_trabajo")

    def test_el_mismo_texto_en_positivo_sigue_siendo_ingreso(self):
        """El veto del signo no puede tragarse los ingresos de verdad."""
        for modulo, llamar in (
            (deel, lambda d, m: deel._clasificar("", d, m)),
            (wise, lambda d, m: wise._clasificar(d, m)),
            (bancolombia, lambda d, m: bancolombia._clasificar(d, m)),
        ):
            for palabras, categoria in modulo.REGLAS:
                if categoria not in {"ingreso_trabajo", "ingreso_capital"}:
                    continue
                for palabra in palabras:
                    self.assertEqual(
                        llamar(palabra, 1000), categoria,
                        f"{modulo.NOMBRE}: {palabra!r} en positivo dejó de ser {categoria}",
                    )


class TestAvisosDeSigno(unittest.TestCase):
    """La segunda mitad del hallazgo del signo.

    Aunque la clasificación falle, el ledger tiene que notarlo. Antes solo
    miraba costos y retenciones, así que un ingreso negativo neteaba en
    silencio: 10.000.000 + (−3.000.000) = 7.000.000 y `validar()` devolvía
    lista vacía.
    """

    def _ledger(self, categoria, *montos):
        from datetime import date

        from engine.ledger import Ledger, Movimiento

        return Ledger([
            Movimiento(date(2025, 3, i + 1), "mov", monto, "COP", categoria)
            for i, monto in enumerate(montos)
        ]).convertir(None)

    def test_toda_categoria_con_signo_esperado_avisa_cuando_va_al_reves(self):
        from engine.ledger import Ledger

        for categoria, (signo, _, _) in Ledger.SIGNO_ESPERADO.items():
            ledger = self._ledger(categoria, 10_000_000 * signo, -3_000_000 * signo)
            self.assertTrue(
                ledger.avisos_de_signo(),
                f"{categoria}: un movimiento con el signo contrario no avisó",
            )

    def test_el_aviso_no_se_dispara_cuando_todo_va_en_el_sentido_correcto(self):
        from engine.ledger import Ledger

        for categoria, (signo, _, _) in Ledger.SIGNO_ESPERADO.items():
            ledger = self._ledger(categoria, 10_000_000 * signo, 5_000_000 * signo)
            self.assertEqual(
                ledger.avisos_de_signo(), [],
                f"{categoria}: avisó sin que hubiera signos mezclados",
            )

    def test_un_ingreso_negativo_no_pasa_callado_por_validar(self):
        ledger = self._ledger("ingreso_trabajo", 10_000_000, -3_000_000)
        self.assertEqual(ledger.total("ingreso_trabajo"), 7_000_000)
        self.assertTrue(any("NEGATIVO" in a for a in ledger.validar()))


# ---------------------------------------------------------------------
# 3. Las filas que no se pueden leer
# ---------------------------------------------------------------------

class TestMoneda(unittest.TestCase):
    """La segunda ambigüedad que el proyecto no había atacado.

    El separador decimal se resolvió deduciéndolo del archivo. La moneda
    seguía resolviéndose con constantes del adaptador, que es exactamente el
    patrón que causó el ×1000 — solo que acá el factor es la TRM, o sea
    ~4.000.
    """

    def test_bancolombia_lee_la_columna_de_moneda_si_existe(self):
        """Bancolombia tiene cuentas en dólares y de compensación. La moneda
        estaba cableada a COP: 20.000 USD entraban como 20.000 pesos."""
        ruta = csv_temporal("extracto-usd.csv",
                            "Fecha,Documento,Descripcion,Moneda,Valor\n"
                            "15/03/2025,001,ABONO EXTERIOR,USD,20000.00\n")
        movs = bancolombia.importar(ruta)
        self.assertEqual(movs[0].moneda, "USD")

    def test_sin_columna_de_moneda_bancolombia_sigue_siendo_pesos(self):
        ruta = csv_temporal("extracto.csv",
                            "Fecha,Documento,Descripcion,Valor\n"
                            "15/03/2025,001,ABONO,2.500.000\n")
        self.assertEqual(bancolombia.importar(ruta)[0].moneda, "COP")

    def test_una_celda_de_moneda_vacia_es_fila_ilegible_y_no_el_defecto(self):
        """`(fila.get(c_moneda) or "USD")` convertía 23.000.000 COP en
        23.000.000 USD por una celda en blanco, en una sola fila del archivo:
        corrupción parcial que ningún cuadre de totales detecta."""
        ruta = csv_temporal("deel.csv",
                            "Payment ID,Fecha,Tipo,Moneda,Monto,Cliente\n"
                            "P-001,2025-03-15,Pago recibido,COP,15.000.000,A\n"
                            "P-002,2025-06-16,Pago recibido,,23.000.000,B\n")
        avisos: list[str] = []
        movs = deel.importar(ruta, avisos=avisos)
        self.assertEqual(len(movs), 1)
        self.assertEqual(movs[0].moneda, "COP")
        self.assertTrue(any("moneda" in a for a in avisos), avisos)

    def test_una_moneda_que_no_es_iso_tampoco_se_supone(self):
        """Con TODAS las filas ilegibles se lanza, que es lo correcto: no hay
        nada que importar y un ledger vacío parecería un año sin ingresos."""
        ruta = csv_temporal("deel.csv",
                            "Date,Type,Amount,Currency,Description\n"
                            "2025-03-14,invoice,3800.00,dólares,Payment received\n")
        with self.assertRaises(ValueError) as ctx:
            deel.importar(ruta)
        self.assertIn("moneda", str(ctx.exception))

    def test_una_fila_con_moneda_mala_entre_buenas_se_salta_y_se_cuenta(self):
        ruta = csv_temporal("deel.csv",
                            "Date,Type,Amount,Currency,Description\n"
                            "2025-03-14,invoice,3800.00,USD,Payment received\n"
                            "2025-04-14,invoice,3800.00,dólares,Payment received\n")
        avisos: list[str] = []
        movs = deel.importar(ruta, avisos=avisos)
        self.assertEqual(len(movs), 1)
        self.assertTrue(any("no se pudieron leer" in a for a in avisos), avisos)


class TestConvencionDeFecha(unittest.TestCase):
    """La tercera ambigüedad. Mover un movimiento de mes le cambia la TRM y,
    en la frontera del año, lo saca del año gravable."""

    def test_un_dia_mayor_que_doce_prueba_la_convencion(self):
        self.assertEqual(convencion_de_fecha(["01/05/2025", "01/13/2025"])[0], "mdy")
        self.assertEqual(convencion_de_fecha(["01/05/2025", "13/01/2025"])[0], "dmy")

    def test_un_archivo_en_mm_dd_se_lee_en_mm_dd(self):
        ruta = csv_temporal("payoneer.csv",
                            "Date,Description,Currency,Amount\n"
                            "01/05/2025,Payment from ACME,USD,5000.00\n"
                            "01/13/2025,Payment from ACME,USD,5000.00\n"
                            "03/09/2025,Payment from ACME,USD,5000.00\n")
        avisos: list[str] = []
        movs = generico.importar(ruta, avisos=avisos)
        self.assertEqual([m.fecha.isoformat() for m in movs],
                         ["2025-01-05", "2025-01-13", "2025-03-09"])
        self.assertTrue(any("mm/dd" in a for a in avisos), avisos)

    def test_un_archivo_colombiano_sigue_leyendose_dd_mm(self):
        ruta = csv_temporal("banco.csv",
                            "fecha,descripcion,valor\n"
                            "05/01/2025,PAGO,1.500.000\n"
                            "13/01/2025,PAGO,2.500.000\n")
        movs = generico.importar(ruta)
        self.assertEqual([m.fecha.isoformat() for m in movs],
                         ["2025-01-05", "2025-01-13"])

    def test_un_archivo_indecidible_avisa(self):
        _, avisos = convencion_de_fecha(["01/05/2025", "02/06/2025"])
        self.assertTrue(any("ambiguas" in a for a in avisos), avisos)

    def test_convenciones_contradictorias_no_inventan_una(self):
        conv, avisos = convencion_de_fecha(["13/01/2025", "01/13/2025"])
        self.assertIsNone(conv)
        self.assertTrue(avisos)


class TestCodificaciones(unittest.TestCase):
    """latin-1 acepta cualquier byte, así que nunca falla y el respaldo con
    `errors="replace"` es inalcanzable. Eso no es código muerto inofensivo:
    significa que un utf-8 corrupto se lee SIN ERROR como mojibake y entra
    al ledger con las descripciones rotas — que son justo lo que usan las
    reglas de clasificación."""

    def test_un_extracto_en_latin1_conserva_sus_tildes(self):
        ruta = Path(tempfile.mkdtemp()) / "banco.csv"
        ruta.write_bytes(
            "fecha,descripcion,valor\n14/03/2025,RETENCIÓN,1.500.000\n"
            .encode("latin-1")
        )
        movs = generico.importar(ruta)
        self.assertIn("RETENCIÓN", movs[0].descripcion)

    def test_un_utf8_doble_codificado_avisa_en_vez_de_entrar_como_mojibake(self):
        """El caso que de verdad pasa: un utf-8 leído como latin-1 y vuelto
        a guardar como utf-8. El archivo es utf-8 VÁLIDO, decodifica sin un
        solo error, y dice "RETENCIÃ³N"."""
        ruta = Path(tempfile.mkdtemp()) / "banco.csv"
        crudo = "fecha,descripcion,valor\n14/03/2025,RETENCIÓN,1.500.000\n"
        doble = crudo.encode("utf-8").decode("latin-1").encode("utf-8")
        ruta.write_bytes(doble)
        avisos: list[str] = []
        movs = generico.importar(ruta, avisos=avisos)
        self.assertTrue(any("caracteres rotos" in a for a in avisos), avisos)
        # Y aun así se importa: el monto está bien, lo roto es la descripción.
        self.assertEqual(movs[0].monto_origen, 1_500_000)

    def test_un_archivo_sano_no_produce_falsas_alarmas(self):
        """El detector de mojibake no puede gritar sobre texto normal."""
        ruta = Path(tempfile.mkdtemp()) / "banco.csv"
        ruta.write_text(
            "fecha,descripcion,valor\n"
            "14/03/2025,RETENCIÓN Y GRAVAMEN — señor Muñoz,1.500.000\n",
            encoding="utf-8",
        )
        avisos: list[str] = []
        generico.importar(ruta, avisos=avisos)
        self.assertEqual(avisos, [])


class TestFilasIlegibles(unittest.TestCase):
    """Una celda mala en la fila 200 abortaba el archivo entero y borraba
    doce meses de ingreso. Saltarla es lo correcto; saltarla callado no."""

    def test_una_fila_mala_no_bota_el_resto_del_archivo(self):
        ruta = csv_temporal("extracto.csv",
                            "fecha,descripcion,valor\n"
                            "14/03/2025,uno,1.500.000\n"
                            "15/03/2025,dos,basura\n"
                            "16/03/2025,tres,2.500.000\n")
        avisos: list[str] = []
        movs = generico.importar(ruta, avisos=avisos)
        self.assertEqual(len(movs), 2)
        self.assertEqual(sum(m.monto_origen for m in movs), 4_000_000)

    def test_la_fila_saltada_se_reporta_con_su_numero_de_linea(self):
        ruta = csv_temporal("extracto.csv",
                            "fecha,descripcion,valor\n"
                            "14/03/2025,uno,1.500.000\n"
                            "15/03/2025,dos,basura\n")
        avisos: list[str] = []
        generico.importar(ruta, avisos=avisos)
        self.assertTrue(avisos, "una fila perdida no puede ser silenciosa")
        texto = " ".join(avisos)
        self.assertIn("línea 3", texto)
        self.assertIn("NO están en el ledger", texto)

    def test_un_archivo_entero_ilegible_si_es_error(self):
        ruta = csv_temporal("extracto.csv",
                            "fecha,descripcion,valor\n"
                            "14/03/2025,uno,basura\n"
                            "15/03/2025,dos,masbasura\n")
        with self.assertRaises(ValueError):
            generico.importar(ruta)

    def test_los_avisos_llegan_al_que_llama_al_despachador(self):
        """`adapters.importar` es lo que usa el CLI: si los avisos se quedan
        adentro, el usuario no ve nada y el exit code es 0."""
        ruta = csv_temporal("deel.csv",
                            "Date,Type,Amount,Currency,Description\n"
                            "2025-03-14,invoice,3800.00,USD,Payment received\n"
                            "2025-03-15,invoice,basura,USD,Payment received\n")
        avisos: list[str] = []
        movs, nombre = adapters.importar(ruta, avisos=avisos)
        self.assertEqual(len(movs), 1)
        self.assertTrue(any("no se pudieron leer" in a for a in avisos), avisos)


if __name__ == "__main__":
    unittest.main()
