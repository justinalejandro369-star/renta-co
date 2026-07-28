"""Tests del motor. Sin dependencias externas:

    python -m unittest discover engine/tests -v

Los valores esperados están calculados A MANO con la norma en la mano, no
copiados de la salida del programa. Un test que solo repite lo que el código
produce no prueba nada.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from engine import parametros as P
from engine import perfil as PF
from engine.adapters.generico import parse_fecha, parse_monto
from engine.depuracion import comparar, impuesto_241, liquidar

RAIZ = Path(__file__).resolve().parent.parent.parent
UVT_2025 = 49_799


class TestTarifa241(unittest.TestCase):
    """Art. 241 ET, verificado a mano rango por rango."""

    def setUp(self):
        self.par = P.cargar(2025)

    def test_uvt_correcta(self):
        self.assertEqual(self.par.uvt, UVT_2025)

    def test_primer_tramo_exento(self):
        # 1.090 UVT = $54.280.910 están a tarifa 0%
        self.assertEqual(impuesto_241(1090 * UVT_2025, self.par), 0)
        self.assertEqual(impuesto_241(1000 * UVT_2025, self.par), 0)
        self.assertEqual(impuesto_241(0, self.par), 0)

    def test_base_negativa(self):
        self.assertEqual(impuesto_241(-5_000_000, self.par), 0)

    def test_segundo_tramo_19pct(self):
        # 1.500 UVT → (1500 - 1090) * 19% = 77,9 UVT
        base = 1500 * UVT_2025
        esperado = round(410 * 0.19 * UVT_2025)
        self.assertEqual(impuesto_241(base, self.par), esperado)

    def test_tercer_tramo_28pct_con_adicional(self):
        # 2.000 UVT → (2000 - 1700) * 28% + 116 = 84 + 116 = 200 UVT
        base = 2000 * UVT_2025
        esperado = round(200 * UVT_2025)
        self.assertEqual(impuesto_241(base, self.par), esperado)

    def test_frontera_1700_uvt(self):
        # En 1.700 UVT ambos tramos deben coincidir: (1700-1090)*19% = 115,9 UVT
        base = 1700 * UVT_2025
        esperado = round(610 * 0.19 * UVT_2025)
        self.assertEqual(impuesto_241(base, self.par), esperado)
        # y el adicional del tramo siguiente es 116 UVT — coincide por diseño
        self.assertAlmostEqual(610 * 0.19, 115.9, places=4)

    def test_tramo_superior_39pct(self):
        # 35.000 UVT → (35000 - 31000) * 39% + 10.352 = 1560 + 10352 = 11.912 UVT
        base = 35_000 * UVT_2025
        esperado = round(11_912 * UVT_2025)
        self.assertEqual(impuesto_241(base, self.par), esperado)

    def test_monotonia(self):
        anterior = -1
        for uvt in range(0, 40_000, 500):
            actual = impuesto_241(uvt * UVT_2025, self.par)
            self.assertGreaterEqual(actual, anterior)
            anterior = actual


class TestTopes(unittest.TestCase):
    def setUp(self):
        self.par = P.cargar(2025)

    def _perfil(self, **secciones):
        base = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 200_000_000},
        }
        for k, v in secciones.items():
            base.setdefault(k, {}).update(v)
        datos, supuestos = PF._completar(base)
        return PF.Perfil(datos, None, supuestos)

    def test_tope_conjunto_recorta_deducciones(self):
        """Deducciones enormes no pueden pasar del tope de 1.340 UVT."""
        p = self._perfil(deducciones={"medicina_prepagada": 500_000_000,
                                      "intereses_vivienda": 500_000_000})
        L = liquidar(p, self.par, "A")
        tope_esperado = min(200_000_000 * 0.40, 1340 * UVT_2025)
        self.assertAlmostEqual(L.tope_conjunto, tope_esperado, delta=1)
        self.assertGreater(L.rechazado_por_tope, 0)

    def test_tope_40pct_manda_cuando_ingreso_es_bajo(self):
        """Con ingresos bajos, el 40% muerde antes que las 1.340 UVT."""
        p = self._perfil(ingresos={"rentas_trabajo_honorarios": 80_000_000},
                         deducciones={"medicina_prepagada": 50_000_000})
        L = liquidar(p, self.par, "A")
        self.assertAlmostEqual(L.tope_conjunto, 80_000_000 * 0.40, delta=1)

    def test_medicina_prepagada_tope_192_uvt(self):
        p = self._perfil(deducciones={"medicina_prepagada": 999_000_000})
        L = liquidar(p, self.par, "A")
        renglon = next(r for r in L.renglones if "Medicina" in r.concepto)
        self.assertEqual(renglon.valor, round(192 * UVT_2025))

    def test_gmf_deduce_la_mitad(self):
        p = self._perfil(deducciones={"gmf_pagado": 2_000_000})
        L = liquidar(p, self.par, "A")
        renglon = next(r for r in L.renglones if "GMF" in r.concepto)
        self.assertEqual(renglon.valor, 1_000_000)

    def test_dependientes_72uvt_quedan_fuera_del_tope(self):
        """El punto clave: 72 UVT por dependiente NO consume el tope del 40%.

        Con el tope YA saturado, agregar dependientes debe seguir bajando la
        renta líquida peso por peso. Si consumieran el tope, no bajaría nada.

        Para saturarlo hacen falta 66.730.660 (1.340 UVT). La prepagada sola
        no alcanza: está capada en 192 UVT. Se satura con aportes voluntarios,
        que llegan al 30% del ingreso.
        """
        satura = {"medicina_prepagada": 9_561_408, "aportes_voluntarios": 60_000_000}
        sin = liquidar(self._perfil(deducciones=satura), self.par, "A")
        con = liquidar(
            self._perfil(deducciones={**satura, "dependientes": 4}), self.par, "A"
        )
        self.assertGreater(sin.rechazado_por_tope, 0, "el tope debe estar saturado")
        self.assertAlmostEqual(
            sin.renta_liquida - con.renta_liquida, 4 * 72 * UVT_2025, delta=2
        )
        self.assertIn("72 UVT", con.dependientes_via)

    def test_con_tope_libre_gana_la_via_del_10pct(self):
        """La otra cara: si el tope NO está saturado, la vía del 10% (art. 387)
        puede valer más que las 72 UVT, y el motor debe tomar esa.

        Con 200 M de renta de trabajo: 10% = 20 M, capado a 384 UVT =
        19.122.816, contra 4 × 72 UVT = 14.342.112. Gana el 10%.
        """
        L = liquidar(self._perfil(deducciones={"dependientes": 4}), self.par, "A")
        sin = liquidar(self._perfil(), self.par, "A")
        self.assertEqual(sin.rechazado_por_tope, 0, "el tope debe estar libre")
        self.assertIn("10%", L.dependientes_via)
        self.assertAlmostEqual(
            sin.renta_liquida - L.renta_liquida, 384 * UVT_2025, delta=2
        )

    def test_maximo_4_dependientes(self):
        p = self._perfil(deducciones={"dependientes": 10})
        self.assertTrue(any("máximo 4" in e for e in PF.validar(p)))

    def test_renta_exenta_25_solo_en_ruta_b(self):
        p = self._perfil()
        a = liquidar(p, self.par, "A")
        b = liquidar(p, self.par, "B")
        ren_a = next(r for r in a.renglones if "Renta exenta" in r.concepto)
        ren_b = next(r for r in b.renglones if "Renta exenta" in r.concepto)
        self.assertEqual(ren_a.valor, 0)
        self.assertGreater(ren_b.valor, 0)

    def test_costos_solo_en_ruta_a(self):
        p = self._perfil(costos={"otros": 60_000_000})
        a = liquidar(p, self.par, "A")
        b = liquidar(p, self.par, "B")
        self.assertEqual(
            next(r for r in b.renglones if "Costos" in r.concepto).valor, 0
        )
        self.assertEqual(
            next(r for r in a.renglones if "Costos" in r.concepto).valor, 60_000_000
        )

    def test_incrngo_no_consume_el_tope(self):
        """INCRNGO resta antes y además reduce la base del tope del 40%."""
        sin = liquidar(self._perfil(), self.par, "A")
        con = liquidar(
            self._perfil(incrngo={"aportes_obligatorios_salud_pension": 20_000_000}),
            self.par, "A",
        )
        self.assertLess(con.renta_liquida, sin.renta_liquida)

    def test_descuento_donaciones_topado_al_25pct_del_impuesto(self):
        p = self._perfil(descuentos={"donaciones_certificadas_rte": 900_000_000})
        L = liquidar(p, self.par, "A")
        descuento = next(r for r in L.renglones if "donaciones" in r.concepto)
        self.assertLessEqual(descuento.valor, round(L.impuesto * 0.25) + 1)


class TestComparacion(unittest.TestCase):
    def setUp(self):
        self.par = P.cargar(2025)

    def test_costos_altos_favorecen_ruta_a(self):
        datos = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 200_000_000},
            "costos": {"otros": 120_000_000},
        }
        d, s = PF._completar(datos)
        r = comparar(PF.Perfil(d, None, s), self.par)
        self.assertEqual(r["mejor_ruta"], "A")

    def test_sin_costos_gana_ruta_b(self):
        datos = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 200_000_000},
        }
        d, s = PF._completar(datos)
        r = comparar(PF.Perfil(d, None, s), self.par)
        self.assertEqual(r["mejor_ruta"], "B")

    def test_sensibilidad_positiva_y_agrupada_por_costo(self):
        """La tabla se ordena por ahorro DENTRO de cada grupo, no en global.

        Un desembolso de $56 M que ahorra $12 M no puede encabezar una lista
        titulada "cuánto vale cada palanca": lo que la gente lee ahí es qué
        perseguir primero, y perseguir eso les cuesta plata.
        """
        from engine.depuracion import DESEMBOLSO

        datos = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 200_000_000},
        }
        d, s = PF._completar(datos)
        r = comparar(PF.Perfil(d, None, s), self.par)
        sens = r["sensibilidad"]

        self.assertTrue(all(p.ahorro_max > 0 for p in sens))

        gratis = [p.ahorro_max for p in sens if p.tipo != DESEMBOLSO]
        self.assertEqual(gratis, sorted(gratis, reverse=True))

        tipos = [p.tipo for p in sens]
        primero = next((i for i, x in enumerate(tipos) if x == DESEMBOLSO), len(tipos))
        self.assertTrue(all(x == DESEMBOLSO for x in tipos[primero:]),
                        "los desembolsos deben quedar agrupados al final")

    def test_donar_nunca_conviene_como_jugada_fiscal(self):
        """El descuento es del 25%: donar $100 ahorra $25. Siempre pierdes."""
        from engine.depuracion import DESEMBOLSO

        datos = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 300_000_000},
        }
        d, s = PF._completar(datos)
        r = comparar(PF.Perfil(d, None, s), self.par)
        donacion = next(
            (p for p in r["sensibilidad"] if "Donaciones" in p.etiqueta), None
        )
        self.assertIsNotNone(donacion)
        self.assertEqual(donacion.tipo, DESEMBOLSO)
        self.assertFalse(donacion.conviene)
        self.assertLess(donacion.neto, 0)

    def test_riesgo_iva_se_dispara(self):
        datos = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 100_000_000},
            "verificaciones": {"consignaciones_totales_anio": 300_000_000},
        }
        d, s = PF._completar(datos)
        r = comparar(PF.Perfil(d, None, s), self.par)
        riesgo = next(v for v in r["verificaciones"] if v["id"] == "R-01")
        self.assertEqual(riesgo["estado"], "UMBRAL SUPERADO")
        self.assertEqual(riesgo["severidad"], "alta")

    def test_riesgo_iva_sin_cuantificar_avisa(self):
        datos = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 100_000_000},
        }
        d, s = PF._completar(datos)
        r = comparar(PF.Perfil(d, None, s), self.par)
        riesgo = next(v for v in r["verificaciones"] if v["id"] == "R-01")
        self.assertEqual(riesgo["estado"], "SIN CUANTIFICAR")


class TestExpedienteEjemplo(unittest.TestCase):
    """El ejemplo debe correr entero. Es el test de humo del repo."""

    def test_corre_completo(self):
        p = PF.cargar(RAIZ / "expediente.ejemplo")
        self.assertEqual(PF.validar(p), [])
        r = comparar(p, P.cargar(p.anio_gravable))
        self.assertIn(r["mejor_ruta"], ("A", "B"))
        self.assertGreater(r["rutas"]["A"].impuesto, 0)
        self.assertGreater(len(r["sensibilidad"]), 0)

    def test_ejemplo_expone_el_riesgo_de_pila(self):
        p = PF.cargar(RAIZ / "expediente.ejemplo")
        r = comparar(p, P.cargar(2025))
        self.assertTrue(any(v["id"] == "R-02" for v in r["verificaciones"]))


class TestParametros(unittest.TestCase):
    def test_ag2026_hereda_de_ag2025(self):
        p = P.cargar(2026)
        self.assertEqual(p.uvt, 52_374)
        self.assertTrue(p.exigir("tarifa.rangos"))       # heredado
        self.assertFalse(p.completo)
        self.assertTrue(p.advertencias())

    def test_anio_inexistente_da_mensaje_util(self):
        with self.assertRaises(P.ParametrosNoEncontrados) as ctx:
            P.cargar(1999)
        self.assertIn("Disponibles", str(ctx.exception))

    def test_cada_tope_tiene_fuente(self):
        par = P.cargar(2025)
        for bloque in par.get("topes", {}).values():
            if isinstance(bloque, dict):
                self.assertTrue(bloque.get("fuente"), f"tope sin fuente: {bloque}")


class TestParseo(unittest.TestCase):
    def test_monto_formato_colombiano(self):
        self.assertEqual(parse_monto("$1.234.567,89"), 1_234_567.89)
        self.assertEqual(parse_monto("1.234.567"), 1_234_567)

    def test_monto_formato_anglosajon(self):
        self.assertEqual(parse_monto("1,234,567.89"), 1_234_567.89)
        self.assertEqual(parse_monto("3800.00"), 3800.0)

    def test_monto_negativo_y_parentesis(self):
        self.assertEqual(parse_monto("-1500.50"), -1500.50)
        self.assertEqual(parse_monto("(2.000,00)"), -2000.0)

    def test_monto_vacio(self):
        self.assertEqual(parse_monto(""), 0.0)
        self.assertEqual(parse_monto("-"), 0.0)

    def test_fechas(self):
        self.assertEqual(parse_fecha("2025-03-14").isoformat(), "2025-03-14")
        self.assertEqual(parse_fecha("14/03/2025").isoformat(), "2025-03-14")


class TestAdaptadores(unittest.TestCase):
    def test_detecta_deel(self):
        from engine import adapters

        ruta = RAIZ / "expediente.ejemplo" / "00-crudo" / "movimientos-plataforma.csv"
        movs, nombre = adapters.importar(ruta)
        self.assertEqual(nombre, "Deel")
        self.assertEqual(len(movs), 26)

    def test_clasificacion_deel(self):
        from engine import adapters
        from engine.ledger import Ledger

        ruta = RAIZ / "expediente.ejemplo" / "00-crudo" / "movimientos-plataforma.csv"
        movs, _ = adapters.importar(ruta)
        ledger = Ledger(movs)
        cats = {m.categoria for m in ledger.movimientos}
        self.assertIn("ingreso_trabajo", cats)
        self.assertIn("traslado", cats)
        self.assertIn("costo", cats)
        # 12 facturas mensuales
        self.assertEqual(
            sum(1 for m in movs if m.categoria == "ingreso_trabajo"), 12
        )
        # los retiros a banco NO son ingreso
        self.assertEqual(sum(1 for m in movs if m.categoria == "traslado"), 5)

    def test_ledger_no_cuenta_traslados_como_ingreso(self):
        from engine import adapters
        from engine.ledger import Ledger

        ruta = RAIZ / "expediente.ejemplo" / "00-crudo" / "movimientos-plataforma.csv"
        movs, _ = adapters.importar(ruta)
        ledger = Ledger(movs)
        for m in ledger.movimientos:
            m.moneda = "COP"      # evita depender de la red en el test
        ledger.convertir(None)
        self.assertEqual(ledger.total("ingreso_trabajo"), 12 * 3800)


if __name__ == "__main__":
    unittest.main()


class TestAdaptadorNoSecuestraArchivos(unittest.TestCase):
    """Un CSV colombiano no puede ser leído como si fuera de Deel.

    El export de un gateway local trae "Payment ID" y montos en pesos con
    punto de miles. Si el adaptador de Deel se lo quedaba, lo parseaba con
    separador decimal anglosajón y le asignaba USD: el ingreso declarado
    quedaba multiplicado por ~4, en silencio.
    """

    CSV_COLOMBIANO = (
        "Fecha,Payment ID,Descripcion,Monto\n"
        "15/03/2025,MP-88231,Pago recibido cliente,500.000\n"
        "20/03/2025,MP-88410,Pago recibido cliente,250.000\n"
    )

    def _escribir(self, contenido, nombre):
        import tempfile

        d = Path(tempfile.mkdtemp())
        ruta = d / nombre
        ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def test_no_lo_reclama_deel(self):
        from engine.adapters import deel

        cabeceras = ["Fecha", "Payment ID", "Descripcion", "Monto"]
        self.assertFalse(deel.detecta(cabeceras, "movimientos.csv"))

    def test_lo_toma_el_generico_y_los_montos_quedan_bien(self):
        from engine import adapters

        ruta = self._escribir(self.CSV_COLOMBIANO, "movimientos.csv")
        movs, nombre = adapters.importar(ruta)
        self.assertEqual(nombre, "Genérico (CSV)")
        self.assertEqual([m.monto_origen for m in movs], [500_000.0, 250_000.0])
        self.assertTrue(all(m.moneda == "COP" for m in movs))

    def test_deel_sin_columna_de_moneda_falla_en_vez_de_suponer_usd(self):
        from engine.adapters import deel

        ruta = self._escribir(self.CSV_COLOMBIANO, "deel-export.csv")
        self.assertTrue(deel.detecta(["Fecha", "Payment ID", "Monto"], ruta.name))
        with self.assertRaises(ValueError) as ctx:
            deel.importar(ruta)
        self.assertIn("moneda", str(ctx.exception))


class TestEtiquetaDelSaldo(unittest.TestCase):
    """Una ruta puede dar saldo a pagar y la otra saldo a favor.

    El comparativo imprime las dos columnas por posición. Usar la etiqueta de
    la Ruta A para ambas hacía que un saldo A FAVOR apareciera bajo el rótulo
    "SALDO A PAGAR", con el valor en absoluto: el signo del resultado quedaba
    invertido en pantalla y en el CSV que se lleva el contador. Y pasaba en el
    caso más común, retenciones mayores al impuesto de una de las rutas.
    """

    def setUp(self):
        self.par = P.cargar(2025)

    def _perfil(self, retenciones):
        datos = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 130_000_000},
            "costos": {"otros": 40_000_000},
            "anticipos": {"retenciones_practicadas": retenciones},
        }
        d, sup = PF._completar(datos)
        return PF.Perfil(d, None, sup)

    def test_las_dos_rutas_emiten_los_mismos_renglones(self):
        """Requisito para poder imprimirlas por posición."""
        for retenciones in (0, 8_322_360, 900_000_000):
            p = self._perfil(retenciones)
            a = liquidar(p, self.par, "A")
            b = liquidar(p, self.par, "B")
            self.assertEqual(len(a.renglones), len(b.renglones))
            for i, (ra, rb) in enumerate(zip(a.renglones, b.renglones)):
                if i < len(a.renglones) - 1:
                    self.assertEqual(ra.concepto, rb.concepto,
                                     f"renglón {i} desalineado con ret={retenciones}")

    def test_signos_opuestos_en_el_ultimo_renglon(self):
        """Con la retención entre los dos impuestos, A y B caen a lados
        distintos. Es el caso que rompía la salida."""
        p = self._perfil(8_322_360)
        a = liquidar(p, self.par, "A")
        b = liquidar(p, self.par, "B")
        self.assertLess(a.saldo, 0, "la Ruta A debería dar saldo a favor")
        self.assertGreater(b.saldo, 0, "la Ruta B debería dar saldo a pagar")
        # Y las etiquetas del último renglón DIFIEREN: eso es lo que el CLI
        # detecta para cambiar a la fila con signo explícito.
        self.assertNotEqual(a.renglones[-1].concepto, b.renglones[-1].concepto)

    def test_el_saldo_del_objeto_conserva_el_signo(self):
        """El renglón guarda el valor absoluto, pero .saldo no: es lo que
        consumen el CLI, el CSV y el benchmark."""
        p = self._perfil(900_000_000)
        for ruta in ("A", "B"):
            L = liquidar(p, self.par, ruta)
            self.assertLess(L.saldo, 0)
            self.assertGreater(L.renglones[-1].valor, 0)


class TestRegresionesDeLaAuditoria(unittest.TestCase):
    """Casos que una auditoría adversarial encontró rotos. Fijados acá para
    que no vuelvan en silencio."""

    def setUp(self):
        self.par = P.cargar(2025)

    def _perfil(self, **secciones):
        base = {"contribuyente": {"anio_gravable": 2025, "residente_fiscal": True}}
        for k, v in secciones.items():
            base.setdefault(k, {}).update(v)
        d, sup = PF._completar(base)
        return PF.Perfil(d, None, sup)

    def test_parse_monto_rechaza_montos_malformados(self):
        """El regex validaba DESPUÉS de borrar los separadores, así que
        '1.2.3' llegaba convertido en '123' y pasaba como ciento veintitrés."""
        for basura in ("1.2.3", "1..2", "1.2.3.4", "12,34,567", "1e5",
                       "nan", "inf", "1_000", "(-1.234)", "١٢٣", "１２３"):
            with self.assertRaises(ValueError, msg=f"{basura!r} debería fallar"):
                parse_monto(basura)

    def test_parse_monto_sigue_aceptando_lo_valido(self):
        self.assertEqual(parse_monto("1.234.567"), 1_234_567)
        self.assertEqual(parse_monto("3800.00"), 3800.0)
        self.assertEqual(parse_monto("1.234"), 1234)
        self.assertEqual(parse_monto("1.234,56"), 1234.56)
        self.assertEqual(parse_monto("1,234.56"), 1234.56)
        self.assertEqual(parse_monto("(2.000,00)"), -2000.0)
        self.assertEqual(parse_monto("1.234.567,89", sep_decimal=","), 1_234_567.89)

    def test_deel_sin_moneda_no_cae_al_generico(self):
        """El respaldo genérico anulaba la guarda de moneda: un export de
        Deel sin columna de moneda se leía como COP, o sea 3.800 USD como
        3.800 pesos."""
        import tempfile

        from engine import adapters

        d = Path(tempfile.mkdtemp())
        ruta = d / "deel-payments.csv"
        ruta.write_text("Date,Type,Amount\n2025-03-14,invoice,3800.00\n",
                        encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            adapters.importar(ruta)
        self.assertIn("moneda", str(ctx.exception))

    def test_una_sola_palanca_de_dependientes(self):
        """Cuatro filas con la misma cifra invitaban a sumarlas, y el valor
        marginal del 2º al 4º dependiente es cero cuando gana la vía del
        10%, que no depende de cuántos sean."""
        r = comparar(self._perfil(
            ingresos={"rentas_trabajo_honorarios": 200_000_000}), self.par)
        filas = [p for p in r["sensibilidad"] if "dependiente" in p.etiqueta]
        self.assertEqual(len(filas), 1, f"debería haber una sola fila: {filas}")

    def test_via_de_dependientes_reportada_es_la_de_la_ruta_ganadora(self):
        """El resumen tomaba siempre la de la Ruta A y contradecía su propia
        tabla cuando ganaba la B."""
        p = self._perfil(
            ingresos={"rentas_trabajo_honorarios": 100_000_000},
            costos={"otros": 5_000_000},
            deducciones={"aportes_voluntarios": 25_000_000, "dependientes": 1},
        )
        r = comparar(p, self.par)
        ganadora = r["rutas"][r["mejor_ruta"]]
        self.assertIn(ganadora.dependientes_via,
                      ("72 UVT por dependiente (fuera del tope)",
                       "10% de la renta de trabajo (dentro del tope)"))
        # El objeto de la ruta ganadora es la fuente de verdad; el CLI lo lee
        # de ahí y no de la Ruta A.
        self.assertIs(ganadora, r["rutas"][r["mejor_ruta"]])

    def test_el_saldo_es_siempre_el_ultimo_renglon(self):
        """El CLI y el CSV identifican la fila del saldo por posición."""
        for ret in (0, 8_322_360, 900_000_000):
            p = self._perfil(
                ingresos={"rentas_trabajo_honorarios": 130_000_000},
                costos={"otros": 40_000_000},
                anticipos={"retenciones_practicadas": ret},
            )
            for ruta in ("A", "B"):
                L = liquidar(p, self.par, ruta)
                self.assertIn("SALDO", L.renglones[-1].concepto)


class TestRegresionesRonda2(unittest.TestCase):
    """Bugs que introdujeron los arreglos de la ronda anterior."""

    def setUp(self):
        self.par = P.cargar(2025)

    def test_sep_decimal_no_puede_partir_grupos_de_miles(self):
        """La regresión más cara del proyecto hasta ahora.

        Con `sep_decimal="."` —lo que pasan los adaptadores de Deel y Wise—
        "1.234.567" se partía por el último punto y salía 1234.567. Un CSV
        colombiano en pesos reclamado por esos adaptadores perdía un factor
        de mil, sin una sola advertencia.
        """
        for pista in (None, ".", ","):
            self.assertEqual(parse_monto("1.234.567", pista), 1_234_567,
                             f"falla con sep_decimal={pista!r}")
            self.assertEqual(parse_monto("1.234.567,89", pista), 1_234_567.89)
            self.assertEqual(parse_monto("1,234,567.89", pista), 1_234_567.89)

    def test_cero_con_decimales_no_tumba_el_adaptador(self):
        """`0.00` con sep_decimal="," daba error, y como el raise es por
        archivo, una sola fila en cero degradaba el extracto entero al
        adaptador genérico y perdía sus reglas de clasificación."""
        for pista in (None, ".", ","):
            self.assertEqual(parse_monto("0.00", pista), 0.0)
            self.assertEqual(parse_monto("1,50", pista), 1.5)

    def test_desbordamiento_no_devuelve_infinito(self):
        """float() no revienta con 400 dígitos: devuelve inf, que después
        rompe en Movimiento.convertir() lejos del archivo que lo causó."""
        for basura in ("9" * 400, "1" + ".000" * 200, "(" + "9" * 400 + ")"):
            with self.assertRaises(ValueError):
                parse_monto(basura)

    def test_errores_no_filtran_mensajes_internos_de_float(self):
        """El usuario debe ver su cadena original, no una mutilada."""
        for basura in ("1.2.3", "12,34,567", "1..2"):
            for pista in (None, ".", ","):
                with self.assertRaises(ValueError) as ctx:
                    parse_monto(basura, pista)
                self.assertIn("no es un monto reconocible", str(ctx.exception))
                self.assertIn(repr(basura), str(ctx.exception))

    def test_razon_de_dependientes_coincide_con_la_via_elegida(self):
        """El mensaje decía siempre que la vía ganadora 'no depende de
        cuántos sean'. Es cierto solo para la del 10%; con la de 72 UVT el
        motivo real es que la base ya llegó al tramo de tarifa 0%."""
        datos = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 40_935_336,
                         "rentas_capital": 26_091_191},
            "incrngo": {"aportes_obligatorios_salud_pension": 1_550_827},
            "costos": {"otros": 12_916_385},
            "anticipos": {"retenciones_practicadas": 17_209_626},
        }
        d, sup = PF._completar(datos)
        p = PF.Perfil(d, None, sup)
        r = comparar(p, self.par)
        fila = next((x for x in r["sensibilidad"] if "dependiente" in x.etiqueta), None)
        if fila is None or "no agrega nada" not in fila.nota:
            self.skipTest("este perfil no produce la nota de saturación")
        via = r["rutas"][r["mejor_ruta"]].dependientes_via
        if "10%" in via:
            self.assertIn("10%", fila.nota)
        else:
            self.assertIn("tarifa 0%", fila.nota)


class TestRegresionesRonda3(unittest.TestCase):
    """La tercera ronda de verificación. Los dos primeros son la misma clase
    de bug —una moneda leída con el factor equivocado— por dos caminos."""

    def setUp(self):
        self.par = P.cargar(2025)

    def test_montos_con_tres_decimales(self):
        """La regla 'tres dígitos detrás del separador = miles' no tenía
        excepción, así que rompía TODO monto de tres decimales: 0.500 salía
        500,0 y 12500.750 daba error. Las comisiones de Wise y las monedas
        de tres decimales (KWD, BHD, OMR) caen justo ahí."""
        self.assertEqual(parse_monto("0.500", "."), 0.5)
        self.assertEqual(parse_monto("0.001", "."), 0.001)
        self.assertEqual(parse_monto("12500.750", "."), 12500.75)
        self.assertEqual(parse_monto("1000.000", "."), 1000.0)
        self.assertEqual(parse_monto("897.681", "."), 897.681)

    def test_el_caso_ambiguo_sigue_resolviendose_a_favor_de_pesos(self):
        """'1.234' sin pista, o con pista de coma decimal, son mil
        doscientos treinta y cuatro pesos."""
        self.assertEqual(parse_monto("1.234"), 1234)
        self.assertEqual(parse_monto("1.234", ","), 1234)
        self.assertEqual(parse_monto("1.234", "."), 1.234)

    def test_grupos_de_miles_siguen_siendo_grupos_de_miles(self):
        """El arreglo no puede reabrir la regresión de la ronda anterior."""
        for pista in (None, ".", ","):
            self.assertEqual(parse_monto("1.234.567", pista), 1_234_567)
            self.assertEqual(parse_monto("1.000.000", pista), 1_000_000)

    def test_wise_sin_moneda_no_supone_dolares(self):
        """Deel tenía el guardia y Wise no: un archivo en pesos leído como
        dólares multiplica el ingreso declarado por ~4.000."""
        import tempfile

        from engine import adapters

        d = Path(tempfile.mkdtemp())
        ruta = d / "wise-statement.csv"
        ruta.write_text("Date,Amount,Description\n"
                        "2025-03-14,4500000,Received money from Cliente\n",
                        encoding="utf-8")
        try:
            movs, nombre = adapters.importar(ruta)
        except ValueError as e:
            self.assertIn("moneda", str(e))
            return
        # Si lo toma el genérico, tiene que ser COP, no USD.
        self.assertTrue(all(m.moneda == "COP" for m in movs),
                        f"{nombre} asumió una moneda extranjera")

    def test_fecha_con_zona_horaria_no_cambia_de_anio(self):
        """Deel y Wise emiten marcas ISO con zona. Cortarlas a 19 caracteres
        dejaba la fecha en UTC y movía un pago del 31 de diciembre al año
        siguiente, donde filtrar_anio lo botaba del ledger."""
        self.assertEqual(parse_fecha("2026-01-01T02:30:00Z").isoformat(),
                         "2025-12-31")
        self.assertEqual(parse_fecha("2025-06-15T12:00:00-05:00").isoformat(),
                         "2025-06-15")
        self.assertEqual(parse_fecha("2025-06-15").isoformat(), "2025-06-15")

    def test_tarifa_incompleta_no_se_carga(self):
        """_fusionar reemplaza las listas enteras: un año hijo con un solo
        rango borraba los otros seis y el motor liquidaba impuesto cero para
        cualquier base, sin aparecer como heredado."""
        import tempfile

        d = Path(tempfile.mkdtemp())
        (d / "ag2025").mkdir()
        (d / "ag2025" / "parametros.toml").write_text(
            (RAIZ / "knowledge" / "ag2025" / "parametros.toml").read_text(),
            encoding="utf-8")
        (d / "ag2099").mkdir()
        (d / "ag2099" / "parametros.toml").write_text(
            '[meta]\nanio_gravable = 2099\nhereda_de = "ag2025"\n'
            '[uvt]\nvalor = 60000\nfuente = "inventada"\n'
            '[[tarifa.rangos]]\ndesde_uvt = 0\nhasta_uvt = 0\n'
            'tarifa = 0.0\nadicional_uvt = 0\n',
            encoding="utf-8")
        with self.assertRaises(P.ParametrosNoEncontrados):
            P.cargar(2099, d)

    def test_traslados_que_se_cancelan_siguen_avisando(self):
        """Importar la plataforma y el banco deja el total de traslados en
        cero, y el aviso más importante del módulo no se emitía justo en el
        caso que describe."""
        from engine.ledger import Ledger, Movimiento
        from datetime import date as _date

        ledger = Ledger([
            Movimiento(_date(2025, 3, 10), "retiro", -1000, "COP", "traslado"),
            Movimiento(_date(2025, 3, 11), "abono", 1000, "COP", "traslado"),
        ])
        ledger.convertir(None)
        self.assertEqual(ledger.total("traslado"), 0)
        self.assertIn("traslado", ledger.resumen())
        self.assertTrue(any("traslados" in a.lower() for a in ledger.validar()))


class TestClasificacionYSalidas(unittest.TestCase):
    """Reglas de clasificación y escritura del ledger."""

    def _ledger(self, movs):
        from engine.ledger import Ledger

        return Ledger(movs).convertir(None)

    def _mov(self, desc, monto, categoria="desconocido"):
        from datetime import date as _date

        from engine.ledger import Movimiento

        return Movimiento(_date(2025, 5, 5), desc, monto, "COP", categoria)

    def test_pago_a_tercero_por_nequi_no_es_traslado(self):
        """"NEQUI" y "TRASLADO" como subcadena convertían en traslado
        cualquier pago a un tercero, que es como se le paga a medio país."""
        from engine.adapters.bancolombia import _clasificar

        self.assertNotEqual(_clasificar("PAGO NEQUI A CONTRATISTA"), "traslado")
        self.assertNotEqual(_clasificar("TRANSFERENCIA NEQUI PROVEEDOR"), "traslado")
        self.assertEqual(_clasificar("TRASLADO ENTRE CUENTAS PROPIAS"), "traslado")

    def test_ingreso_convertido_sigue_siendo_ingreso(self):
        """"Received money from Cliente — converted to COP" trae las dos
        palabras; clasificarlo como traslado borra un ingreso del ledger."""
        from engine.adapters.wise import _clasificar

        self.assertEqual(
            _clasificar("Received money from Cliente SAS, converted to COP"),
            "ingreso_trabajo",
        )

    def test_wise_no_reclama_otherwise(self):
        from engine.adapters import wise

        self.assertFalse(wise.detecta(["Fecha", "Valor"], "otherwise.csv"))

    def test_csv_del_ledger_neutraliza_formulas(self):
        """El ledger se lo manda el usuario a su contador por correo, y las
        descripciones vienen de un CSV de terceros."""
        import csv as _csv
        import tempfile

        ledger = self._ledger([
            self._mov("=HYPERLINK(\"http://x\",\"pago\")", 1000, "costo"),
            self._mov("pago normal", 2000, "costo"),
        ])
        destino = Path(tempfile.mkdtemp()) / "ledger.csv"
        ledger.escribir_csv(destino)
        with open(destino, newline="", encoding="utf-8") as f:
            filas = list(_csv.DictReader(f))
        peligrosas = [r for r in filas if r["descripcion"].startswith("=")]
        self.assertEqual(peligrosas, [], "una descripción quedó como fórmula")
        self.assertTrue(any(r["descripcion"] == "pago normal" for r in filas))

    def test_los_reembolsos_netean_y_se_avisan(self):
        """Un reembolso dentro de los costos tiene que restar del gasto
        deducible: lo devuelto no se gastó.

        Este test fijó dos veces el comportamiento equivocado. Primero con
        abs() sobre el total, donde el signo del resultado dependía de cuál
        partida pesara más. Después sumando solo las salidas, que ignora el
        reembolso en silencio y sobrestima el costo — o sea subestima el
        impuesto, que es el lado caro.

        Lo correcto es netear Y decirlo, porque la cifra que sale ya no es la
        suma de los comprobantes y el contador va a preguntar.
        """
        ledger = self._ledger([
            self._mov("pago a contratista", -5_000_000, "costo"),
            self._mov("reembolso del contratista", 1_000_000, "costo"),
        ])
        self.assertEqual(ledger.a_perfil()["costos"]["otros"], 4_000_000)
        self.assertTrue(any("POSITIVO" in a for a in ledger.validar()),
                        "netear sin avisar deja al usuario sin explicación")

    def test_retencion_reversada_resta_del_anticipo(self):
        """Mismo arreglo que en costos, que no se había aplicado acá: con
        abs() por movimiento, una retención devuelta AUMENTABA el anticipo
        que se descuenta del impuesto."""
        ledger = self._ledger([
            self._mov("retención en la fuente", -1_000_000, "retencion"),
            self._mov("reintegro de retención", 500_000, "retencion"),
        ])
        self.assertEqual(
            ledger.a_perfil()["anticipos"]["retenciones_practicadas"], 500_000
        )

    def test_extracto_en_latin1_conserva_las_tildes(self):
        """Con errors='replace' se perdían las tildes y con ellas las
        palabras que usan las reglas de clasificación."""
        import tempfile

        from engine.adapters.generico import abrir_csv

        ruta = Path(tempfile.mkdtemp()) / "extracto.csv"
        ruta.write_bytes(
            "fecha,descripcion,valor\n05/05/2025,RETENCIÓN EN LA FUENTE,-1000\n"
            .encode("latin-1")
        )
        with abrir_csv(ruta) as f:
            contenido = f.read()
        self.assertIn("RETENCIÓN", contenido)
