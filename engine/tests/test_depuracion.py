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

    def test_sensibilidad_ordenada_y_positiva(self):
        datos = {
            "contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 200_000_000},
        }
        d, s = PF._completar(datos)
        r = comparar(PF.Perfil(d, None, s), self.par)
        ahorros = [p.ahorro_max for p in r["sensibilidad"]]
        self.assertEqual(ahorros, sorted(ahorros, reverse=True))
        self.assertTrue(all(a > 0 for a in ahorros))

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
