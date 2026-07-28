#!/usr/bin/env python3
"""Escáner de datos personales para renta-co.

    python scripts/escanear_privacidad.py expediente/04-entregables/
    python scripts/escanear_privacidad.py --perfil expediente/perfil.toml README.md
    python scripts/escanear_privacidad.py --staged        # lo que va a entrar al commit
    python scripts/escanear_privacidad.py --estricto .    # ignora .privacidadignore

Código de salida 1 si encuentra algo de confianza ALTA. Sirve como hook de
pre-commit y como job de CI. Sin dependencias externas.

DISEÑO — por qué hay dos niveles de confianza
─────────────────────────────────────────────
En un expediente tributario, "90.000.000" (un monto) y "19.122.816" (una
cédula) tienen exactamente la misma forma. No se pueden distinguir mirando
el número.

Un intento anterior resolvió el ruido exigiendo una palabra de contexto en
la misma línea. Fue una regresión: en un CSV el encabezado `documento` está
en la línea 1 y las cédulas en las filas siguientes, así que TODA cédula de
una tabla quedaba invisible. Un detector de PII debe fallar hacia el falso
positivo, nunca hacia el falso negativo.

La solución es no descartar nada y separar por confianza:

  ALTA  — hay palabra de contexto en la línea, o la columna del CSV se llama
          "cedula"/"cuenta"/"documento", o el número tiene 4+ grupos (una
          cédula colombiana los tiene, un monto casi nunca), o son dígitos
          corridos sin separadores. Rompe el build.
  BAJA  — número con separadores, sin ninguna de esas señales. Es casi
          siempre un monto. Se reporta igual, pero no rompe el build.

Nada se silencia: lo de confianza baja se cuenta y se puede ver con
--mostrar-baja. Lo que cambia es qué bloquea un commit.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import sys
import tomllib
import unicodedata
from pathlib import Path

# Denylist en vez de allowlist: se salta lo que es binario conocido y se
# escanea todo lo demás. La versión anterior tenía una lista de extensiones
# permitidas y dejaba pasar .log, .bak, .rtf, .tsv, .xml, .eml y los archivos
# sin extensión — justo el tipo de archivo donde queda un volcado olvidado.
BINARIAS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp", ".tiff",
    ".mp3", ".mp4", ".wav", ".mov", ".avi", ".zip", ".gz", ".tar", ".bz2",
    ".7z", ".rar", ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".bin",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".lock",
}

# Formatos que sí contienen texto pero que este escáner no sabe abrir.
# No se ignoran en silencio: se reportan como NO ESCANEADO.
OPACAS = {".pdf", ".xlsx", ".xls", ".docx", ".doc", ".odt", ".ods", ".rtf"}

IGNORAR_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules",
                ".pytest_cache", ".ruff_cache"}

ARCHIVO_IGNORADOS = ".privacidadignore"
MAX_BYTES = 8 * 1024 * 1024

TABULARES = {".csv", ".tsv"}


# ---------------------------------------------------------------------
# Patrones
# ---------------------------------------------------------------------

def luhn(numero: str) -> bool:
    digitos = [int(d) for d in numero if d.isdigit()][::-1]
    if len(digitos) < 13:
        return False
    total = 0
    for i, d in enumerate(digitos):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# Solo palabras que acompañan a un IDENTIFICADOR. Se dejaron fuera a
# propósito "contribuyente", "declarante", "dependiente", "contratista" y
# "nombre": son vocabulario corriente de la documentación tributaria y
# aparecen en frases como "$3.585.528 por dependiente", que no contienen
# ningún dato personal. Incluirlas volvía a llenar el reporte de ruido.
CONTEXTO = re.compile(
    r"\b(?:c[eé]dula|c\.?c\.?|nit|identificaci[oó]n|documento|doc|pasaporte|"
    r"cuenta|ahorros|corriente|tarjeta|titular|apellido|"
    # `contraparte`, `beneficiario` y `payee` son los nombres con los que el
    # PROPIO ledger guarda lo que el banco traía en su columna `documento`.
    # Sin ellos, el escáner degradaba a BAJA justamente la PII que esta
    # herramienta escribe: la misma cédula salía ALTA bajo el encabezado
    # `documento` y BAJA bajo `contraparte` después de importarla.
    r"contraparte|beneficiario|payee)\b",
    re.IGNORECASE,
)

# Separadores de miles aceptados, incluidos los unicode que aparecen al
# copiar de un PDF o de una página web.
SEP = r"[.\s  ·•,-]"

PATRONES = [
    ("NIT", re.compile(rf"\d{{3}}{SEP}?\d{{3}}{SEP}?\d{{3}}\s?-\s?\d(?!\d)"), "alta"),
    ("tarjeta", re.compile(r"(?:\d[ .\-]?){13,19}"), "luhn"),
    # Cuatro grupos: forma de cédula. Un monto de esa magnitud existe
    # (1.411.950.000 = 30.000 UVT), por eso el "$" delante lo baja a confianza
    # baja más abajo, en vez de descartarlo acá.
    ("cédula", re.compile(rf"\b\d{{1,3}}(?:{SEP}\d{{3}}){{3}}\b"), "alta"),
    # Tres grupos: ambiguo. La confianza la decide el contexto.
    ("cédula o monto", re.compile(rf"\b\d{{1,3}}(?:{SEP}\d{{3}}){{2}}\b"), "ambigua"),
    # Dígitos corridos: un monto en prosa lleva separadores, un identificador
    # copiado de un sistema no. Se busca sin \b para atrapar CC1016086781 y
    # los que van pegados dentro de una URL.
    ("cédula o documento", re.compile(r"(?<!\d)\d{8,11}(?!\d)"), "alta"),
    ("cuenta bancaria", re.compile(rf"(?<!\d)\d{{2,4}}{SEP}\d{{5,8}}{SEP}\d{{1,4}}(?!\d)"), "alta"),
    ("correo", re.compile(
        r"[\w.%+-]+\s*(?:@|\[at\]|\(at\)|\(arroba\))\s*[\w.-]+\s*"
        r"(?:\.|\(punto\))\s*[A-Za-z]{2,}"), "alta"),
    ("teléfono", re.compile(
        r"(?:\+?57[\s.-]?)?\(?3\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"), "alta"),
    ("dirección", re.compile(
        r"\b(?:calle|cll?|carrera|cra|kra|kr|avenida|av|autopista|diagonal|dg|"
        r"transversal|tv|manzana|mz)\.?\s*\d+[\w\s#\-]{0,25}", re.IGNORECASE), "alta"),
    ("ruta de usuario", re.compile(
        r"(?:/(?:Users|home)/|[A-Za-z]:\\Users\\)[A-Za-z0-9._-]+"), "alta"),
]

# Se borran de la línea ANTES de aplicar los patrones. Ojo: acá no puede ir
# un patrón de monto con "$", porque anteponer "$" a una cédula la haría
# desaparecer. Los montos se manejan por confianza, no por exclusión.
RUIDO = re.compile(
    r"\b(?:19|20)\d{2}\b"                        # años
    r"|\b\d{4}-\d{2}-\d{2}\b"                    # fechas ISO
    r"|\bart\.?\s*\d+|\bnum\.?\s*\d+|\bpar\.?\s*\d+"   # referencias normativas
    r"|\bUVT\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------

def enmascarar(texto: str) -> str:
    if "@" in texto:
        usuario, _, dominio = texto.partition("@")
        return f"{usuario[:1]}{'*' * max(len(usuario) - 1, 3)}@{dominio}"
    digitos = [c for c in texto if c.isdigit()]
    if len(digitos) <= 4:
        return re.sub(r"\d", "X", texto)
    total, vistos, salida = len(digitos), 0, []
    for c in texto:
        if c.isdigit():
            vistos += 1
            salida.append(c if vistos <= 1 or vistos > total - 3 else "X")
        else:
            salida.append(c)
    return "".join(salida)


def normalizar(texto: str) -> str:
    """Minúsculas sin tildes. Un nombre sale 'Pérez' en el perfil y
    'PEREZ GOMEZ' en el encabezado de un extracto: hay que comparar igual."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return sin_tildes.lower()


