"""Tests de engine/cli.py — 442 líneas que ningún test importaba.

Por qué existe este archivo
───────────────────────────
`make ejemplo` corría el CLI y solo miraba el código de salida. Con eso,
escapaban exactamente los dos bugs que rondas anteriores ya habían arreglado
ahí y que nada impedía reabrir:

  · la columna de RUTA B imprimiendo los valores de la RUTA A;
  · el CSV perdiendo el signo del saldo, con lo que un saldo A FAVOR se leía
    como saldo A PAGAR.

Y el tercero, de la ronda 5: `importar` salía 0 con un archivo sin importar.

Se prueba por la SALIDA, que es lo que el usuario y el agente leen. Un test
que solo mire el exit code repite el hueco que dejó pasar todo esto.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from engine import cli

RAIZ = Path(__file__).resolve().parent.parent.parent
EJEMPLO = RAIZ / "expediente.ejemplo"


def correr(*argv) -> tuple[int, str]:
    """Corre el CLI y devuelve (código de salida, salida completa)."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        codigo = cli.main(list(argv))
    return codigo, buffer.getvalue()


def expediente_con(**archivos) -> Path:
    exp = Path(tempfile.mkdtemp()) / "expediente"
    (exp / "00-crudo").mkdir(parents=True)
    for nombre, contenido in archivos.items():
        (exp / "00-crudo" / nombre.replace("__", ".")).write_text(
            contenido, encoding="utf-8")
    return exp


# ---------------------------------------------------------------------

class TestCalcular(unittest.TestCase):
    """La tabla de dos columnas es la salida principal del producto."""

    def setUp(self):
        self.codigo, self.salida = correr("calcular", "--expediente", str(EJEMPLO))

    def test_el_ejemplo_calcula(self):
        self.assertEqual(self.codigo, 0, self.salida)

    def test_la_columna_de_ruta_b_trae_los_valores_de_la_ruta_b(self):
        """El bug: se imprimía `ren.valor` en las dos columnas, así que la
        RUTA B mostraba los números de la RUTA A. La tabla se veía perfecta
        y decía dos veces lo mismo."""
        from engine import parametros as P
        from engine import perfil as PF
        from engine.depuracion import comparar

        p = PF.cargar(EJEMPLO)
        r = comparar(p, P.cargar(p.anio_gravable))
        a, b = r["rutas"]["A"], r["rutas"]["B"]

        distintos = [i for i, ren in enumerate(a.renglones)
                     if ren.valor != b.renglones[i].valor]
        self.assertTrue(distintos, "el perfil de ejemplo dejó de distinguir las rutas")

        for i in distintos:
            esperado_b = cli.cop(b.renglones[i].valor)
            self.assertIn(esperado_b, self.salida,
                          f"el renglón {a.renglones[i].concepto!r} no muestra el "
                          f"valor de la Ruta B ({esperado_b})")

    def test_el_saldo_se_imprime_con_su_signo_en_las_dos_rutas(self):
        from engine import parametros as P
        from engine import perfil as PF
        from engine.depuracion import comparar

        p = PF.cargar(EJEMPLO)
        r = comparar(p, P.cargar(p.anio_gravable))
        for ruta in ("A", "B"):
            self.assertIn(cli.cop(round(r["rutas"][ruta].saldo)), self.salida)
        self.assertIn("a pagar", self.salida)
        self.assertIn("a favor", self.salida)

    def test_la_ruta_ganadora_que_se_imprime_es_la_que_calculo_el_motor(self):
        from engine import parametros as P
        from engine import perfil as PF
        from engine.depuracion import comparar

        p = PF.cargar(EJEMPLO)
        r = comparar(p, P.cargar(p.anio_gravable))
        self.assertIn(f"RUTA {r['mejor_ruta']}", self.salida)

    def test_el_borrador_se_anuncia_como_borrador(self):
        """No es cosmética: es lo que separa esto de una declaración."""
        self.assertIn("BORRADOR", self.salida)
        self.assertIn("contador", self.salida.lower())

    def test_las_verificaciones_de_riesgo_llegan_a_la_salida(self):
        from engine import parametros as P
        from engine import perfil as PF
        from engine.depuracion import comparar

        p = PF.cargar(EJEMPLO)
        r = comparar(p, P.cargar(p.anio_gravable))
        for v in r["verificaciones"]:
            self.assertIn(v["id"], self.salida,
                          f"{v['id']} se calculó y no se imprimió")


