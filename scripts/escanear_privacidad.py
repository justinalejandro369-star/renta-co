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

# El inventario es un REPORTE de hallazgos, así que sus líneas tienen la
# forma de lo que reporta: el escáner se gritaba a sí mismo sobre su propia
# salida —tercera vez que pasa en este proyecto— y además se habría
# inventariado a sí mismo, creciendo en cada regeneración. Está en
# .privacidadignore y se salta acá: no es un archivo fuente, es una vista
# enmascarada de archivos que ya están inventariados línea por línea.
ARCHIVO_INVENTARIO = "privacidad-esperado.txt"
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
    # `c.e.` es cédula de extranjería. `t.i.` (tarjeta de identidad) se probó
    # y se sacó: "ti" ES una palabra del español, y "lo que terceros
    # reportaron sobre ti" convertía en identificador cada monto de esa
    # línea del README. Una abreviatura solo sirve como señal de contexto si
    # no colisiona con el idioma.
    r"\b(?:c[eé]dula|c\.?c\.?|c\.?e\.?|nit|identificaci[oó]n|documento|doc|pasaporte|"
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
# La barra va aquí porque es como quedan los dígitos al copiarlos de
# algunos sistemas: `1/016/086/781` escapaba entero.
#
# El guion bajo se probó y se SACÓ. Es el separador de miles de Python y de
# TOML, y este proyecto escribe así todos sus montos —incluidos los de la
# plantilla que el usuario copia—, así que agregarlo convertía cada cifra
# del repo en candidata: `300_000_000` en una línea que dice «Ahorros»
# salía como cédula de confianza ALTA. Un separador solo sirve como señal
# si no es además la forma normal de escribir un número.
SEP = r"[.\s  ·•,\-/]"

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
    # Cédulas de 6–7 dígitos: las antiguas y, sobre todo, las CÉDULAS DE
    # EXTRANJERÍA, que son de 6 o 7. Un caso de uso entero —el extranjero
    # residente fiscal en Colombia— quedaba sin cobertura. Van como ambiguas
    # porque a esa longitud sí chocan con montos: la confianza la decide el
    # contexto o la columna, igual que "cédula o monto".
    ("cédula corta o extranjería", re.compile(r"(?<!\d)\d{6,7}(?!\d)"), "ambigua"),
    # Corridas de 12 o más dígitos: `\d{8,11}` las dejaba pasar enteras. La
    # skill promete detectar "cuentas bancarias de 9 a 20 dígitos".
    ("cuenta o identificador largo", re.compile(r"(?<!\d)\d{12,}(?!\d)"), "alta"),
    # IBAN. El repo trae adaptador de Wise, y Wise entrega IBAN.
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"), "alta"),
    # Fijos colombianos: desde 2022 son 10 dígitos y empiezan por 60X. El
    # patrón de teléfono solo anclaba en los celulares (3XX).
    ("teléfono fijo", re.compile(
        r"(?:\+?57[\s.-]?)?\(?60\d\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"), "alta"),
    ("cuenta bancaria", re.compile(rf"(?<!\d)\d{{2,4}}{SEP}\d{{5,8}}{SEP}\d{{1,4}}(?!\d)"), "alta"),
    ("correo", re.compile(
        r"[\w.%+-]+\s*(?:@|\[at\]|\(at\)|\(arroba\))\s*[\w.-]+\s*"
        r"(?:\.|\(punto\))\s*[A-Za-z]{2,}"), "alta"),
    # Correo DELETREADO, que es como lo escribe quien sabe que hay un
    # escáner o quien lo dicta por teléfono: «persona arroba ejemplo punto
    # com». Exige las DOS palabras —la del @ y la del punto— porque cada una
    # por separado es vocabulario corriente y llenaría el reporte de ruido.
    ("correo deletreado", re.compile(
        r"\b[\w.%+-]+\s+(?:arroba|at)\s+[\w.-]+\s+(?:punto|dot)\s+[A-Za-z]{2,}\b",
        re.IGNORECASE), "alta"),
    ("teléfono", re.compile(
        r"(?:\+?57[\s.-]?)?\(?3\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"), "alta"),
    ("dirección", re.compile(
        r"\b(?:calle|cll?|carrera|cra|kra|kr|avenida|av|autopista|diagonal|dg|"
        r"transversal|tv|manzana|mz)\.?\s*\d+[\w\s#\-]{0,25}", re.IGNORECASE), "alta"),
    # Dirección SIN verbo de vía. Media Colombia urbana vive en un
    # `Apto 502 Torre 3` y el patrón de arriba, que ancla en «calle» o
    # «carrera», no veía ninguno. El complemento de la vía identifica una
    # vivienda igual de bien que la vía.
    # `conjunto` y `urbanización` se probaron y se sacaron: no llevan número
    # de casa —«Conjunto Los Robles»— y en cambio «tope conjunto 40%»
    # aparece en cada documento de este repo.
    ("dirección (unidad)", re.compile(
        r"\b(?:apto|apartamento|torre|bloque|manzana|mz|lote)\.?\s*\d+"
        r"[\w\s#\-]{0,25}", re.IGNORECASE), "alta"),
    # Rural: `Km 5 vía La Calera`, `Vereda El Salado`. Es la dirección de
    # una finca, y no lleva número de casa.
    ("dirección (rural)", re.compile(
        r"\b(?:km|kil[oó]metro)\.?\s*\d+\s*(?:v[ií]a|vereda|carretera)\b[\w\s]{0,30}"
        r"|\bvereda\s+[A-ZÁÉÍÓÚÑ][\w]*(?:\s+[A-ZÁÉÍÓÚÑ]?[\w]*){0,3}",
        re.IGNORECASE), "alta"),
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
    # Números de acto administrativo. Van con su palabra delante a
    # propósito: el radicado de un concepto DIAN —100202208-1621— tiene
    # exactamente la forma de una cédula, y borrar cualquier corrida de
    # dígitos "porque parece un radicado" abriría la puerta de par en par.
    r"|\b(?:concepto|conceptos|resoluci[oó]n|resoluciones|res\.|radicado|circular|"
    r"sentencia|decreto|ley)\s+(?:unificad[oa]\s+)?(?:DIAN\s+)?[\d.\-]{3,}"
    r"|\bUVT\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------