def nombres_del_perfil(ruta: Path | None) -> list[str]:
    """Tokens de nombre propio del perfil, normalizados.

    Acepta tokens de 3 caracteres ('Ana', 'Luz'), parte los apellidos
    compuestos por guion, y no exige mayúscula inicial: un perfil escrito
    en minúscula sigue protegido.
    """
    if not ruta or not ruta.exists():
        return []
    with open(ruta, "rb") as f:
        datos = tomllib.load(f)

    CLAVES = re.compile(
        r"nombre|apellido|titular|conyuge|c[oó]nyuge|dependiente|hijo|"
        r"madre|padre|hermano|contratista|beneficiario|contribuyente",
        re.IGNORECASE,
    )
    COMUNES = {
        "los", "las", "del", "para", "con", "sin", "por", "que", "una", "uno",
        "cuenta", "banco", "ahorros", "tarjeta", "credito", "saldo", "wallet",
        "vehiculo", "avaluo", "inmueble", "plataforma", "cliente", "pagos",
    }

    tokens: set[str] = set()

    def recorrer(nodo, clave_padre=""):
        if isinstance(nodo, dict):
            for k, v in nodo.items():
                recorrer(v, k)
        elif isinstance(nodo, list):
            for v in nodo:
                recorrer(v, clave_padre)
        elif isinstance(nodo, str) and CLAVES.search(clave_padre):
            for palabra in re.split(r"[\s\-]+", nodo):
                limpia = normalizar(palabra.strip(".,;:()\"'"))
                if len(limpia) >= 3 and limpia.isalpha() and limpia not in COMUNES:
                    tokens.add(limpia)

    recorrer(datos)
    return sorted(tokens)