class TestCsvDeEscenarios(unittest.TestCase):
    """El CSV lo lee un script o el contador, no una persona mirando iconos."""

    def setUp(self):
        from engine import parametros as P
        from engine import perfil as PF
        from engine.depuracion import comparar

        self.p = PF.cargar(EJEMPLO)
        self.r = comparar(self.p, P.cargar(self.p.anio_gravable))

    def _escribir(self, a, b) -> list[list[str]]:
        import csv

        destino = Path(tempfile.mkdtemp()) / "escenarios.csv"
        cli._escribir_csv(destino, a, b)
        with open(destino, newline="", encoding="utf-8") as f:
            return list(csv.reader(f))

    def test_el_saldo_conserva_el_signo_aunque_las_dos_rutas_coincidan(self):
        """El bug: el signo solo se usaba cuando las rutas divergían, así que
        la misma columna significaba una cosa u otra según el perfil. Quien
        lo leyera con un script sumaba un saldo a favor como si fuera a
        pagar."""
        a, b = self.r["rutas"]["A"], self.r["rutas"]["B"]
        filas = self._escribir(a, b)
        saldo = [f for f in filas if f[0].startswith("= SALDO")]
        self.assertEqual(len(saldo), 1, f"no hay renglón de saldo: {filas[-1]}")
        self.assertIn("positivo a pagar", saldo[0][0])
        self.assertEqual(int(saldo[0][1]), round(a.saldo))
        self.assertEqual(int(saldo[0][2]), round(b.saldo))

    def test_la_columna_b_del_csv_no_repite_la_columna_a(self):
        a, b = self.r["rutas"]["A"], self.r["rutas"]["B"]
        filas = self._escribir(a, b)[1:]
        for i, ren in enumerate(a.renglones[:-1]):
            self.assertEqual(int(filas[i][1]), ren.valor)
            self.assertEqual(int(filas[i][2]), b.renglones[i].valor)

    def test_un_saldo_a_favor_sale_negativo(self):
        """Se construye a mano un caso de saldo a favor: es el que el signo
        equivocado convierte en una deuda inventada."""
        a = self.r["rutas"]["A"]
        b = self.r["rutas"]["B"]
        a.saldo = -5_000_000
        b.saldo = -3_000_000
        filas = self._escribir(a, b)
        saldo = [f for f in filas if f[0].startswith("= SALDO")][0]
        self.assertEqual(int(saldo[1]), -5_000_000)
        self.assertEqual(int(saldo[2]), -3_000_000)


