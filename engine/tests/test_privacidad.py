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

    def test_ninguna_ruta_de_esta_maquina_quedo_en_el_repo(self):
        """La ruta HOME de quien escribe no puede terminar publicada.

        Este test existe porque pasó, en la sesión que escribió el test de
        `enmascarar`: se documentó el comportamiento con un ejemplo real
        —`/Users/<usuario>`— en el docstring de la función y en el test. Los
        dos archivos están en `.privacidadignore`, así que el escaneo por
        defecto no los mira, y CI no corre `--estricto` porque el modo
        estricto sale 1 a propósito (los tests traen cédulas de prueba).

        O sea: el punto ciego exacto que la verificación adversarial había
        reportado, ocupado en menos de una hora por quien lo estaba
        arreglando. La guarda tiene que ser específica y correr SIEMPRE, no
        depender de que alguien se acuerde de pasar una bandera.

        Se compara contra el HOME de la máquina actual, que es lo único que
        distingue "ejemplo ficticio" de "mi computador".
        """
        import os

        usuario = Path.home().name
        if not usuario or len(usuario) < 3:
            self.skipTest("no hay un nombre de usuario contra el cual comparar")

        # Los ejemplos ficticios del repo son intencionales y se listan acá
        # para que un usuario que de verdad se llame así no rompa el build.
        FICTICIOS = {"fulanito", "usuario", "user", "runner", "home", "root"}
        if usuario.lower() in FICTICIOS:
            self.skipTest(f"el usuario de esta máquina ({usuario}) es un ficticio")

        sucios = []
        for archivo in RAIZ.rglob("*"):
            if not archivo.is_file() or archivo.suffix.lower() in esc.BINARIAS:
                continue
            if esc.IGNORAR_DIRS & set(archivo.parts):
                continue
            try:
                texto = archivo.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for n, linea in enumerate(texto.splitlines(), start=1):
                if usuario in linea:
                    sucios.append(f"{archivo.relative_to(RAIZ)}:{n}")
        self.assertEqual(
            sucios, [],
            f"el usuario de esta máquina aparece en el repo (usa un nombre "
            f"ficticio como 'fulanito'): {sucios[:5]}",
        )
        del os

    # El filtro de formas y el recorrido viven en el escáner, no acá. Copiar
    # la lógica al test es la misma clase de divergencia que ya costó una
    # ronda: dos copias, se actualiza una, y la que queda vieja es la que
    # decide si el build pasa.
    FORMAS_ESPERABLES = esc.FORMAS_DE_LABORATORIO
    INVENTARIO = RAIZ / "scripts" / "privacidad-esperado.txt"

    def test_lo_excluido_esta_inventariado_y_no_crece_solo(self):
        """La compuerta que faltaba sobre `.privacidadignore`.

        No se puede exigir que `--estricto` salga 0: los archivos excluidos
        traen cédulas de PRUEBA a propósito, y por eso CI nunca lo corrió
        como gate. Pero eso los dejó sin NINGUNA revisión automática, y ahí
        fue exactamente donde se coló la ruta HOME real (ver el test de
        arriba).

        La salida no es exigir cero: es exigir que lo que hay esté
        INVENTARIADO. Las formas que un caso de prueba produce de por sí
        —cédulas, cuentas, NIT— se filtran; lo demás —correos, direcciones,
        teléfonos, rutas de usuario, IBAN— queda congelado en
        `scripts/privacidad-esperado.txt`. Cualquier línea nueva rompe el
        build y obliga a mirarla.

        Regenerarlo es una decisión visible en el diff:

            python3 scripts/escanear_privacidad.py --inventario > \\
                scripts/privacidad-esperado.txt

        Corre SIEMPRE, sin bandera, en las tres versiones de Python de CI.
        """
        self.assertTrue(
            self.INVENTARIO.exists(),
            f"falta {self.INVENTARIO.relative_to(RAIZ)}; genéralo con "
            f"`python3 scripts/escanear_privacidad.py --inventario`",
        )
        esperado = [
            l for l in self.INVENTARIO.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")
        ]
        obtenido = esc.inventario_de_lo_excluido(RAIZ)

        nuevos = [l for l in obtenido if l not in esperado]
        self.assertEqual(
            nuevos, [],
            "un archivo excluido de .privacidadignore trae un dato que el "
            "inventario no conocía. .privacidadignore silencia los montos y "
            "las cédulas de laboratorio, no esto. Míralo ANTES de regenerar "
            f"el inventario: {nuevos[:5]}",
        )
        sobran = [l for l in esperado if l not in obtenido]
        self.assertEqual(
            sobran, [],
            "el inventario tiene líneas que ya no existen. Regenéralo para "
            f"que siga sirviendo de línea base: {sobran[:5]}",
        )

    def test_el_inventario_es_capaz_de_fallar(self):
        """Una aserción que no puede fallar no es una aserción. Se comprueba
        contra el mecanismo real —`escanear` sobre un archivo de verdad— y no
        contra una lista inventada."""
        ruta = Path(tempfile.mkdtemp()) / "excluido.py"
        ruta.write_text(
            '# ejemplo: escribeme@bufete-ficticio.com.co\n', encoding="utf-8"
        )
        etiquetas = {
            e for _, e, _, c in esc.escanear(ruta)
            if c == "alta" and e not in self.FORMAS_ESPERABLES
        }
        self.assertIn("correo", etiquetas)
        self.assertNotIn(
            "correo", {l.split(" · ")[1] for l in
                       self.INVENTARIO.read_text(encoding="utf-8").splitlines()
                       if " · " in l and "test_privacidad" not in l},
            "si esa etiqueta ya estuviera inventariada fuera de los tests, "
            "el inventario no probaría nada",
        )


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