# ---------------------------------------------------------------------

MONETARIA = re.compile(
    r"\b(?:monto|valor|saldo|importe|total|amount|trm|debito|credito|"
    r"monto_cop|monto_origen|impuesto|base|uvt|cop|usd|"
    # Columnas de los CSV que genera el propio motor. Sin ellas,
    # `escenarios.csv` —cuyas columnas son ruta_A_costos y ruta_B_exenta_25—
    # reportaba cada cifra de ocho dígitos como documento de confianza ALTA.
    # El escáner gritando sobre su propia salida es la forma más rápida de
    # que la gente deje de leerlo.
    r"ruta_[ab](?:_\w+)?|costos?|exenta|deduccion|deducciones)\b",
    re.IGNORECASE,
)


def columnas_por_encabezado(texto: str, sep: str) -> tuple[set[int], set[int]]:
    """Clasifica las columnas de un CSV por lo que dice su encabezado.

    Es lo que arregla el caso que rompía la versión anterior: en un CSV el
    encabezado 'documento' está en la línea 1 y las cédulas en las filas
    siguientes, así que buscar contexto por línea nunca las encontraba.

    Y en sentido contrario: una columna 'monto_cop' de un ledger está llena
    de enteros de 8 dígitos que no son cédulas de nadie.

    Devuelve (columnas de identificador, columnas de dinero).
    """
    try:
        primera = next(csv.reader(io.StringIO(texto), delimiter=sep), [])
    except csv.Error:
        return set(), set()
    ident, dinero = set(), set()
    for i, celda in enumerate(primera):
        nombre = celda or ""
        if MONETARIA.search(nombre):
            dinero.add(i)
        elif CONTEXTO.search(nombre):
            ident.add(i)
    return ident, dinero


