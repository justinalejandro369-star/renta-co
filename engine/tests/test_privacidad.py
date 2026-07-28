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


def ignorados_por_git(rutas: list[Path]) -> set[str]:
    """Los que git no publicaría. Vacío si git no está disponible.

    Sin esto, el test dependía de si alguien había corrido `calcular --csv`
    antes: `expediente.ejemplo/03-analisis/escenarios.csv` es un artefacto
    generado, está en .gitignore y nunca se publica, pero el escaneo del
    árbol lo veía igual. Un test que falla según qué comandos corriste antes
    enseña a ignorar los fallos, que es exactamente lo contrario de lo que
    hace falta acá.
    """
    import shutil
    import subprocess

    if not shutil.which("git") or not rutas:
        return set()
    try:
        r = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=RAIZ, input="\n".join(str(x) for x in rutas),
            capture_output=True, text=True,
        )
    except OSError:
        return set()
    return {linea for linea in r.stdout.splitlines() if linea}


class TestRepositorio(unittest.TestCase):
    """El repositorio publicado no puede contener datos personales."""

    def test_repo_limpio(self):
        globs = esc.globs_ignorados(RAIZ, estricto=False)
        candidatos = [
            a.relative_to(RAIZ) for a in RAIZ.rglob("*")
            if a.is_file() and a.suffix.lower() not in esc.BINARIAS
            and not esc.IGNORAR_DIRS & set(a.parts)
        ]
        fuera_de_git = ignorados_por_git(candidatos)
        sucios = []
        for archivo in RAIZ.rglob("*"):
            if not archivo.is_file() or archivo.suffix.lower() in esc.BINARIAS:
                continue
            if esc.IGNORAR_DIRS & set(archivo.parts):
                continue
            relativo = archivo.relative_to(RAIZ)
            if str(relativo) in fuera_de_git:
                continue
            if esc.esta_ignorado(relativo, globs):
                continue
            hallazgos = [h for h in esc.escanear(archivo, []) if h[3] == "alta"]
            if hallazgos:
                sucios.append((str(relativo), hallazgos[:3]))
        self.assertEqual(sucios, [], f"PII en el repositorio: {sucios}")

    def test_privacidadignore_no_puede_desactivar_el_escaner(self):
        """Un PR no puede poner CI en verde vaciando el escaneo.

        La primera versión rechazaba una lista literal de globs ('*', '**',
        …). No protegía nada: '?*' y '[a-z]*' hacen exactamente lo mismo y no
        estaban en ninguna lista. Ahora se rechaza por EFECTO —cuántos
        archivos deja fuera cada glob— que es lo que importa y no se puede
        rodear cambiando la sintaxis.
        """
        archivos = [Path(f"dir/archivo{i}.md") for i in range(10)]

        for glob in ("*", "**", "?*", "[a-zA-Z0-9._-]*", "*[!x]*", "*.md"):
            quedan, avisos = esc.aplicar_ignorados(archivos, [glob])
            self.assertEqual(len(quedan), len(archivos),
                             f"el glob {glob!r} vació el escaneo")
            self.assertTrue(avisos, f"el glob {glob!r} no produjo aviso")
            self.assertIn("RECHAZA", avisos[0])

    def test_privacidadignore_si_permite_excepciones_puntuales(self):
        """Lo que sí es su propósito: dejar fuera unos pocos archivos."""
        archivos = [Path(f"dir/archivo{i}.md") for i in range(10)]
        quedan, avisos = esc.aplicar_ignorados(archivos, ["dir/archivo3.md"])
        self.assertEqual(len(quedan), 9)
        self.assertEqual(avisos, [])

    def test_modo_estricto_ignora_el_archivo_de_exclusiones(self):
        self.assertEqual(esc.globs_ignorados(RAIZ, estricto=True), [])


class TestUmbralAcumulado(unittest.TestCase):
    """Medir cada glob contra el total dejaba pasar varios globs pequeños
    que juntos apagaban el escáner."""

    def _archivos(self, n=100, dirs=4):
        return [Path(f"dir{i % dirs}/a{i}.txt") for i in range(n)]

    def test_varios_globs_pequenos_no_apagan_el_escaner(self):
        archivos = self._archivos()
        quedan, avisos = esc.aplicar_ignorados(
            archivos, ["dir0/*", "dir1/*", "dir2/*", "dir3/*"]
        )
        self.assertGreater(len(quedan), len(archivos) * 0.5,
                           "cuatro globs del 25% vaciaron el escaneo")
        self.assertGreaterEqual(len(avisos), 3)

    def test_excepciones_puntuales_siguen_funcionando(self):
        archivos = self._archivos()
        quedan, avisos = esc.aplicar_ignorados(
            archivos, ["dir0/a0.txt", "dir1/a1.txt"]
        )
        self.assertEqual(len(quedan), 98)
        self.assertEqual(avisos, [])