class TestPatronesQueFaltaban(unittest.TestCase):
    """Formas de identificador colombiano que el escáner no veía."""

    def test_una_cedula_de_extranjeria_se_detecta(self):
        """Son de 6 o 7 dígitos, y `\\d{8,11}` las dejaba pasar enteras. Un
        extranjero residente fiscal en Colombia es un caso de uso completo
        del producto y no tenía cobertura."""
        for texto in ("cedula de extranjeria: 791234",
                      "CE 1234567", "documento 791234"):
            self.assertTrue(altas(escanear_texto(texto)),
                            f"{texto!r} no se detectó")

    def test_una_corrida_larga_de_digitos_se_detecta(self):
        """La skill promete cuentas de 9 a 20 dígitos; `\\d{8,11}` cortaba
        en 11 y una de 12+ salía intacta."""
        self.assertIn("cuenta o identificador largo",
                      tipos(escanear_texto("cuenta 12345678901234")))

    def test_un_iban_se_detecta(self):
        """El repo trae adaptador de Wise, y Wise entrega IBAN."""
        self.assertIn("IBAN", tipos(escanear_texto("IBAN ES9121000418450200051332")))

    def test_un_fijo_colombiano_se_detecta(self):
        """Desde 2022 los fijos son de 10 dígitos y empiezan por 60X. El
        patrón de teléfono solo anclaba en los celulares (3XX)."""
        for texto in ("Tel 601 745 8900", "(604) 444 5566", "+57 605 3334455"):
            self.assertTrue(altas(escanear_texto(texto)), f"{texto!r} no se detectó")

    def test_los_numeros_de_norma_no_son_ruido_nuevo(self):
        """El radicado de un concepto DIAN tiene forma de cédula. Ampliar los
        patrones no puede llenar el reporte de citas normativas: un escáner
        que grita en cada línea deja de leerse."""
        for texto in ("DIAN, Concepto 100202208-1621 de 2023",
                      "Resolución DIAN 000238 del 15 de diciembre de 2025",
                      "la Res. 000165 de 2023 no la derogó",
                      "Decreto 1625 de 2016 art. 1.6.1.13.2.7",
                      "El tope conjunto es de 1.340 UVT"):
            self.assertEqual(altas(escanear_texto(texto)), [],
                             f"{texto!r} produjo un falso positivo")


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

    def test_privacidadignore_no_puede_apagar_el_hook(self):
        """Ese archivo existe para bajarle el ruido a un escaneo informativo
        del árbol de trabajo. Lo que está en el ÍNDICE es otra cosa: es
        exactamente lo que se va a publicar. Una línea plausible —la que
        cualquiera escribiría pensando «eso ya está gitignored»— lo apagaba
        entero, y el límite acumulado del 40% no dispara porque el glob es
        legítimamente estrecho."""
        import subprocess

        (self.repo / ".privacidadignore").write_text("datos/*\n", encoding="utf-8")
        (self.repo / "datos").mkdir()
        (self.repo / "datos" / "cliente.csv").write_text(
            "cedula: 1016086781\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True,
                       capture_output=True)
        r = self._correr("--staged")
        self.assertEqual(r.returncode, 1,
                         f".privacidadignore apagó el hook:\n{r.stdout}")

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