class TestImportar(unittest.TestCase):
    """El comando por el que pasa todo lo que el usuario carga de verdad."""

    BUENO = ("fecha,descripcion,valor\n"
             "14/03/2025,Pago cliente,50.000.000\n"
             "20/06/2025,Pago cliente,30.000.000\n")

    def test_el_caso_feliz_sale_cero(self):
        exp = expediente_con(banco__csv=self.BUENO)
        codigo, salida = correr("importar", "--expediente", str(exp), "--anio", "2025")
        self.assertEqual(codigo, 0, salida)
        self.assertTrue((exp / "02-datos" / "ledger.csv").exists())

    def test_un_archivo_que_no_se_pudo_importar_NO_sale_cero(self):
        """Antes: imprimía un ✗ temprano, seguía, escribía el ledger con los
        ingresos de ese archivo faltando, y salía 0."""
        exp = expediente_con(banco__csv=self.BUENO,
                             roto__csv="columna_rara,otra\na,b\n")
        codigo, salida = correr("importar", "--expediente", str(exp), "--anio", "2025")
        self.assertEqual(codigo, 1, salida)
        self.assertIn("INCOMPLETO", salida)
        self.assertIn("roto.csv", salida)

    def test_una_fila_ilegible_no_bota_el_archivo_pero_si_el_codigo_de_salida(self):
        """Una celda mala en la fila 200 abortaba el export entero y borraba
        doce meses de ingreso. Ahora se salta, se cuenta, y se dice."""
        exp = expediente_con(banco__csv=(
            "fecha,descripcion,valor\n"
            "14/03/2025,Pago cliente,50.000.000\n"
            "15/03/2025,Pago roto,no-es-un-numero\n"
            "20/06/2025,Pago cliente,30.000.000\n"
        ))
        codigo, salida = correr("importar", "--expediente", str(exp), "--anio", "2025")
        self.assertEqual(codigo, 1, salida)
        self.assertIn("línea 3", salida)
        # Y lo que sí se pudo leer, se leyó.
        ledger = (exp / "02-datos" / "ledger.csv").read_text(encoding="utf-8")
        self.assertIn("50000000", ledger)
        self.assertIn("30000000", ledger)

    def test_el_sugerido_advierte_en_el_encabezado_cuando_falta_algo(self):
        """Este archivo es el que alguien abre para copiar cifras al perfil.
        Si el ledger está incompleto, las cifras de ahí lo están, y cuadran
        entre sí de todos modos."""
        exp = expediente_con(banco__csv=self.BUENO,
                             roto__csv="columna_rara,otra\na,b\n")
        correr("importar", "--expediente", str(exp), "--anio", "2025")
        sugerido = (exp / "02-datos" / "sugerido-perfil.toml").read_text(encoding="utf-8")
        encabezado = sugerido.split("[ingresos]")[0]
        self.assertIn("INCOMPLETAS", encabezado)
        self.assertIn("roto.csv", encabezado)

    def test_sin_archivos_avisa_y_no_finge_exito(self):
        exp = expediente_con()
        codigo, salida = correr("importar", "--expediente", str(exp))
        self.assertEqual(codigo, 1)
        self.assertIn("No hay archivos CSV", salida)

    def test_reimportar_reporta_el_estado_del_ledger_anterior(self):
        """El mensaje va siempre, no solo cuando se conservó algo."""
        exp = expediente_con(banco__csv=self.BUENO)
        correr("importar", "--expediente", str(exp), "--anio", "2025")
        _, salida = correr("importar", "--expediente", str(exp), "--anio", "2025")
        self.assertIn("Ledger anterior", salida)


class TestParametros(unittest.TestCase):
    def test_muestra_la_uvt_y_la_tarifa_del_anio(self):
        from engine import parametros as P

        codigo, salida = correr("parametros", "--anio", "2025")
        self.assertEqual(codigo, 0)
        par = P.cargar(2025)
        self.assertIn(cli.cop(par.uvt), salida)
        for r in par.exigir("tarifa.rangos"):
            self.assertIn(f"{r['tarifa']:.0%}", salida)

    def test_un_anio_sin_parametros_falla_con_mensaje(self):
        codigo, salida = correr("parametros", "--anio", "1999")
        self.assertEqual(codigo, 1)
        self.assertIn("1999", salida)


class TestVerificar(unittest.TestCase):
    def test_el_ejemplo_es_un_perfil_valido(self):
        codigo, salida = correr("verificar", "--expediente", str(EJEMPLO))
        self.assertEqual(codigo, 0, salida)
        self.assertIn("válido", salida)

    def test_un_perfil_fuera_de_alcance_no_se_puede_calcular(self):
        exp = Path(tempfile.mkdtemp())
        (exp / "perfil.toml").write_text(
            "[contribuyente]\nanio_gravable = 2025\nresidente_fiscal = true\n"
            "[ingresos]\nrentas_trabajo_honorarios = 100_000_000\n"
            "rentas_pension = 20_000_000\n",
            encoding="utf-8",
        )
        codigo, salida = correr("verificar", "--expediente", str(exp))
        self.assertEqual(codigo, 1)
        self.assertIn("FUERA DE ALCANCE", salida)


if __name__ == "__main__":
    unittest.main()