def rangos_de_celdas(linea: str, sep: str) -> list[tuple[int, int]]:
    """Posición (inicio, fin) de cada celda de una línea de CSV.

    Partir por `linea.split(sep)` era incorrecto en cuanto una celda traía el
    separador entre comillas —que es el caso normal: las descripciones de un
    extracto y los conceptos del `escenarios.csv` del propio motor lo traen—.
    Cada coma dentro de comillas corría UNA columna todas las de la derecha,
    así que la columna de montos dejaba de reconocerse y sus cifras de ocho
    dígitos se reportaban como documento de confianza ALTA.

    El resultado era el escáner gritando sobre su propia salida, que es la
    forma más rápida de que la gente deje de leerlo.
    """
    rangos: list[tuple[int, int]] = []
    inicio = 0
    entre_comillas = False
    for i, c in enumerate(linea):
        if c == '"':
            entre_comillas = not entre_comillas
        elif c == sep and not entre_comillas:
            rangos.append((inicio, i))
            inicio = i + 1
    rangos.append((inicio, len(linea)))
    return rangos


def escanear(ruta: Path, nombres=None) -> list[tuple[int, str, str, str]]:
    """Devuelve (línea, tipo, muestra enmascarada, confianza)."""
    nombres = nombres or []
    if ruta.suffix.lower() in OPACAS:
        return [(0, "formato no legible", ruta.suffix, "opaca")]
    try:
        if ruta.stat().st_size > MAX_BYTES:
            return [(0, "archivo muy grande", f"{ruta.stat().st_size // 1024} KB", "opaca")]
        texto = ruta.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return []
    return escanear_texto(texto, nombres, ruta.suffix.lower())


def escanear_texto(texto: str, nombres, sufijo="") -> list[tuple[int, str, str, str]]:
    cols_id: set[int] = set()
    cols_dinero: set[int] = set()
    sep = ""
    if sufijo in TABULARES:
        sep = "\t" if sufijo == ".tsv" else ","
        cols_id, cols_dinero = columnas_por_encabezado(texto, sep)

    # Se normaliza acá también, no solo al leer el perfil: quien llame a esta
    # función directo no tiene por qué saber que los nombres van en minúscula
    # y sin tildes.
    normalizado_nombres = [normalizar(n) for n in nombres if n]
    hallazgos = []

    for n, linea in enumerate(texto.splitlines(), start=1):
        # La sustitución preserva la longitud: los índices de `limpia` se
        # comparan después contra los rangos de columna calculados sobre
        # `linea`. Reemplazar por un solo espacio desplazaba las posiciones y
        # hacía que la columna de montos de un CSV no se reconociera.
        limpia = RUIDO.sub(lambda m: " " * len(m.group(0)), linea)
        contexto_linea = bool(CONTEXTO.search(linea))

        # Rangos de la línea según el encabezado de su columna.
        rangos_id: list[tuple[int, int]] = []
        rangos_dinero: list[tuple[int, int]] = []
        if sep and (cols_id or cols_dinero):
            for i, (desde, hasta) in enumerate(rangos_de_celdas(linea, sep)):
                if i in cols_id:
                    rangos_id.append((desde, hasta))
                elif i in cols_dinero:
                    rangos_dinero.append((desde, hasta))

        vistos = set()
        for etiqueta, patron, modo in PATRONES:
            for m in patron.finditer(limpia):
                bruto = m.group(0).strip()
                if not bruto or bruto in vistos:
                    continue

                en_columna_id = any(a <= m.start() < b for a, b in rangos_id)
                en_columna_dinero = any(a <= m.start() < b for a, b in rangos_dinero)

                # Un "$" delante marca dinero, pero NO borra el hallazgo: solo
                # lo baja de confianza, y solo si la línea no trae una palabra
                # de identificador. Así "$1.411.950.000" (un umbral en UVT) no
                # hace ruido, y "Cedula: $1.016.086.781" —el truco obvio para
                # evadir el escáner— sigue rompiendo el build.
                antes = limpia[max(0, m.start() - 2):m.start()]
                con_signo_peso = "$" in antes

                if modo == "luhn":
                    if not luhn(bruto):
                        continue
                    confianza = "alta"
                elif modo == "ambigua":
                    confianza = ("alta" if (contexto_linea or en_columna_id)
                                 else "baja")
                elif con_signo_peso and not contexto_linea:
                    confianza = "baja"
                elif en_columna_dinero and etiqueta in {
                    "cédula o documento", "cuenta bancaria",
                }:
                    # Una columna 'monto_cop' de un ledger está llena de
                    # enteros de 8 dígitos que no son documento de nadie.
                    confianza = "baja"
                else:
                    confianza = "alta"

                vistos.add(bruto)
                hallazgos.append((n, etiqueta, enmascarar(bruto), confianza))

        linea_norm = normalizar(linea)
        for nombre in normalizado_nombres:
            if re.search(rf"\b{re.escape(nombre)}\b", linea_norm):
                hallazgos.append(
                    (n, "nombre del perfil", nombre[0] + "*" * (len(nombre) - 1), "alta")
                )
    return hallazgos