# Palabras que pueden salir en claro dentro de una dirección o una ruta:
# son vocabulario, no identidad. Todo lo demás se tapa.
PALABRAS_NEUTRAS = {
    "calle", "cll", "cl", "carrera", "cra", "kra", "kr", "avenida", "av",
    "autopista", "diagonal", "dg", "transversal", "tv", "manzana", "mz",
    "apto", "apartamento", "torre", "bloque", "interior", "int", "piso",
    "barrio", "km", "via", "users", "home", "c", "d", "documents",
}


def _tapar_palabra(palabra: str) -> str:
    """Deja la inicial y tapa el resto, salvo que sea vocabulario."""
    limpia = normalizar(palabra.strip(".,;:()[]\"'"))
    if not palabra or not any(c.isalpha() for c in palabra):
        return palabra
    if limpia in PALABRAS_NEUTRAS or len(limpia) <= 2:
        return palabra
    return palabra[0] + "*" * (len(palabra) - 1)


def enmascarar(texto: str) -> str:
    """Versión publicable de un hallazgo.

    El reporte del escáner se pega en un issue, se manda por correo y lo lee
    el contador. Si `enmascarar` devuelve el dato entero, el informe es él
    mismo la fuga que el escáner existe para evitar. PRIVACY.md dice
    "siempre enmascarado" y la skill dice "nunca imprimas el dato completo".

    Tapaba solo los dígitos, así que lo alfabético salía intacto y los dos
    hallazgos cuyo valor ES alfabético salían enteros:

        "/Users/fulanito"            → "/Users/fulanito"
        "Calle 100 #45-20 Apto 301 Barrio Chico"
                                     → "Calle 1XX #XX-XX Apto 301 Barrio Chico"

    El patrón "ruta de usuario" existe justamente para atrapar el nombre de
    la cuenta del sistema. Ahora se tapan las dos cosas: los dígitos y las
    palabras que no son vocabulario de dirección.
    """
    if "@" in texto:
        usuario, _, dominio = texto.partition("@")
        # El dominio también se tapa: "@bufete-gomez-abogados.com.co"
        # identifica a una persona tan bien como el usuario.
        nombre_dominio, punto, tld = dominio.rpartition(".")
        dominio_tapado = f"{_tapar_palabra(nombre_dominio)}{punto}{tld}" if punto else dominio
        return f"{usuario[:1]}{'*' * max(len(usuario) - 1, 3)}@{dominio_tapado}"

    # Los dígitos se cuentan sobre el texto COMPLETO: en "1.016.086.781" hay
    # que dejar el primero y los tres últimos del número entero, no de cada
    # grupo. Se decide aquí y se aplica al recorrer.
    total = sum(1 for c in texto if c.isdigit())
    vistos = 0
    salida = []
    # Se recorre por trozos para poder tratar distinto lo alfabético puro
    # —donde vive el nombre— y lo que lleva dígitos.
    for trozo in re.split(r"([^\w]+)", texto):
        if not trozo:
            continue
        if any(c.isdigit() for c in trozo):
            for c in trozo:
                if c.isdigit():
                    vistos += 1
                    # Con cuatro dígitos o menos se tapan todos: dejar el
                    # primero y los tres últimos sería dejarlo entero.
                    visible = total > 4 and (vistos <= 1 or vistos > total - 3)
                    salida.append(c if visible else "X")
                else:
                    salida.append(c)
        elif re.fullmatch(r"[^\w]+", trozo):
            salida.append(trozo)
        else:
            salida.append(_tapar_palabra(trozo))
    return "".join(salida)


