"""Tests de la capa de datos: TRM, ledger e importación.

Por qué existe este archivo
───────────────────────────
Una medición con inyección de mutaciones sobre el repositorio encontró que
el núcleo tributario estaba bien cubierto —toda mutación de constantes,
topes o tarifa se detectaba— y que la capa de datos no tenía **ninguna**
aserción. Doce mutaciones escapaban, entre ellas:

  · `Movimiento.convertir()` ignorando la TRM: 3.800 dólares como 3.800
    pesos, el error de ~4.000× que el proyecto entero dice prevenir.
  · `TRM.de()` devolviendo el promedio en vez de la del día — exactamente
    lo que el art. 288 prohíbe, y lo que la herramienta anuncia como su
    valor diferencial.
  · `filtrar_anio` mezclando años.

O sea: la mitad del producto que el usuario realmente usa —porque nadie
teclea trescientos movimientos a mano— no estaba verificada por nada.

Los valores esperados se calculan a mano en cada test.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from engine.ledger import (Ledger, Movimiento, aplicar_clasificacion_previa,
                           comparar_trm_diaria_vs_promedio,
                           leer_clasificacion_previa)
from engine.trm import TRM, SinTRM, leer_cache


def serie(**por_dia) -> TRM:
    """TRM de juguete: serie('2025-03-14', 4000.0) → {date: 4000.0}."""
    return TRM({date.fromisoformat(k.replace("_", "-")): v
                for k, v in por_dia.items()})


class TestConversionTRM(unittest.TestCase):
    """El art. 288 exige la TRM de la fecha de realización de cada operación."""

    def setUp(self):
        self.trm = TRM({
            date(2025, 3, 14): 4_000.00,
            date(2025, 3, 17): 4_100.00,   # lunes
            date(2025, 12, 31): 4_400.00,
        })

    def test_la_conversion_usa_la_trm_del_dia(self):
        m = Movimiento(date(2025, 3, 14), "pago", 3_800.00, "USD").convertir(self.trm)
        self.assertEqual(m.trm, 4_000.00)
        self.assertEqual(m.monto_cop, 15_200_000)   # 3.800 × 4.000

    def test_dias_distintos_dan_montos_distintos(self):
        """Si `de()` devolviera siempre el mismo valor —el promedio, o el
        primero de la serie— esto no lo notaría nadie más."""
        a = Movimiento(date(2025, 3, 14), "pago", 1_000.0, "USD").convertir(self.trm)
        b = Movimiento(date(2025, 3, 17), "pago", 1_000.0, "USD").convertir(self.trm)
        self.assertEqual(a.monto_cop, 4_000_000)
        self.assertEqual(b.monto_cop, 4_100_000)
        self.assertNotEqual(a.monto_cop, b.monto_cop)

    def test_el_promedio_no_es_la_trm_de_ningun_dia(self):
        """Fija que el motor no esté usando el promedio por debajo."""
        promedio = self.trm.promedio()
        m = Movimiento(date(2025, 3, 14), "pago", 1_000.0, "USD").convertir(self.trm)
        self.assertNotEqual(m.monto_cop, round(1_000.0 * promedio))

    def test_los_pesos_no_se_convierten(self):
        m = Movimiento(date(2025, 3, 14), "pago", 5_000_000, "COP").convertir(self.trm)
        self.assertEqual(m.trm, 1.0)
        self.assertEqual(m.monto_cop, 5_000_000)

    def test_moneda_extranjera_sin_serie_falla(self):
        with self.assertRaises(ValueError):
            Movimiento(date(2025, 3, 14), "pago", 100.0, "USD").convertir(None)

    def test_fin_de_semana_toma_el_ultimo_dia_habil_y_deja_rastro(self):
        """La TRM del viernes rige el sábado: eso es correcto. Lo que no
        puede pasar es que no quede registro de cuántos días se retrocedió."""
        sabado = date(2025, 3, 15)
        self.assertEqual(self.trm.de(sabado), 4_000.00)
        self.assertIn(sabado, self.trm.suplidas)
        self.assertEqual(self.trm.suplidas[sabado][0], date(2025, 3, 14))

    def test_hueco_largo_se_reporta(self):
        hueco = date(2025, 3, 20)     # 3 días después del 17
        self.trm.de(hueco)
        self.assertTrue(self.trm.huecos_grandes(dias=2))

    def test_sin_trm_en_toda_la_semana_es_error(self):
        with self.assertRaises(SinTRM):
            self.trm.de(date(2025, 6, 1))


class TestCacheTRM(unittest.TestCase):
    def _escribir(self, contenido: str, binario=False) -> Path:
        ruta = Path(tempfile.mkdtemp()) / "trm-cache.csv"
        if binario:
            ruta.write_bytes(contenido)
        else:
            ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def test_lectura_normal(self):
        serie, avisos = leer_cache(self._escribir("fecha,trm\n2025-06-10,4010.50\n"))
        self.assertEqual(serie[date(2025, 6, 10)], 4010.50)
        self.assertEqual(avisos, [])

    def test_separador_de_miles_no_da_trm_de_cuatro_pesos(self):
        """csv.DictReader mandaba el resto a la restkey y quedaba TRM = 4,
        que después multiplica los ingresos en dólares por cuatro."""
        serie, _ = leer_cache(self._escribir('fecha,trm\n2025-06-10,"4,010.50"\n'))
        self.assertEqual(serie[date(2025, 6, 10)], 4010.50)

    def test_valor_fuera_de_rango_se_descarta_con_aviso(self):
        serie, avisos = leer_cache(self._escribir("fecha,trm\n2025-06-10,4\n"))
        self.assertEqual(serie, {})
        self.assertTrue(any("fuera del rango" in a for a in avisos))

    def test_bom_no_vacia_el_cache(self):
        """Un caché guardado desde Excel trae BOM y la cabecera dejaba de
        reconocerse, con lo que el archivo entero se leía como vacío."""
        serie, _ = leer_cache(
            self._escribir("﻿fecha,trm\n2025-06-10,4010.50\n".encode("utf-8"),
                           binario=True)
        )
        self.assertEqual(serie[date(2025, 6, 10)], 4010.50)

    def test_cabecera_irreconocible_avisa_en_vez_de_callar(self):
        serie, avisos = leer_cache(self._escribir("a,b\n1,2\n"))
        self.assertEqual(serie, {})
        self.assertTrue(avisos)


class TestLedger(unittest.TestCase):
    def _mov(self, dia, monto, categoria="desconocido", moneda="COP", fuente="x.csv"):
        return Movimiento(date(2025, dia // 100, dia % 100), "mov", monto,
                          moneda, categoria, fuente=fuente)

    def test_filtrar_anio_es_exacto(self):
        ledger = Ledger([
            Movimiento(date(2024, 12, 31), "anterior", 100, "COP"),
            Movimiento(date(2025, 1, 1), "primero", 200, "COP"),
            Movimiento(date(2025, 12, 31), "último", 300, "COP"),
            Movimiento(date(2026, 1, 1), "siguiente", 400, "COP"),
        ]).convertir(None)
        filtrado = ledger.filtrar_anio(2025)
        self.assertEqual(len(filtrado.movimientos), 2)
        self.assertEqual({m.fecha.year for m in filtrado.movimientos}, {2025})

    def test_los_traslados_no_cuentan_como_ingreso(self):
        ledger = Ledger([
            self._mov(310, 10_000_000, "ingreso_trabajo"),
            self._mov(311, -8_000_000, "traslado"),
            self._mov(312, 8_000_000, "traslado"),
        ]).convertir(None)
        self.assertEqual(ledger.total("ingreso_trabajo"), 10_000_000)
        self.assertEqual(ledger.total("traslado"), 0)
        # Aunque el neto sea cero, la categoría existe y hay que avisar.
        self.assertIn("traslado", ledger.resumen())
        self.assertTrue(any("traslado" in a.lower() for a in ledger.validar()))

    def test_consignaciones_desglosa_por_fuente_y_no_concluye(self):
        ledger = Ledger([
            self._mov(310, 50_000_000, "ingreso_trabajo", fuente="deel.csv"),
            self._mov(311, 50_000_000, "ingreso_trabajo", fuente="banco.csv"),
        ]).convertir(None)
        cons = ledger.consignaciones()
        self.assertEqual(cons["entradas_brutas"], 100_000_000)
        self.assertEqual(len(cons["por_fuente"]), 2)
        self.assertFalse(cons["listo_para_el_umbral"])
        self.assertTrue(any("dos veces" in a for a in cons["avisos"]))

    def test_comparar_trm_promedio_usa_las_fechas_del_ledger(self):
        trm = TRM({
            date(2025, 3, 14): 4_000.0,
            date(2025, 3, 17): 5_000.0,
            date(2020, 1, 1): 100.0,      # ruido de otro año en el caché
        })
        ledger = Ledger([
            Movimiento(date(2025, 3, 14), "a", 1_000.0, "USD", "ingreso_trabajo"),
            Movimiento(date(2025, 3, 17), "b", 1_000.0, "USD", "ingreso_trabajo"),
        ]).convertir(trm)
        r = comparar_trm_diaria_vs_promedio(ledger, trm)
        self.assertEqual(r["con_trm_diaria"], 9_000_000)      # 4M + 5M
        self.assertEqual(r["trm_promedio"], 4_500.0)          # no incluye el 100
        self.assertEqual(r["diferencia"], 0)

    def test_el_csv_del_ledger_hace_ida_y_vuelta(self):
        ledger = Ledger([
            self._mov(314, 1_500_000, "costo"),
            self._mov(315, 2_500_000, "ingreso_trabajo"),
        ]).convertir(None)
        destino = Path(tempfile.mkdtemp()) / "ledger.csv"
        ledger.escribir_csv(destino)
        previas, ilegibles = leer_clasificacion_previa(destino)
        self.assertEqual(len(previas), 2)
        self.assertEqual(ilegibles, [])

    def test_las_correcciones_a_mano_sobreviven_a_reimportar(self):
        """La herramienta dice «arréglala en el ledger y vuelve a correr», y
        sobreescribía el archivo tirando esa corrección a la basura."""
        original = Ledger([self._mov(314, 1_500_000, "desconocido")]).convertir(None)
        destino = Path(tempfile.mkdtemp()) / "ledger.csv"
        original.escribir_csv(destino)

        # El usuario abre el CSV y lo reclasifica.
        texto = destino.read_text(encoding="utf-8").replace("desconocido", "traslado")
        destino.write_text(texto, encoding="utf-8")

        # Se vuelve a importar el mismo movimiento, sin clasificar.
        nuevo = Ledger([self._mov(314, 1_500_000, "desconocido")]).convertir(None)
        r = aplicar_clasificacion_previa(nuevo, *leer_clasificacion_previa(destino))
        self.assertEqual(r.conservadas, 1)
        self.assertEqual(nuevo.movimientos[0].categoria, "traslado")

    def test_una_categoria_inventada_en_el_csv_no_se_aplica(self):
        original = Ledger([self._mov(314, 1_500_000, "desconocido")]).convertir(None)
        destino = Path(tempfile.mkdtemp()) / "ledger.csv"
        original.escribir_csv(destino)
        destino.write_text(
            destino.read_text(encoding="utf-8").replace("desconocido", "inventada"),
            encoding="utf-8",
        )
        nuevo = Ledger([self._mov(314, 1_500_000, "desconocido")]).convertir(None)
        r = aplicar_clasificacion_previa(nuevo, *leer_clasificacion_previa(destino))
        self.assertEqual(r.conservadas, 0)
        self.assertEqual(nuevo.movimientos[0].categoria, "desconocido")
        self.assertTrue(r.perdidas, "una categoría inventada se descartó en silencio")


class TestCaminoNegativoDeLaReclasificacion(unittest.TestCase):
    """Lo que pasa cuando la reclasificación NO funciona.

    El camino feliz tenía dos tests desde la ronda 4. El negativo no tenía
    ninguno, y ahí vivían los dos fallos: dos filas con la misma llave se
    clasificaban las dos con la última categoría, y un ledger guardado desde
    Excel en locale español perdía TODAS las correcciones sin decir nada —el
    mensaje `↻` solo se imprimía si el contador daba mayor que cero.
    """

    def _escribir(self, *movs) -> Path:
        destino = Path(tempfile.mkdtemp()) / "ledger.csv"
        Ledger(list(movs)).convertir(None).escribir_csv(destino)
        return destino

    def _mov(self, dia, monto, categoria, fuente="banco.csv", desc="giro"):
        return Movimiento(date(2025, 3, dia), desc, monto, "COP", categoria,
                          fuente=fuente)

    def test_dos_filas_con_la_misma_llave_conservan_cada_una_su_categoria(self):
        """Dos transferencias del mismo monto el mismo día es lo más común
        de un extracto. Con la llave sola, el dict se quedaba con la última
        y `aplicar` se la imponía a las dos."""
        destino = self._escribir(
            self._mov(14, 1_500_000, "traslado", desc="giro A"),
            self._mov(14, 1_500_000, "costo", desc="giro B"),
        )
        nuevo = Ledger([
            self._mov(14, 1_500_000, "desconocido", desc="giro A"),
            self._mov(14, 1_500_000, "desconocido", desc="giro B"),
        ]).convertir(None)
        r = aplicar_clasificacion_previa(nuevo, *leer_clasificacion_previa(destino))
        self.assertEqual([m.categoria for m in nuevo.movimientos],
                         ["traslado", "costo"])
        self.assertEqual(r.conservadas, 2)

    def test_un_ledger_guardado_en_locale_espanol_se_sigue_leyendo(self):
        """Excel reescribe 1500000.00 como 1500000,00 según la configuración
        regional de la máquina. `float()` reventaba y el `continue` se tragaba
        la excepción: se perdían todas las clasificaciones."""
        destino = self._escribir(self._mov(14, 1_500_000, "traslado"))
        destino.write_text(
            destino.read_text(encoding="utf-8").replace("1500000.00", '"1500000,00"'),
            encoding="utf-8",
        )
        nuevo = Ledger([self._mov(14, 1_500_000, "desconocido")]).convertir(None)
        r = aplicar_clasificacion_previa(nuevo, *leer_clasificacion_previa(destino))
        self.assertEqual(r.conservadas, 1)
        self.assertEqual(nuevo.movimientos[0].categoria, "traslado")

    def test_una_fila_ilegible_se_reporta_en_vez_de_desaparecer(self):
        destino = self._escribir(self._mov(14, 1_500_000, "traslado"))
        destino.write_text(
            destino.read_text(encoding="utf-8").replace("1500000.00", "no-es-numero"),
            encoding="utf-8",
        )
        nuevo = Ledger([self._mov(14, 1_500_000, "desconocido")]).convertir(None)
        r = aplicar_clasificacion_previa(nuevo, *leer_clasificacion_previa(destino))
        self.assertEqual(r.conservadas, 0)
        self.assertTrue(r.ilegibles)
        self.assertTrue(any("no se pudieron leer" in a for a in r.avisos()))

    def test_el_resumen_habla_tambien_cuando_no_se_conservo_nada(self):
        """El caso que importa: cero conservadas tiene que decirse. El
        mensaje viejo vivía dentro de un `if aplicadas`."""
        vacio = Ledger([]).convertir(None)
        r = aplicar_clasificacion_previa(vacio, {}, [])
        self.assertIn("0 clasificación(es) conservadas", r.resumen())

    def test_una_correccion_cuyo_movimiento_desaparecio_se_reporta(self):
        destino = self._escribir(self._mov(14, 1_500_000, "traslado"))
        nuevo = Ledger([self._mov(20, 999, "desconocido")]).convertir(None)
        r = aplicar_clasificacion_previa(nuevo, *leer_clasificacion_previa(destino))
        self.assertEqual(r.conservadas, 0)
        self.assertTrue(r.perdidas)
        self.assertTrue(any("NO se pudieron reaplicar" in a for a in r.avisos()))


class TestImportacionCompleta(unittest.TestCase):
    """De CSV crudo a cifras del perfil, que es el camino que nadie verifica
    y por el que pasa todo lo que el usuario realmente carga."""

    def test_deel_en_dolares_llega_al_perfil_convertido(self):
        from engine import adapters

        d = Path(tempfile.mkdtemp())
        (d / "deel.csv").write_text(
            "Date,Type,Amount,Currency,Counterparty,Description\n"
            "2025-03-14,invoice,3800.00,USD,Cliente,Payment received\n"
            "2025-03-17,withdraw,-3000.00,USD,Bank,Withdraw to bank\n",
            encoding="utf-8",
        )
        movs, nombre = adapters.importar(d / "deel.csv")
        self.assertEqual(nombre, "Deel")

        trm = TRM({date(2025, 3, 14): 4_000.0, date(2025, 3, 17): 4_100.0})
        ledger = Ledger(movs).convertir(trm)

        # 3.800 × 4.000 = 15.200.000, y el retiro NO es ingreso.
        self.assertEqual(ledger.total("ingreso_trabajo"), 15_200_000)
        self.assertEqual(ledger.total("traslado"), -12_300_000)
        self.assertEqual(
            ledger.a_perfil()["ingresos"]["rentas_trabajo_honorarios"], 15_200_000
        )


class TestFilasEnCero(unittest.TestCase):
    """Las filas con monto cero se descartan, y si TODAS lo son se avisa:
    un extracto entero en cero casi siempre significa que se identificó mal
    la columna de monto, no que no hubo movimientos."""

    def _csv(self, contenido: str) -> Path:
        ruta = Path(tempfile.mkdtemp()) / "extracto.csv"
        ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def test_las_filas_en_cero_no_entran_al_ledger(self):
        from engine.adapters.generico import importar

        movs = importar(self._csv(
            "fecha,descripcion,valor\n"
            "14/03/2025,pago,1500000\n"
            "15/03/2025,ajuste,0\n"
            "16/03/2025,pago,2500000\n"
        ))
        self.assertEqual(len(movs), 2)
        self.assertTrue(all(m.monto_origen != 0 for m in movs))

    def test_un_archivo_entero_en_cero_es_error(self):
        from engine.adapters.generico import importar

        with self.assertRaises(ValueError) as ctx:
            importar(self._csv(
                "fecha,descripcion,valor\n"
                "14/03/2025,pago,0\n"
                "15/03/2025,pago,0\n"
            ))
        self.assertIn("monto", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