class TestNombresDelPerfil(unittest.TestCase):
    """`--perfil` era inusable por ruido: sobre el propio ejemplo del repo
    extraía los tokens `art`, `trm`, `usd`, `inicial` y `reconocimiento` y
    reportaba 12 falsos positivos ALTA en el README.

    La causa: recorría cualquier clave que empatara `nombre|titular|…` sin
    mirar dónde estaba, y `perfil.toml` usa `nombre` para los ACTIVOS del
    patrimonio. Como es la ÚNICA detección de nombres propios que existe, el
    ruido no la degradaba: la apagaba.
    """

    def _perfil(self, texto: str) -> Path:
        ruta = Path(tempfile.mkdtemp()) / "perfil.toml"
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def test_el_nombre_de_un_activo_no_es_el_nombre_de_una_persona(self):
        ruta = self._perfil(
            '[contribuyente]\nnombre = "Yamile Restrepo"\n'
            '[[patrimonio.activos]]\n'
            'nombre = "Reconocimiento inicial USD segun art. 288"\n'
            'valor = 350000000\n'
        )
        tokens = esc.nombres_del_perfil(ruta)
        self.assertIn("yamile", tokens)
        self.assertIn("restrepo", tokens)
        for ruido in ("reconocimiento", "inicial", "usd", "art", "segun"):
            self.assertNotIn(ruido, tokens, f"'{ruido}' es vocabulario, no un nombre")

    def test_el_ejemplo_del_repo_no_produce_ni_un_token_de_vocabulario(self):
        """La aserción sobre el archivo REAL, no sobre uno de laboratorio:
        es el que produjo los 94 falsos positivos del hallazgo."""
        tokens = esc.nombres_del_perfil(RAIZ / "expediente.ejemplo" / "perfil.toml")
        self.assertTrue(tokens, "el ejemplo tiene que aportar nombres, o la "
                                "detección queda muerta en el flujo real")
        for ruido in ("trm", "usd", "art", "cop", "banco", "wallet",
                      "inmueble", "vehiculo", "avaluo"):
            self.assertNotIn(ruido, tokens)

    def test_los_nombres_de_las_otras_personas_tambien_se_recogen(self):
        ruta = self._perfil(
            '[personas]\n'
            'madre = "Amparo Osorno"\n'
            'contratistas = ["Nicolás Betancur", "Sebastián Zuluaga"]\n'
        )
        tokens = esc.nombres_del_perfil(ruta)
        for esperado in ("amparo", "osorno", "nicolas", "betancur",
                         "sebastian", "zuluaga"):
            self.assertIn(esperado, tokens)

    def test_una_nota_dentro_de_una_seccion_de_personas_no_cuenta(self):
        """Las dos condiciones a la vez —sección de personas Y clave de
        persona— y no una de las dos."""
        ruta = self._perfil(
            '[contribuyente]\n'
            'nombre = "Yamile Restrepo"\n'
            'nota = "verificar residencia fiscal antes de declarar"\n'
        )
        tokens = esc.nombres_del_perfil(ruta)
        self.assertIn("yamile", tokens)
        self.assertNotIn("residencia", tokens)
        self.assertNotIn("verificar", tokens)

    def test_una_clave_de_persona_fuera_de_su_seccion_tampoco(self):
        ruta = self._perfil(
            '[[patrimonio.pasivos]]\n'
            'titular = "Banco Ficticio de Colombia"\n'
            'valor = 48000000\n'
        )
        self.assertEqual(esc.nombres_del_perfil(ruta), [])

    def test_un_nombre_del_perfil_sigue_rompiendo_el_build(self):
        """El arreglo del ruido no puede haber apagado la detección."""
        hallazgos = escanear_texto(
            "El memo lo firma Yamile Restrepo el 15 de octubre.",
            nombres=["yamile", "restrepo"],
        )
        altas = [h for h in hallazgos if h[3] == "alta"]
        self.assertEqual(len(altas), 2, hallazgos)
        self.assertTrue(all(h[1] == "nombre del perfil" for h in altas))

    def test_el_nombre_sale_enmascarado_en_el_reporte(self):
        hallazgos = escanear_texto("Firma: Yamile", nombres=["yamile"])
        self.assertEqual(hallazgos[0][2], "y*****")