# Un nombre de archivo con la cédula queda en el árbol de GitHub, en el diff
# y en la URL — indexable — aunque el contenido esté limpio.
# "extracto-cc-1016086781-juan-perez.pdf" es exactamente como los nombra un
# banco colombiano. Ni `escanear` ni `escanear_indice` miraban la ruta.
def hallazgos_del_nombre(ruta) -> list[tuple[int, str, str, str]]:
    nombre = Path(ruta).name
    hallazgos = []
    for etiqueta, patron, modo in PATRONES:
        if modo == "luhn" or etiqueta == "ruta de usuario":
            continue
        for m in patron.finditer(nombre):
            bruto = m.group(0).strip()
            if bruto:
                hallazgos.append(
                    (0, f"{etiqueta} EN EL NOMBRE DEL ARCHIVO",
                     enmascarar(bruto), "alta")
                )
                break
    return hallazgos


def normalizar(texto: str) -> str:
    """Minúsculas sin tildes. Un nombre sale 'Pérez' en el perfil y
    'PEREZ GOMEZ' en el encabezado de un extracto: hay que comparar igual."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return sin_tildes.lower()


# Secciones de primer nivel del perfil donde una cadena PUEDE ser el nombre
# de una persona. Fuera de ellas, `nombre` significa otra cosa: en
# [[patrimonio.activos]] significa "Apartamento en Chapinero" y "Reconocimiento
# inicial USD", que es de donde salían los tokens `art`, `trm` y `usd`.
SECCIONES_DE_PERSONAS = {
    "contribuyente", "personas", "dependientes", "contratistas", "conyuge",
    "conyuge_o_companero", "titulares",
}

# Y dentro de esas secciones, solo estas claves. `nombre` a secas en
# [contribuyente] sí es una persona; `nota`, `descripcion` o `fuente` no.
CLAVES_DE_PERSONA = re.compile(
    r"^(?:nombres?|apellidos?|nombre_completo|titular(?:es)?|"
    r"c[oó]nyuge|companer[oa]|compañer[oa]|hijos?|madre|padre|padres|"
    r"hermanos?|dependientes?|contratistas?|beneficiarios?)$",
    re.IGNORECASE,
)


def nombres_del_perfil(ruta: Path | None) -> list[str]:
    """Tokens de nombre propio del perfil, normalizados.

    Acepta tokens de 3 caracteres ('Ana', 'Luz'), parte los apellidos
    compuestos por guion, y no exige mayúscula inicial: un perfil escrito
    en minúscula sigue protegido.

    La versión anterior recorría CUALQUIER clave que empatara
    `nombre|titular|…` sin mirar dónde estaba. Como `perfil.toml` usa
    `nombre` para los ACTIVOS del patrimonio, sobre el propio ejemplo del
    repo extraía los tokens `art`, `trm`, `usd`, `inicial` y `reconocimiento`
    y reportaba 12 falsos positivos de confianza ALTA en el README. Una
    detección con esa tasa de ruido no se vuelve a usar, y es la ÚNICA
    detección de nombres propios que existe: el ruido no la degradaba, la
    apagaba.

    Ahora la clave tiene que estar en una sección de PERSONAS y llamarse
    como una persona. Las dos condiciones a la vez, no una.
    """
    if not ruta or not ruta.exists():
        return []
    with open(ruta, "rb") as f:
        datos = tomllib.load(f)

    COMUNES = {
        "los", "las", "del", "para", "con", "sin", "por", "que", "una", "uno",
        "cuenta", "banco", "ahorros", "tarjeta", "credito", "saldo", "wallet",
        "vehiculo", "avaluo", "inmueble", "plataforma", "cliente", "pagos",
    }

    tokens: set[str] = set()

    def cosechar(valor: str):
        for palabra in re.split(r"[\s\-]+", valor):
            limpia = normalizar(palabra.strip(".,;:()\"'"))
            if len(limpia) >= 3 and limpia.isalpha() and limpia not in COMUNES:
                tokens.add(limpia)

    def recorrer(nodo, clave=""):
        """Baja por el árbol de UNA sección de personas.

        Dentro de ella se aceptan las claves de persona a cualquier
        profundidad, para que `[[personas]] nombre = "..."` y
        `[contribuyente] nombre = "..."` funcionen igual.
        """
        if isinstance(nodo, dict):
            for k, v in nodo.items():
                recorrer(v, k)
        elif isinstance(nodo, list):
            for v in nodo:
                recorrer(v, clave)
        elif isinstance(nodo, str) and CLAVES_DE_PERSONA.fullmatch(clave):
            cosechar(nodo)

    for seccion, contenido in datos.items():
        if normalizar(seccion) in SECCIONES_DE_PERSONAS:
            recorrer(contenido, seccion)

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

    hallazgos += hallazgos_partidos(texto)
    return hallazgos


# Un número roto en dos por un salto de línea. Es lo que produce copiar de
# un PDF a dos columnas o de un extracto con el ancho justo, y el escáner
# leía las dos mitades por separado: `1.016.086.` no es nada y `781` tampoco.
CORTE = re.compile(rf"(\d(?:{SEP}|\d)*)$")
PEGA = re.compile(rf"^((?:{SEP}|\d)*\d)")

# Solo las formas FUERTES cruzan líneas. Correr las ambiguas —tres grupos,
# seis o siete dígitos— sobre cada par de líneas llevó los hallazgos de
# confianza baja de 187 a 869 sobre este mismo repo: en un documento
# tributario, una fila que termina en dígito seguida de otra que empieza en
# dígito es el contenido NORMAL. Un contador de ruido que se multiplica por
# cinco deja de significar algo, y esa es la forma conocida de apagar esta
# herramienta. Un monto partido en dos casi nunca es una cédula; una corrida
# de ocho a once dígitos o cuatro grupos de tres, sí.
FORMAS_FUERTES = {
    "cédula", "cédula o documento", "cuenta o identificador largo", "NIT",
}


def hallazgos_partidos(texto: str) -> list[tuple[int, str, str, str]]:
    """Identificadores que quedan a caballo entre dos líneas.

    Se unen las dos líneas y se busca solo lo que CRUCE la unión: lo que cabe
    entero en una de las dos ya lo encontró el paso normal, y reportarlo otra
    vez sería duplicar.

    La confianza es ALTA únicamente con palabra de contexto en alguna de las
    dos líneas. Sin ella queda BAJA, porque una tabla de montos donde una
    fila termina en dígito y la siguiente empieza en dígito produce esta
    misma forma, y ese es el contenido normal de un expediente tributario:
    subirlo todo a ALTA volvería a llenar el reporte de ruido, que es como se
    apagó `--perfil`.
    """
    lineas = texto.splitlines()
    hallazgos = []
    for i in range(len(lineas) - 1):
        izq, der = lineas[i].rstrip(), lineas[i + 1].lstrip()
        if not izq or not der:
            continue
        cola = CORTE.search(izq)
        cabeza = PEGA.match(der)
        if not cola or not cabeza:
            continue
        unido = cola.group(1) + cabeza.group(1)
        # Sin el corte no hay nada nuevo que reportar.
        if len(cola.group(1)) < 2 or len(cabeza.group(1)) < 2:
            continue
        # También la línea de ARRIBA: en un extracto copiado de un PDF el
        # encabezado («Documento:») queda en su propia línea y el número
        # roto empieza en la siguiente. Mirando solo el par, el caso que
        # motivó todo esto salía de confianza baja.
        previa = lineas[i - 1] if i else ""
        contexto = bool(CONTEXTO.search(izq) or CONTEXTO.search(der)
                        or CONTEXTO.search(previa))
        for etiqueta, patron, modo in PATRONES:
            if etiqueta not in FORMAS_FUERTES:
                continue
            for m in patron.finditer(unido):
                bruto = m.group(0).strip()
                # Tiene que CRUZAR la unión, y no caber en ninguna mitad.
                cruza = m.start() < len(cola.group(1)) < m.end()
                if not cruza or bruto in izq or bruto in der:
                    continue
                hallazgos.append((
                    i + 1, f"{etiqueta} (roto en dos líneas)",
                    enmascarar(bruto), "alta" if contexto else "baja",
                ))
                break
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
        # `-z` y NO `--name-only` a secas: con la configuración por defecto
        # (`core.quotePath = true`) git ENTRECOMILLA y escapa los nombres que
        # no son ASCII puro, así que "cédula.csv" llegaba como
        # "c\303\251dula.csv". El `git show` de ese nombre inventado fallaba,
        # el `except ... continue` se tragaba el error, `revisados` quedaba en
        # cero y el hook imprimía "no hay nada en el índice" y salía 0.
        #
        # En Colombia los nombres con tilde y con ñ no son un caso raro: son
        # el caso normal. `declaración.csv`, `nómina.csv`, `cédula.pdf`. El
        # hook estaba ciego justo para los archivos que peor pinta tienen.
        salida = subprocess.run(
            ["git", "diff", "--cached", "-z", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, check=True,
        ).stdout.decode("utf-8", errors="surrogateescape")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise SinIndice(
            f"No se pudo leer el índice de git desde {Path.cwd()} ({e}). "
            f"--staged tiene que correr dentro del repositorio cuyo commit se "
            f"está revisando."
        ) from e

    rutas = [p for p in salida.split("\0") if p.strip()]
    resultados, revisados = [], 0
    for ruta in rutas:
        sufijo = Path(ruta).suffix.lower()
        revisados += 1
        # Lo que el escáner NO PUEDE leer se reporta y BLOQUEA, no se salta.
        # Antes un `.pdf`, un `.xlsx` o un `.png` en el índice imprimían
        # "revísalo a mano" y salían 0: el hook aprobaba un archivo que no
        # había podido mirar. Un extracto en PDF y una foto de la cédula son
        # los dos soportes más comunes que existen.
        if sufijo in BINARIAS or sufijo in OPACAS:
            resultados.append((ruta, [(0, "formato no legible", sufijo or "(sin extensión)",
                                       "opaca")]))
            continue
        try:
            blob = subprocess.run(
                ["git", "show", f":{ruta}"],
                capture_output=True, check=True,
            ).stdout
        except subprocess.CalledProcessError as e:
            # Tampoco se salta en silencio: si no se pudo leer el blob, el
            # hook no tiene con qué aprobar el commit.
            resultados.append((ruta, [(0, "no se pudo leer del índice",
                                       str(e.returncode), "opaca")]))
            continue
        if b"\0" in blob[:8192]:
            resultados.append((ruta, [(0, "contenido binario", sufijo or "(sin extensión)",
                                       "opaca")]))
            continue
        if len(blob) > MAX_BYTES:
            resultados.append((ruta, [(0, "archivo muy grande",
                                       f"{len(blob) // 1024} KB", "opaca")]))
            continue
        h = escanear_texto(blob.decode("utf-8", errors="replace"), nombres, sufijo)
        h += hallazgos_del_nombre(ruta)
        if h:
            resultados.append((ruta, h))
    return resultados, revisados


# ---------------------------------------------------------------------

# Formas que un caso de prueba o un docstring de formato produce de por sí:
# los tests traen cédulas de laboratorio y el parser documenta cada formato
# de monto con un ejemplo. No entran al inventario porque lo llenarían de
# ruido y lo volverían inútil, que es lo mismo que le pasó a `--perfil`.
FORMAS_DE_LABORATORIO = {
    "cédula", "cédula o monto", "cédula o documento",
    "cédula corta o extranjería", "cuenta o identificador largo",
    "cuenta bancaria", "NIT", "tarjeta",
}


def inventario_de_lo_excluido(raiz: Path) -> list[str]:
    """Lo que hay en los archivos que `.privacidadignore` deja fuera.

    El modo estricto sale 1 A PROPÓSITO, así que CI nunca lo pudo usar como
    compuerta y los archivos excluidos quedaron sin ninguna revisión
    automática. Ahí fue justo donde se coló una ruta HOME real.

    La salida no es exigir cero: es exigir que lo que hay esté INVENTARIADO,
    y que cualquier línea nueva rompa el build. Sin número de línea, para que
    agregar un test arriba no mueva el inventario entero.
    """
    globs = globs_ignorados(raiz, estricto=False)
    excluidos = sorted(
        a for a in archivos_de([str(raiz)])
        if esta_ignorado(a, globs, raiz) and a.name != ARCHIVO_INVENTARIO
    )
    filas = set()
    for archivo in excluidos:
        for _, etiqueta, muestra, confianza in escanear(archivo):
            if confianza != "alta" or etiqueta in FORMAS_DE_LABORATORIO:
                continue
            filas.add(f"{archivo.relative_to(raiz)} · {etiqueta} · {muestra}")
    return sorted(filas)


def imprimir_inventario(raiz: Path) -> int:
    print("# Línea base de scripts/escanear_privacidad.py --inventario.")
    print("#")
    print("# Lo que los archivos de .privacidadignore contienen HOY, sin las")
    print("# formas que un caso de prueba produce de por sí. Cualquier línea")
    print("# nueva rompe el build: mírala antes de regenerar este archivo.")
    print("#")
    print("# Regenerar:")
    print("#   python3 scripts/escanear_privacidad.py --inventario > \\")
    print("#       scripts/privacidad-esperado.txt")
    for fila in inventario_de_lo_excluido(raiz):
        print(fila)
    return 0


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
    ap.add_argument("--inventario", action="store_true",
                    help="Imprimir la línea base de lo que hay en los "
                         "archivos de .privacidadignore. Ver "
                         "scripts/privacidad-esperado.txt")
    args = ap.parse_args(argv)

    if args.inventario:
        return imprimir_inventario(Path.cwd())

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
        # `.privacidadignore` NO se aplica acá, a propósito.
        #
        # Ese archivo existe para bajarle el ruido a un ESCANEO informativo
        # sobre un árbol de trabajo. Lo que está en el índice es otra cosa:
        # es exactamente lo que se va a publicar. Permitir excluir algo de
        # ahí es permitir apagar el guardián en la única puerta que importa,
        # y una línea plausible —`expediente/*`, que cualquiera escribiría
        # pensando «eso ya está gitignored»— lo apagaba entero.
        #
        # Si un archivo del índice da un falso positivo, la salida es
        # `git commit --no-verify`, que deja rastro de la decisión, y no un
        # archivo de configuración que la vuelve permanente y silenciosa.
        if globs_ignorados(raiz_repo, args.estricto):
            print(f"({ARCHIVO_IGNORADOS} NO se aplica a --staged: lo que está "
                  f"en el índice es lo que se va a publicar.)")
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

    # En modo hook, lo que NO se pudo leer bloquea. Un PDF, un XLSX o una
    # foto de la cédula en el índice salían con "revísalo a mano" y código 0,
    # o sea el hook aprobando un archivo que no pudo mirar. Y el extracto en
    # PDF y la foto de la cédula son los dos soportes más comunes que hay.
    #
    # Fuera del hook no bloquea: ahí el escaneo es informativo y el usuario
    # está mirando la salida.
    if args.staged and opacas:
        print(f"⚠ {opacas} archivo(s) del índice que este escáner NO PUDO LEER.")
        print()
        print("  El commit se detiene: no se puede aprobar lo que no se revisó.")
        print("  Míralos a mano y, si están bien, saca el archivo del índice o")
        print("  commitea con --no-verify a sabiendas de lo que llevas.")
        return 1

    print(f"✓ Sin datos personales de confianza alta en {revisados} archivo(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