# ---------------------------------------------------------------------

def globs_ignorados(raiz: Path, estricto: bool) -> list[str]:
    if estricto:
        return []
    archivo = raiz / ARCHIVO_IGNORADOS
    if not archivo.exists():
        return []
    globs = []
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        g = linea.strip()
        if not g or g.startswith("#"):
            continue
        globs.append(g)
    return globs


# Si las exclusiones se comen más que esto del árbol, el archivo dejó de ser
# una lista de excepciones y pasó a ser un interruptor de apagado.
LIMITE_OMISION = 0.40


def aplicar_ignorados(archivos: list[Path], globs: list[str],
                      raiz: Path | None = None) -> tuple[list[Path], list[str]]:
    """Filtra por los globs y rechaza los que apaguen el escáner.

    Una lista literal de globs prohibidos (`*`, `**`, …) no protege nada:
    `?*` o `[a-z]*` hacen exactamente lo mismo y no están en ninguna lista.
    Se mide el EFECTO — cuántos archivos deja fuera cada glob — que es lo que
    de verdad importa y no se puede rodear cambiando la sintaxis.
    """
    if not archivos or not globs:
        return archivos, []

    avisos = []
    aceptados: list[str] = []
    total = len(archivos)
    # El límite se mide contra el árbol COMPLETO cuando se sabe cuál es.
    # Midiéndolo solo contra el objetivo del escaneo, revisar un directorio
    # que está legítimamente ignorado rechazaba su propio glob por "100% del
    # árbol". Y midiéndolo siempre contra el directorio actual, una lista de
    # archivos que no viene del repo se compara contra un universo ajeno.
    universo = total
    if raiz is not None:
        universo = max(len(archivos_de([str(raiz)])), total)
    limite = universo * LIMITE_OMISION

    # El límite es ACUMULADO, no por glob. Medir cada uno contra el total
    # dejaba pasar cuatro globs del 25% que juntos apagaban el escáner
    # entero: cada uno quedaba por debajo del umbral y ninguno se rechazaba.
    for g in globs:
        candidatos = aceptados + [g]
        omitidos = sum(1 for a in archivos if esta_ignorado(a, candidatos, raiz))
        if omitidos > limite:
            solo_este = sum(1 for a in archivos if esta_ignorado(a, [g], raiz))
            avisos.append(
                f"{ARCHIVO_IGNORADOS}: se RECHAZA el glob '{g}'. Por sí solo deja "
                f"fuera {solo_este} de {total} archivos, y sumado a los anteriores "
                f"llegaría a {omitidos} ({omitidos / universo:.0%} del árbol). El "
                f"límite acumulado es {LIMITE_OMISION:.0%}: este archivo es para "
                f"excepciones puntuales, no para apagar el escáner."
            )
            continue
        aceptados.append(g)

    restantes = [a for a in archivos if not esta_ignorado(a, aceptados, raiz)]
    return restantes, avisos


