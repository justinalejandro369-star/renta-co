"""Tests del escáner de datos personales.

Un escáner de PII falla de dos maneras y las dos son graves:

  · FALSO NEGATIVO — deja pasar una cédula. El dato termina publicado.
  · FALSO POSITIVO — grita ante cada monto. La gente deja de leerlo, y un
    escáner que nadie lee es peor que no tener escáner.

Estos tests fijan las dos direcciones. La segunda importa especialmente en
este proyecto: en un expediente tributario "$3.585.528" aparece en cada
párrafo y tiene exactamente la forma de una cédula.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import escanear_privacidad as esc  # noqa: E402


def escanear_texto(texto: str, nombres=None, sufijo=".md"):
    return esc.escanear_texto(texto, nombres or [], sufijo)


def tipos(hallazgos) -> set[str]:
    """Tipos de los hallazgos de confianza ALTA — los que rompen el build."""
    return {t for _, t, _, c in hallazgos if c == "alta"}


def altas(hallazgos) -> list:
    return [h for h in hallazgos if h[3] == "alta"]


class TestDetecta(unittest.TestCase):
    """Falsos negativos: lo que NO puede escapar."""

    def test_cedula_con_contexto(self):
        h = escanear_texto("Contribuyente, cédula 1.016.086.781")
        self.assertIn("cédula", tipos(h))

    def test_cedula_de_cuatro_grupos_sin_contexto(self):
        # Una cédula tiene cuatro grupos; un monto en pesos casi nunca.
        h = escanear_texto("aparece 1.016.086.781 sin más")
        self.assertIn("cédula", tipos(h))

    def test_cedula_en_columna_de_csv_sin_contexto_en_la_fila(self):
        """La regresión que motivó el rediseño.

        El encabezado 'documento' está en la línea 1 y las cédulas en las
        filas siguientes. Buscar contexto por línea nunca las encontraba.
        """
        csv = ("nombre,documento,ciudad\n"
               "PEREZ GOMEZ JUAN,19.122.816,Medellin\n"
               "RIOS LUZ MERY,52.847.113,Bogota\n")
        h = escanear_texto(csv, sufijo=".csv")
        self.assertGreaterEqual(len(altas(h)), 2, f"cédulas no detectadas: {h}")

    def test_columna_de_montos_no_dispara(self):
        """La otra cara: una columna monto_cop de un ledger."""
        csv = ("fecha,descripcion,monto_cop\n"
               "2025-03-14,Pago cliente,15200000\n"
               "2025-04-15,Pago cliente,15850000\n")
        h = escanear_texto(csv, sufijo=".csv")
        self.assertEqual(altas(h), [], f"montos del ledger con confianza alta: {h}")

    def test_cedula_precedida_de_signo_peso(self):
        """Anteponer $ no puede hacer desaparecer un identificador."""
        h = escanear_texto("Cedula: $1.016.086.781")
        self.assertTrue(altas(h), "el prefijo $ ocultó la cédula")

    def test_nombre_en_mayusculas_sin_tildes(self):
        """Como sale en un formulario DIAN o en un extracto bancario."""
        h = escanear_texto("Titular: PEREZ GOMEZ LUZ MERY", ["perez"])
        self.assertIn("nombre del perfil", tipos(h))

    def test_cedula_sin_separadores(self):
        h = escanear_texto("documento 1016086781")
        self.assertTrue({"cédula o documento", "cuenta bancaria"} & tipos(h))

    def test_nit(self):
        h = escanear_texto("NIT 900.123.456-7")
        self.assertIn("NIT", tipos(h))

    def test_tarjeta_valida_luhn(self):
        h = escanear_texto("tarjeta 4111 1111 1111 1111")
        self.assertIn("tarjeta", tipos(h))

    def test_tarjeta_invalida_no_se_reporta_como_tarjeta(self):
        h = escanear_texto("secuencia 1234 5678 9012 3456")
        self.assertNotIn("tarjeta", tipos(h))

    def test_correo(self):
        h = escanear_texto("escríbeme a persona@ejemplo.com")
        self.assertIn("correo", tipos(h))

    def test_telefono_colombiano(self):
        h = escanear_texto("mi celular +57 300 1234567")
        self.assertIn("teléfono", tipos(h))

    def test_direccion(self):
        h = escanear_texto("vivo en Calle 45 #12-34")
        self.assertIn("dirección", tipos(h))

    def test_ruta_de_usuario(self):
        h = escanear_texto("el archivo está en /Users/fulanito/documentos")
        self.assertIn("ruta de usuario", tipos(h))

    def test_nombre_del_perfil(self):
        h = escanear_texto("el pago lo hizo Fulanito el martes", ["Fulanito"])
        self.assertIn("nombre del perfil", tipos(h))


class TestNoRuido(unittest.TestCase):
    """Falsos positivos: lo que NO puede disparar la alarma."""

    def test_montos_en_pesos(self):
        h = escanear_texto("La deducción vale $3.585.528 y el tope $66.730.660.")
        self.assertEqual(altas(h), [], f"montos con confianza alta: {h}")

    def test_aritmetica_en_prosa(self):
        h = escanear_texto(
            "Exención del 25% sobre 90.000.000 = 22.500.000, "
            "renta líquida 67.500.000."
        )
        self.assertEqual(altas(h), [], f"aritmética con confianza alta: {h}")

    def test_cifras_en_uvt(self):
        h = escanear_texto("El tope conjunto es de 1.340 UVT y la exención 790 UVT.")
        self.assertEqual(altas(h), [])

    def test_referencias_normativas(self):
        h = escanear_texto(
            "Art. 336 num. 4 ET, Decreto 1625 de 2016, Ley 2277 de 2022, "
            "Resolución DIAN 000193 de 2024."
        )
        self.assertEqual(altas(h), [])

    def test_anios_y_fechas(self):
        h = escanear_texto("Del 2025 al 2026, vence el 2026-10-26.")
        self.assertEqual(altas(h), [])

    def test_montos_en_moneda_extranjera(self):
        h = escanear_texto("Recibió 3800.00 USD y 1.234,56 EUR.")
        self.assertEqual(altas(h), [])


class TestRepositorio(unittest.TestCase):
    """El repositorio publicado no puede contener datos personales."""

    def test_repo_limpio(self):
        globs = esc.globs_ignorados(RAIZ, estricto=False)
        sucios = []
        for archivo in RAIZ.rglob("*"):
            if not archivo.is_file() or archivo.suffix.lower() in esc.BINARIAS:
                continue
            if esc.IGNORAR_DIRS & set(archivo.parts):
                continue
            relativo = archivo.relative_to(RAIZ)
            if esc.esta_ignorado(relativo, globs):
                continue
            hallazgos = [h for h in esc.escanear(archivo, []) if h[3] == "alta"]
            if hallazgos:
                sucios.append((str(relativo), hallazgos[:3]))
        self.assertEqual(sucios, [], f"PII en el repositorio: {sucios}")

    def test_privacidadignore_no_puede_desactivar_el_escaner(self):
        """Un PR con una línea '*' no puede poner CI en verde."""
        import tempfile as _tf
        with _tf.TemporaryDirectory() as d:
            raiz = Path(d)
            (raiz / esc.ARCHIVO_IGNORADOS).write_text("*\n**\nfoo.md\n")
            globs = esc.globs_ignorados(raiz, estricto=False)
            self.assertEqual(globs, ["foo.md"])

    def test_modo_estricto_ignora_el_archivo_de_exclusiones(self):
        self.assertEqual(esc.globs_ignorados(RAIZ, estricto=True), [])


if __name__ == "__main__":
    unittest.main()