class TestColumnasConComillas(unittest.TestCase):
    """Una coma dentro de comillas corría todas las columnas de la derecha.

    Con eso la columna de montos dejaba de reconocerse y sus cifras de ocho
    dígitos se reportaban como documento de confianza ALTA. Es un falso
    positivo del escáner sobre la salida del propio motor, y el modo de
    fallo que el docstring del módulo llama el más caro: la gente deja de
    leerlo.
    """

    def test_los_rangos_respetan_las_comillas(self):
        linea = '"= SALDO (positivo, negativo)",3656962,11599309,'
        rangos = esc.rangos_de_celdas(linea, ",")
        self.assertEqual(len(rangos), 4)
        self.assertEqual(linea[rangos[1][0]:rangos[1][1]], "3656962")
        self.assertEqual(linea[rangos[2][0]:rangos[2][1]], "11599309")

    def test_una_columna_de_dinero_no_se_desplaza_por_una_coma_citada(self):
        texto = ('concepto,ruta_A_costos,ruta_B_exenta_25\n'
                 '"= SALDO (positivo a pagar, negativo a favor)",3656962,11599309\n')
        self.assertEqual(altas(escanear_texto(texto, [], ".csv")), [])

    def test_y_una_cedula_en_su_columna_sigue_rompiendo_el_build(self):
        """El arreglo no puede volverse una puerta: si la celda desplazada
        fuera de verdad un documento, tiene que seguir saliendo."""
        texto = ('concepto,documento,ruta_A_costos\n'
                 '"pago a tercero, con nota",1016086781,3656962\n')
        self.assertIn("cédula o documento", tipos(escanear_texto(texto, [], ".csv")))


class TestColumnasQueEscribeLaHerramienta(unittest.TestCase):
    """El escáner no puede ser ciego a su propia salida.

    El ledger guarda en `contraparte` lo que el banco traía en `documento`.
    Como `contraparte` no estaba en CONTEXTO, la MISMA cédula salía de
    confianza ALTA antes de importar y BAJA después: la herramienta
    degradaba justamente la PII que ella escribe.
    """

    ENCABEZADO = ("fecha,descripcion,contraparte,moneda,monto_origen,trm,"
                  "monto_cop,categoria,fuente\n")

    def test_una_cedula_en_la_columna_contraparte_es_de_confianza_alta(self):
        texto = self.ENCABEZADO + "2025-03-14,PAGO,79.483.921,COP,1500000.00,1.00,1500000,costo,b.csv\n"
        self.assertTrue(altas(escanear_texto(texto, [], ".csv")),
                        "el ledger degradó su propia PII a confianza baja")

    def test_da_igual_como_se_llame_la_columna_de_documento(self):
        """La clase: los tres nombres con los que puede llegar el mismo dato."""
        for columna in ("documento", "contraparte", "beneficiario"):
            texto = (f"fecha,descripcion,{columna},monto_cop\n"
                     f"2025-03-14,PAGO,79.483.921,1500000\n")
            self.assertTrue(
                altas(escanear_texto(texto, [], ".csv")),
                f"una cédula bajo el encabezado {columna!r} no rompe el build",
            )

    def test_la_columna_de_monto_sigue_siendo_de_monto(self):
        """El arreglo no puede llenar el reporte de ruido: los montos del
        ledger tienen la misma forma y no son documento de nadie."""
        texto = self.ENCABEZADO + "2025-03-14,PAGO,,COP,1500000.00,1.00,15000000,costo,b.csv\n"
        self.assertEqual(altas(escanear_texto(texto, [], ".csv")), [])