def esta_ignorado(ruta: Path, globs: list[str], raiz: Path | None = None) -> bool:
    """¿La ruta cae en alguno de los globs?

    Los globs de .privacidadignore son relativos a la raíz del repositorio.
    La ruta puede llegar relativa, con './' o absoluta —el lanzador
    absolutiza los objetivos—, y compararla tal cual hacía que el mismo
    archivo se ignorara o no según cómo se hubiera invocado el escáner.
    """
    from fnmatch import fnmatch

    candidatos = set()
    texto = str(ruta)
    if texto.startswith("./"):
        texto = texto[2:]
    candidatos.add(texto)

    base = raiz or Path.cwd()
    try:
        candidatos.add(str(Path(texto).resolve().relative_to(base.resolve())))
    except (ValueError, OSError):
        pass

    return any(fnmatch(c, g) for c in candidatos for g in globs)


def archivos_de(objetivos: list[str]) -> list[Path]:
    rutas: list[Path] = []
    for objetivo in objetivos:
        p = Path(objetivo)
        if p.is_dir():
            rutas += [
                f for f in p.rglob("*")
                if f.is_file()
                and f.suffix.lower() not in BINARIAS
                and not IGNORAR_DIRS & set(f.parts)
            ]
        elif p.is_file():
            rutas.append(p)
    return rutas


class SinIndice(Exception):
    """No se pudo leer el índice de git.

    Es un error, no un "no hay nada": antes se imprimía un aviso, se
    devolvía la lista vacía y el proceso salía con 0. Un hook de pre-commit
    que sale 0 cuando no pudo mirar es peor que no tener hook, porque el
    usuario cree que lo revisaron.
    """


def escanear_indice(nombres) -> tuple[list[tuple[str, list]], int]:
    """Escanea los BLOBS del índice, no el working tree.

    `git add` de un archivo con una cédula y después sobrescribirlo con
    contenido limpio dejaba pasar el commit: el hook leía el disco mientras
    lo que se iba a commitear era el blob con el dato.
    """
    try:
        salida = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise SinIndice(
            f"No se pudo leer el índice de git desde {Path.cwd()} ({e}). "
            f"--staged tiene que correr dentro del repositorio cuyo commit se "
            f"está revisando."
        ) from e

    rutas = [p for p in salida.split("\n") if p.strip()]
    resultados, revisados = [], 0
    for ruta in rutas:
        if Path(ruta).suffix.lower() in BINARIAS:
            continue
        try:
            blob = subprocess.run(
                ["git", "show", f":{ruta}"],
                capture_output=True, check=True,
            ).stdout.decode("utf-8", errors="replace")
        except subprocess.CalledProcessError:
            continue
        revisados += 1
        if Path(ruta).suffix.lower() in OPACAS:
            resultados.append((ruta, [(0, "formato no legible", Path(ruta).suffix, "opaca")]))
            continue
        h = escanear_texto(blob, nombres, Path(ruta).suffix.lower())
        if h:
            resultados.append((ruta, h))
    return resultados, revisados