class TestPatronesDeLaRonda7(unittest.TestCase):
    """Lo que seguía escapando después de la ronda 6.

    Todos se reprodujeron antes de escribir el patrón: los siete salían con
    cero hallazgos.
    """

    def test_una_cedula_rota_por_un_salto_de_linea(self):
        """Lo que produce copiar de un PDF a dos columnas. Cada mitad por
        separado no es nada: `1.016.086.` y `781`."""
        h = escanear_texto("Documento:\n1.016.086.\n781\n")
        rotos = [x for x in h if "roto en dos líneas" in x[1]]
        self.assertTrue(rotos, h)
        self.assertEqual(rotos[0][3], "alta")
        # Enmascarado con la misma regla que el resto: primer dígito y los
        # tres últimos, para poder reconocerlo sin publicarlo.
        self.assertNotIn("016", rotos[0][2], "salió sin enmascarar")
        self.assertIn("X", rotos[0][2])

    def test_un_monto_partido_no_cruza_lineas(self):
        """La otra cara, y el ajuste que costó medirlo.

        Correr TODOS los patrones sobre cada par de líneas llevó los
        hallazgos de confianza baja de 187 a 869 sobre este mismo repo: en
        un documento tributario, una fila que termina en dígito seguida de
        otra que empieza en dígito es el contenido normal. Un contador de
        ruido que se multiplica por cinco deja de significar algo, y esa es
        la forma conocida de apagar esta herramienta.

        Solo cruzan líneas las formas FUERTES: cuatro grupos de tres, ocho a
        once dígitos corridos, NIT. Un monto de tres grupos partido en dos
        casi nunca es una cédula.
        """
        h = escanear_texto("Total\n90.000.\n000 pesos\n")
        self.assertEqual([x for x in h if "roto en dos líneas" in x[1]], [], h)

    def test_una_forma_fuerte_partida_sin_contexto_queda_en_baja(self):
        """Pero sin palabra de contexto no rompe el build: cuatro grupos de
        tres también puede ser un monto de mil millones."""
        h = escanear_texto("Total\n1.016.086.\n781\n")
        rotos = [x for x in h if "roto en dos líneas" in x[1]]
        self.assertTrue(rotos, h)
        self.assertEqual(rotos[0][3], "baja")

    def test_lo_que_cabe_en_una_linea_no_se_reporta_dos_veces(self):
        h = escanear_texto("cédula 1.016.086.781\nsigue el texto\n")
        self.assertEqual([x for x in h if "roto en dos líneas" in x[1]], [])

    def test_una_direccion_sin_verbo_de_via(self):
        """Media Colombia urbana vive en un `Apto 502 Torre 3`, y el patrón
        anclaba en «calle» o «carrera»."""
        self.assertIn("dirección (unidad)",
                      tipos(escanear_texto("Vive en Apto 502 Torre 3.")))
        self.assertIn("dirección (unidad)",
                      tipos(escanear_texto("Entrega en Bloque 4 Apartamento 201")))

    def test_una_direccion_rural(self):
        self.assertIn("dirección (rural)",
                      tipos(escanear_texto("La finca queda en Km 5 vía La Calera.")))
        self.assertIn("dirección (rural)",
                      tipos(escanear_texto("Predio en Vereda El Salado, Rionegro.")))

    def test_el_tope_conjunto_no_es_una_direccion(self):
        """`conjunto` y `urbanización` se probaron en el patrón de unidad y
        se sacaron: no llevan número de casa, y «tope conjunto 40%» aparece
        en cada documento de este repo."""
        h = escanear_texto("dentro del tope conjunto 40% / 1.340 UVT")
        self.assertEqual(altas(h), [], h)

    def test_un_correo_deletreado(self):
        """Como lo escribe quien sabe que hay un escáner, o quien lo dicta
        por teléfono."""
        self.assertIn("correo deletreado",
                      tipos(escanear_texto("persona arroba ejemplo punto com")))
        self.assertIn("correo deletreado",
                      tipos(escanear_texto("contacto at bufete dot com")))

    def test_arroba_o_punto_por_separado_no_alcanzan(self):
        """Exige las DOS palabras: cada una por su lado es vocabulario
        corriente y llenaría el reporte de ruido."""
        for texto in ("el punto de equilibrio de la actividad",
                      "arroba de panela, medida antigua",
                      "el at de la arquitectura no aplica acá"):
            self.assertNotIn("correo deletreado", tipos(escanear_texto(texto)), texto)

    def test_digitos_separados_por_barras(self):
        h = escanear_texto("documento 1/016/086/781")
        self.assertIn("cédula", tipos(h))

    def test_el_guion_bajo_NO_es_separador(self):
        """Se probó y se sacó. Es el separador de miles de Python y de TOML,
        y este proyecto escribe así todos sus montos: agregarlo convertía
        `300_000_000` en una línea que dice «Ahorros» en una cédula de
        confianza ALTA. Un separador solo sirve como señal si no es además
        la forma normal de escribir un número."""
        h = escanear_texto('"patrimonio": [("Ahorros", 300_000_000)],')
        self.assertEqual(altas(h), [], h)