class TestEnmascarar(unittest.TestCase):
    """La función que evita que el REPORTE del escáner sea él mismo una fuga.

    El escáner imprime lo que encontró. Si `enmascarar` devuelve el número
    completo, el informe que se pega en un issue publica exactamente el dato
    que el escáner existe para no publicar. No tenía una sola aserción.
    """

    def test_una_cedula_nunca_sale_completa(self):
        for cedula in ("1.016.086.781", "1016086781", "19.122.816", "79483921"):
            salida = esc.enmascarar(cedula)
            self.assertNotEqual(salida, cedula)
            self.assertIn("X", salida)
            digitos = "".join(c for c in salida if c.isdigit())
            original = "".join(c for c in cedula if c.isdigit())
            self.assertLess(len(digitos), len(original),
                            f"{cedula!r} salió con todos sus dígitos: {salida!r}")

    def test_deja_lo_justo_para_reconocer_el_dato(self):
        """Sirve para ubicarlo en el archivo, no para reconstruirlo."""
        self.assertEqual(esc.enmascarar("1016086781"), "1XXXXXX781")

    def test_un_correo_no_sale_ni_con_el_usuario_ni_con_el_dominio(self):
        """El dominio también identifica: "@bufete-gomez-abogados.com.co"
        señala a una persona tan bien como el usuario. Se conserva el TLD,
        que es lo único que ayuda a ubicar el hallazgo sin delatarlo."""
        salida = esc.enmascarar("juan.perez@bufete-gomez.com.co")
        self.assertNotIn("juan.perez", salida)
        self.assertNotIn("bufete-gomez", salida)
        self.assertTrue(salida.endswith(".co"))

    def test_una_ruta_de_usuario_no_sale_con_el_nombre(self):
        """El patrón "ruta de usuario" existe para atrapar el nombre de la
        cuenta del sistema, y `enmascarar` solo tapaba dígitos: lo alfabético
        —o sea el dato— salía íntegro en el reporte."""
        for ruta, nombre in (("/Users/fulanito", "fulanito"),
                             ("/home/mariafernanda", "mariafernanda"),
                             (r"C:\Users\JuanPerez", "JuanPerez")):
            salida = esc.enmascarar(ruta)
            self.assertNotIn(nombre, salida, f"{ruta!r} salió como {salida!r}")

    def test_una_direccion_no_sale_con_el_barrio(self):
        salida = esc.enmascarar("Calle 100 #45-20 Apto 301 Barrio Chapinero")
        self.assertNotIn("Chapinero", salida)
        # El vocabulario de vía sí se conserva: sin él, el hallazgo no se
        # puede ubicar en el archivo.
        self.assertIn("Calle", salida)

    def test_los_numeros_cortos_se_borran_enteros(self):
        """Con cuatro dígitos o menos, dejar el primero y los tres últimos
        sería dejarlo entero."""
        self.assertEqual(esc.enmascarar("1234"), "XXXX")