# ---------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Busca datos personales antes de compartir o commitear."
    )
    ap.add_argument("objetivos", nargs="*", default=["."])
    ap.add_argument("--perfil", type=Path, default=None,
                    help="perfil.toml, para también buscar nombres propios")
    ap.add_argument("--staged", action="store_true",
                    help="Escanear los blobs del índice de git")
    ap.add_argument("--estricto", action="store_true",
                    help="Ignorar .privacidadignore. Lo que usa CI")
    ap.add_argument("--mostrar-baja", action="store_true",
                    help="Listar también los hallazgos de confianza baja")
    args = ap.parse_args(argv)

    nombres = nombres_del_perfil(args.perfil)
    if args.perfil and not nombres:
        print("⚠ El perfil no aportó nombres. La detección de nombres queda apagada.")

    raiz_repo = Path.cwd()
    if args.staged:
        try:
            resultados, revisados = escanear_indice(nombres)
        except SinIndice as e:
            print(f"✗ {e}")
            return 1
        globs = globs_ignorados(raiz_repo, args.estricto)
        if globs:
            antes = len(resultados)
            rutas = [Path(r) for r, _ in resultados]
            conservadas, avisos_globs = aplicar_ignorados(rutas, globs, raiz_repo)
            conservadas = {str(x) for x in conservadas}
            resultados = [(r, h) for r, h in resultados if r in conservadas]
            for aviso in avisos_globs:
                print(f"⚠ {aviso}")
            if antes - len(resultados):
                print(f"({antes - len(resultados)} archivo(s) del índice omitidos "
                      f"por {ARCHIVO_IGNORADOS})")
    else:
        archivos = archivos_de(args.objetivos or ["."])
        globs = globs_ignorados(raiz_repo, args.estricto)
        antes = len(archivos)
        archivos, avisos_globs = aplicar_ignorados(archivos, globs, raiz_repo)
        for aviso in avisos_globs:
            print(f"⚠ {aviso}")
        if antes - len(archivos):
            print(f"({antes - len(archivos)} archivo(s) omitidos por "
                  f"{ARCHIVO_IGNORADOS}; usa --estricto para incluirlos)")
        resultados = [(str(a), escanear(a, nombres)) for a in sorted(archivos)]
        resultados = [(r, h) for r, h in resultados if h]
        revisados = len(archivos)

    if not revisados:
        # El mensaje distingue los dos modos a propósito: "No hay archivos que
        # escanear" saliendo con 0 fue durante meses la señal de que --staged
        # estaba mirando el repositorio equivocado, y se leía como éxito.
        if args.staged:
            print(f"No hay nada en el índice de git de {Path.cwd()}. "
                  f"Nada que revisar antes del commit.")
        else:
            print("No hay archivos que escanear.")
        return 0

    altas = bajas = opacas = 0
    for archivo, hallazgos in resultados:
        visibles = [h for h in hallazgos
                    if h[3] == "alta" or (h[3] == "baja" and args.mostrar_baja)
                    or h[3] == "opaca"]
        altas += sum(1 for h in hallazgos if h[3] == "alta")
        bajas += sum(1 for h in hallazgos if h[3] == "baja")
        opacas += sum(1 for h in hallazgos if h[3] == "opaca")
        if not visibles:
            continue
        print(f"\n{archivo}")
        for n, etiqueta, muestra, confianza in visibles:
            if confianza == "opaca":
                print(f"  NO ESCANEADO      {etiqueta}: {muestra} — revísalo a mano")
            else:
                marca = "  " if confianza == "alta" else "· "
                print(f"  {marca}línea {n:>4}  {etiqueta:<20} {muestra}")

    print()
    if opacas:
        print(f"⚠ {opacas} archivo(s) en formato que este escáner no puede leer "
              f"(PDF, XLSX, DOCX). Revísalos a mano antes de compartirlos.")
    if bajas and not args.mostrar_baja:
        print(f"· {bajas} hallazgo(s) de confianza BAJA (casi siempre montos "
              f"en pesos). Verlos con --mostrar-baja.")

    if altas:
        print(f"⚠ {altas} dato(s) personal(es) de confianza ALTA en "
              f"{revisados} archivo(s) revisados.")
        print()
        print("  La pregunta que importa: ¿a dónde va este archivo?")
        print("    · Se queda en expediente/   → está bien, ahí debe estar.")
        print("    · Va al contador            → lo necesita; confirma el destinatario.")
        print("    · Va a un repo o a un issue → quítalo o usa un placeholder.")
        return 1

    print(f"✓ Sin datos personales de confianza alta en {revisados} archivo(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