class TestHookDePreCommit(unittest.TestCase):
    """`--staged` de punta a punta, con git de verdad.

    El hook que anuncian PRIVACY.md, commands/setup.md y
    skills/renta-privacidad era un no-op: `bin/renta` hacía `cd` a la raíz
    del plugin y `git diff --cached` corría contra el repositorio de
    renta-co, no contra el del usuario. Con una cédula en el índice decía
    "No hay archivos que escanear" y salía 0.

    Se prueba por el LANZADOR, no llamando al script: `AGENTS.md` manda usar
    `bin/renta` como interfaz única, y el bug vivía justo en la diferencia.
    """

    def setUp(self):
        import shutil
        import subprocess

        if not shutil.which("git"):
            self.skipTest("git no disponible")
        self.repo = Path(tempfile.mkdtemp()) / "repo-usuario"
        self.repo.mkdir()
        for orden in (["init", "-q", "."],
                      ["config", "user.email", "t@t"],
                      ["config", "user.name", "t"]):
            subprocess.run(["git", *orden], cwd=self.repo, check=True,
                           capture_output=True)

    def _correr(self, *args):
        import subprocess

        return subprocess.run(
            [str(RAIZ / "bin" / "renta"), "privacidad", *args],
            cwd=self.repo, capture_output=True, text=True,
        )

    def test_una_cedula_en_el_indice_rompe_el_commit(self):
        import subprocess

        (self.repo / "datos.txt").write_text(
            "cedula: 1.016.086.781\n", encoding="utf-8")
        subprocess.run(["git", "add", "datos.txt"], cwd=self.repo, check=True,
                       capture_output=True)
        r = self._correr("--staged")
        self.assertEqual(r.returncode, 1, f"salió 0 con una cédula staged:\n{r.stdout}")
        self.assertIn("datos.txt", r.stdout)

    def test_el_indice_limpio_deja_pasar_el_commit(self):
        import subprocess

        (self.repo / "notas.md").write_text(
            "El tope conjunto es de 1.340 UVT.\n", encoding="utf-8")
        subprocess.run(["git", "add", "notas.md"], cwd=self.repo, check=True,
                       capture_output=True)
        r = self._correr("--staged")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_lo_que_se_revisa_es_el_blob_y_no_el_disco(self):
        """`git add` con la cédula y después limpiar el archivo en disco: lo
        que se va a commitear sigue siendo el blob sucio."""
        import subprocess

        archivo = self.repo / "datos.txt"
        archivo.write_text("cedula: 1.016.086.781\n", encoding="utf-8")
        subprocess.run(["git", "add", "datos.txt"], cwd=self.repo, check=True,
                       capture_output=True)
        archivo.write_text("sin datos\n", encoding="utf-8")
        r = self._correr("--staged")
        self.assertEqual(r.returncode, 1, f"leyó el disco y no el índice:\n{r.stdout}")

    def test_un_nombre_con_tilde_no_deja_ciego_al_hook(self):
        """`git diff --cached --name-only` entrecomilla y escapa los nombres
        no ASCII, así que "cédula.csv" llegaba como "c\\303\\251dula.csv", el
        `git show` fallaba, el except se lo tragaba y el hook decía "no hay
        nada en el índice" y salía 0. En Colombia los nombres con tilde y con
        ñ son el caso normal, no el raro."""
        import subprocess

        for nombre in ("cédula.csv", "nómina-empleados.csv", "año 2025.csv"):
            archivo = self.repo / nombre
            archivo.write_text("cedula: 1016086781\n", encoding="utf-8")
            subprocess.run(["git", "add", nombre], cwd=self.repo, check=True,
                           capture_output=True)
            r = self._correr("--staged")
            self.assertEqual(r.returncode, 1,
                             f"{nombre!r} salió 0 con una cédula dentro:\n{r.stdout}")
            subprocess.run(["git", "rm", "-q", "--cached", nombre], cwd=self.repo,
                           check=True, capture_output=True)

    def test_lo_que_no_se_puede_leer_detiene_el_commit(self):
        """Un PDF, un XLSX o una foto de la cédula en el índice imprimían
        "revísalo a mano" y salían 0: el hook aprobando lo que no miró."""
        import subprocess

        for nombre, contenido in (("extracto.pdf", b"%PDF-1.4 falso\n"),
                                  ("soporte.xlsx", b"PK\x03\x04falso"),
                                  ("cedula.png", b"\x89PNG\r\n\x1a\n")):
            (self.repo / nombre).write_bytes(contenido)
            subprocess.run(["git", "add", "-f", nombre], cwd=self.repo, check=True,
                           capture_output=True)
            r = self._correr("--staged")
            self.assertEqual(r.returncode, 1,
                             f"{nombre} pasó el hook sin poder leerse:\n{r.stdout}")
            subprocess.run(["git", "rm", "-q", "--cached", nombre], cwd=self.repo,
                           check=True, capture_output=True)

    def test_la_cedula_en_el_NOMBRE_del_archivo_rompe_el_commit(self):
        """Un nombre de archivo con la cédula queda en el árbol de GitHub,
        en el diff y en la URL, indexable, aunque el contenido esté limpio.
        Así los nombra un banco colombiano."""
        import subprocess

        nombre = "extracto-cc-1016086781-juan-perez.txt"
        (self.repo / nombre).write_text("sin datos\n", encoding="utf-8")
        subprocess.run(["git", "add", nombre], cwd=self.repo, check=True,
                       capture_output=True)
        r = self._correr("--staged")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("NOMBRE DEL ARCHIVO", r.stdout)

    def test_fuera_de_un_repositorio_no_finge_que_reviso(self):
        import shutil

        vacio = Path(tempfile.mkdtemp())
        shutil.rmtree(self.repo / ".git")
        r = self._correr("--staged")
        self.assertNotEqual(r.returncode, 0,
                            "salió 0 sin haber podido leer el índice")
        del vacio


if __name__ == "__main__":
    unittest.main()
