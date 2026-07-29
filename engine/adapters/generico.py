"""Adaptador genérico: cualquier CSV con fecha, descripción y monto.

Es el que atrapa lo que ningún adaptador específico reconoce. Intenta
adivinar las columnas por nombre; si no lo logra, pide un mapeo explícito.

Todo lo que importa queda en categoría 'desconocido' a propósito: prefiere
que clasifiques a mano antes que adivinar mal el signo de un ingreso.
"""

from __future__ import annotations

import csv
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..ledger import Movimiento

NOMBRE = "Genérico (CSV)"

ALIAS = {
    "fecha": ["fecha", "date", "fecha_operacion", "fecha operación", "fecha movimiento",
              "transaction date", "posting date", "fecha de transaccion"],
    "descripcion": ["descripcion", "descripción", "description", "concepto",
                    "detalle", "narrative", "memo", "referencia"],
    "monto": ["monto", "valor", "amount", "importe", "debito_credito", "value",
              "monto_total", "total"],
    "moneda": ["moneda", "currency", "divisa", "ccy"],
    "contraparte": ["contraparte", "beneficiario", "counterparty", "payee",
                    "tercero", "nombre"],
}

# Forma válida de un monto ANTES de normalizar: dígitos ASCII separados por
# un solo punto o una sola coma. Excluye notación científica, nan/inf,
# guiones bajos, separadores repetidos y dígitos no ASCII.
_TOKEN = re.compile(r"[0-9]+(?:[.,][0-9]+)*")

# Colombia no tiene horario de verano: UTC-5 todo el año.
HORA_COLOMBIA = timezone(timedelta(hours=-5))

FORMATOS_FECHA = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d",
    "%d/%m/%y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
]


def _norm(s: str) -> str:
    return s.strip().lower().replace("_", " ")


def _mapear(cabeceras: list[str]) -> dict[str, str]:
    mapa = {}
    normalizadas = {_norm(c): c for c in cabeceras}
    for campo, alias in ALIAS.items():
        for a in alias:
            if a in normalizadas:
                mapa[campo] = normalizadas[a]
                break
    return mapa


# Fecha numérica de tres grupos: 01/05/2025. Es la forma ambigua.
_FECHA_NUMERICA = re.compile(r"^\s*(\d{1,4})[/-](\d{1,2})[/-](\d{2,4})")


def convencion_de_fecha(textos) -> tuple[str | None, list[str]]:
    """¿El archivo escribe dd/mm o mm/dd? Lo decide el ARCHIVO, no la fila.

    Misma clase de problema que el separador decimal, y sin resolver hasta
    ahora. `FORMATOS_FECHA` prueba `%d/%m/%Y` antes que `%m/%d/%Y`, así que
    un export en mm/dd —Payoneer, PayPal, cualquier reporte gringo— se lee
    fila por fila:

        01/05/2025  → 5 de enero      (era 1 de mayo)
        01/13/2025  → 13 de enero     (correcto, dd/mm no aplica)
        03/09/2025  → 9 de marzo      (era 3 de septiembre)

    Dos filas transpuestas y una correcta en el MISMO archivo, sin un solo
    aviso. Y mover un movimiento de mes no es cosmético: en la frontera del
    año lo saca del año gravable, y con TRM diaria le cambia la tasa.

    La señal que lo resuelve es la misma de siempre: mirar el archivo
    completo. Un solo `13/01` prueba dd/mm, y un solo `01/13` prueba mm/dd.

    Devuelve ("dmy" | "mdy" | None, avisos). None significa indecidible: se
    usa el orden por defecto y se avisa.
    """
    dmy = mdy = 0
    ambiguos = 0
    for crudo in textos:
        m = _FECHA_NUMERICA.match(str(crudo or ""))
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 31 or (a > 12 and b > 12):
            continue                      # ISO o basura: no vota
        if a > 12:
            dmy += 1
        elif b > 12:
            mdy += 1
        else:
            ambiguos += 1

    avisos: list[str] = []
    if dmy and mdy:
        avisos.append(
            f"El archivo trae fechas que solo tienen sentido como dd/mm "
            f"({dmy}) Y fechas que solo tienen sentido como mm/dd ({mdy}). No "
            f"se deduce una convención: revisa la columna de fecha antes de "
            f"dar el ledger por bueno, porque cambiar de mes un movimiento le "
            f"cambia la TRM y puede sacarlo del año gravable."
        )
        return None, avisos
    if dmy:
        return "dmy", avisos
    if mdy:
        avisos.append(
            f"El archivo usa fechas en formato mm/dd (lo delatan {mdy} fila(s) "
            f"con día mayor que 12). Se leen así. Si en realidad eran dd/mm, "
            f"los movimientos quedaron en el mes equivocado."
        )
        return "mdy", avisos
    if ambiguos:
        avisos.append(
            f"Las {ambiguos} fecha(s) numéricas del archivo son ambiguas: "
            f"ninguna tiene un día mayor que 12, así que nada distingue dd/mm "
            f"de mm/dd. Se leen como dd/mm, que es lo colombiano. Si el export "
            f"es de una plataforma gringa, verifica un par contra el original."
        )
    return None, avisos


def parse_fecha(texto: str, convencion: str | None = None):
    """Fecha de un movimiento, en hora de Colombia.

    Los exports de Deel y Wise traen marcas ISO con zona ("2026-01-01T02:30:00Z").
    Cortar la cadena a 19 caracteres descartaba el offset y dejaba la fecha en
    UTC: en la frontera del año gravable eso mueve un movimiento de diciembre
    a enero, y `filtrar_anio` lo bota del ledger.

    `convencion` viene de `convencion_de_fecha()`, o sea de lo que el archivo
    entero prueba. Nunca de una suposición del adaptador.
    """
    texto = texto.strip()
    if not texto:
        raise ValueError("fecha vacía")

    iso = texto.replace("Z", "+00:00")
    try:
        momento = datetime.fromisoformat(iso)
    except ValueError:
        momento = None
    if momento is not None:
        if momento.tzinfo is not None:
            momento = momento.astimezone(HORA_COLOMBIA)
        return momento.date()

    formatos = list(FORMATOS_FECHA)
    if convencion == "mdy":
        formatos = ["%m/%d/%Y", "%m/%d/%y"] + [f for f in formatos
                                               if f not in ("%m/%d/%Y",)]
    for fmt in formatos:
        try:
            recorte = texto[:19] if (" " in texto or "T" in texto) else texto
            return datetime.strptime(recorte, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha no reconocida: {texto!r}")


def _limpiar(texto: str) -> tuple[str, bool] | None:
    """Quita adornos y signo. Devuelve (dígitos y separadores, negativo).

    None si la celda está vacía o es un guion de relleno. Lanza ValueError si
    hay paréntesis Y signo, que es el único adorno genuinamente ambiguo.
    """
    original = str(texto)
    t = original.strip().replace("$", "").replace(" ", "").replace("\xa0", "")
    if not t or t in {"-", "—", "N/A", "n/a"}:
        return None

    entre_parentesis = t.startswith("(") and t.endswith(")")
    if entre_parentesis:
        t = t[1:-1]

    negativo = entre_parentesis
    if t.startswith(("-", "+")):
        if entre_parentesis:
            raise ValueError(
                f"{original!r} no es un monto reconocible: tiene paréntesis Y "
                f"signo, y no se sabe cuál manda."
            )
        negativo = t[0] == "-"
        t = t[1:]
    return t, negativo


def _forma(t: str) -> tuple[list[str], list[str], list[int]] | None:
    """(grupos, separadores, índices decimales) de un token ya limpio.

    None si el token no tiene la forma de un monto. Un separador seguido de
    exactamente tres dígitos es de miles; cualquier otro tamaño lo delata
    como decimal. El decimal solo puede ser el último separador.
    """
    if not _TOKEN.fullmatch(t):
        return None
    grupos = re.split(r"[.,]", t)
    seps = [c for c in t if c in ".,"]
    decimales = [i for i, g in enumerate(grupos[1:]) if len(g) != 3]
    return grupos, seps, decimales


# Monedas cuya unidad mínima hace que un monto de tres cifras con "decimales"
# sea imposible. El peso colombiano se mueve en miles: un movimiento bancario
# de "1,234" no son un peso con veintitrés centavos, son mil doscientos
# treinta y cuatro pesos. Es la misma clase de banda de plausibilidad que
# TRM_MINIMA/TRM_MAXIMA en trm.py, aplicada al monto en vez de a la tasa.
SIN_FRACCION_SIGNIFICATIVA = {"COP", "CLP", "PYG", "IDR", "VND", "KRW", "JPY"}


def _decimal_por_tipo(seps: list[str]) -> list[int]:
    """Índice del separador decimal cuando lo delata su TIPO, no su longitud.

    Tres decimales CON separador de miles —"1,234.500", "1.234,500"— tienen
    todos los grupos de tres dígitos, así que `_forma` no ve ningún decimal y
    el número caía en «mezcla puntos y comas como separadores de miles».

    Lo desambigua el tipo: los separadores de miles de un número son todos
    iguales, así que un último separador distinto de los anteriores solo
    puede ser el decimal.

    **Vive acá, en una sola función, porque la primera versión de esta regla
    se escribió dentro de `parse_monto` y NO en `convencion_del_archivo`.**
    El resultado fue peor que no haberla escrito: el votante seguía metiendo
    la coma Y el punto en `miles`, así que tiraba la evidencia más fuerte del
    archivo, devolvía `None` sin un solo aviso, y en ese mismo archivo
    "2.500" pasaba de leerse como 2,5 a leerse como 2.500 — factor mil, con
    código de salida 0. Antes del arreglo a medias, esa fila fallaba
    ruidosamente y salía 1.

    Es literalmente la ley de este proyecto: los hallazgos más graves de cada
    ronda son arreglos de la ronda anterior aplicados a medias. Si vas a
    agregar una señal nueva de desambiguación, agrégala acá y comprueba que
    los dos lados la usen.
    """
    if len(seps) > 1 and seps[-1] != seps[0] and len(set(seps[:-1])) == 1:
        return [len(seps) - 1]
    return []


def _relleno_de_ceros(entero: str) -> bool:
    """¿La parte entera viene rellena con ceros a la izquierda?

    "054.937" y "0054.937" son montos con cero de relleno —los extractos los
    traen— y leerlos como decimales los divide por mil. El relleno solo
    existe sobre enteros: nadie escribe 0,5 como "00,5".

    Es la señal que faltaba y que costó una regresión: la excepción se
    escribió como `startswith("0")`, que también atrapa al cero solo, y
    "054.937" pasó a valer 55 pesos.
    """
    return len(entero) > 1 and entero[0] == "0"


def _resolver_ambiguo(entero: str, sep: str, sep_decimal: str | None,
                      moneda: str | None) -> list[int]:
    """Un separador con tres dígitos detrás: ¿miles o decimal?

    Devuelve [0] si es decimal, [] si es de miles. Es el único punto del
    parser donde una decisión equivocada cambia el valor por un factor de
    mil, así que vive aparte y con las señales en orden explícito.
    """
    # "0.500": ningún grupo de miles empieza en cero solo. Es decimal.
    if entero == "0":
        return [0]
    # "054.937": cero de relleno, o sea entero. Es de miles.
    if _relleno_de_ceros(entero):
        return []
    # "12500.750": cinco dígitos de parte entera no son un grupo de miles.
    if len(entero) > 3:
        return [0]
    # Banda de moneda: un movimiento en pesos de "1,234" no es un peso con
    # veintitrés centavos.
    if (moneda or "").strip().upper() in SIN_FRACCION_SIGNIFICATIVA:
        return []
    # Y solo al final, lo que el ARCHIVO haya probado.
    return [0] if sep_decimal == sep else []


def parse_monto(texto: str, sep_decimal: str | None = None,
                moneda: str | None = None) -> float:
    """Convierte un monto a float. Formato colombiano y anglosajón.

    La decisión la toma la ESTRUCTURA del número, no una pista externa:

        Un separador seguido de exactamente TRES dígitos es de miles.
        Un separador seguido de uno, dos o cuatro o más dígitos es decimal.
        El decimal solo puede ser el último separador, y solo puede haber uno.

    Con eso, todo se resuelve sin ambigüedad y en las dos convenciones:

        "1.234.567"    → 1234567      tres y tres: miles
        "1.234.567,89" → 1234567.89   miles, miles, decimal
        "1,234,567.89" → 1234567.89   igual al revés
        "3800.00"      → 3800.0       dos dígitos detrás: decimal
        "1,50"         → 1.5
        "0.00"         → 0.0
        "1.2.3"        → error        el primer separador sería decimal y no es el último
        "12,34,567"    → error        mismo motivo
        "1..2"         → error

    Queda UN caso genuinamente ambiguo: un solo separador seguido de tres
    dígitos, con parte entera de una a tres cifras. "1.234" vale mil
    doscientos treinta y cuatro en Colombia y uno coma doscientos treinta y
    cuatro en inglés, y la forma no lo dice. Es la forma de casi todo monto
    colombiano por debajo del millón, así que resolverlo mal no es un caso
    raro: es la mitad de un extracto.

    Se resuelve por tres señales, en este orden —ver `_resolver_ambiguo`— y
    ninguna es una constante del adaptador:

      1. La estructura del propio número. "0.500" empieza en cero solo, y un
         grupo de miles no lo hace: es decimal. "054.937" empieza en cero
         PERO tiene más dígitos, o sea que es relleno, y el relleno solo
         existe sobre enteros: es de miles. "12500.750" tiene cinco dígitos
         de parte entera, así que tampoco es un grupo de miles: es decimal.
      2. La MONEDA. Un movimiento en pesos de "1,234" no son un peso con
         veintitrés centavos. Ver SIN_FRACCION_SIGNIFICATIVA.
      3. `sep_decimal`, que ahora solo puede venir de
         `convencion_del_archivo()` —o sea, de lo que el archivo entero
         PRUEBA— y no de una suposición del adaptador. Esa era la causa
         raíz: con `sep_decimal="."` fijo, un export de Deel reguardado
         desde Excel en locale español declaraba "82.000" USD como 82 USD,
         un factor de mil, sin una sola advertencia. Y en el mismo archivo
         de Bancolombia, "150,000" salía 150 mientras "2,500,000" salía
         bien: corrupción parcial que ningún cuadre de totales detecta.

    Si ninguna señal aplica, gana MILES. Un monto con tres decimales es
    rarísimo en dinero; un grupo de miles es lo normal.

    Validación: dígitos ASCII únicamente. `float()` acepta dígitos árabes y
    de ancho completo, y notación científica; nada de eso es un monto que
    deba entrar callado a un ledger.
    """
    original = str(texto)

    def malo(motivo):
        return ValueError(f"{original!r} no es un monto reconocible: {motivo}.")

    limpio = _limpiar(original)
    if limpio is None:
        return 0.0
    t, negativo = limpio

    forma = _forma(t)
    if forma is None:
        raise malo("solo se aceptan dígitos separados por un punto o una coma")
    grupos, seps, decimales = forma

    if not decimales and len(seps) == 1:
        decimales = _resolver_ambiguo(grupos[0], seps[0], sep_decimal, moneda)

    decimales = decimales or _decimal_por_tipo(seps)

    if len(decimales) > 1:
        raise malo("hay más de un separador decimal")
    if decimales and decimales[0] != len(seps) - 1:
        raise malo(
            f"el separador {seps[decimales[0]]!r} parece decimal pero no es el "
            f"último: los grupos de miles llevan exactamente tres dígitos"
        )

    if decimales:
        entero_grupos, fraccion = grupos[:-1], grupos[-1]
        seps_miles = seps[:-1]
    else:
        entero_grupos, fraccion = grupos, ""
        seps_miles = seps

    if seps_miles and len(set(seps_miles)) > 1:
        raise malo("mezcla puntos y comas como separadores de miles")
    # El primer grupo se mide SIN sus ceros de relleno: "0054.937" es un
    # monto de cinco cifras escrito con relleno, no un agrupamiento
    # malformado. Los demás grupos sí van tal cual, porque un cero a la
    # izquierda dentro de un grupo de miles es normal ("1.054.937").
    primero = entero_grupos[0].lstrip("0") or "0"
    if len(entero_grupos) > 1 and len(primero) > 3:
        raise malo(f"el primer grupo de miles tiene {len(primero)} dígitos")

    valor = float("".join(entero_grupos) + ("." + fraccion if fraccion else ""))
    if not math.isfinite(valor):
        raise malo("el número es tan grande que no cabe en un float")
    return -valor if negativo else valor


def convencion_del_archivo(valores) -> tuple[str | None, list[str]]:
    """Separador decimal que el ARCHIVO prueba, y los avisos del caso.

    Ninguna celda por separado puede resolver "150,000". El archivo entero
    sí: si en otra fila aparece "2,500,000" —dos comas seguidas de tres
    dígitos— entonces la coma es de miles en este archivo, y "150,000" son
    ciento cincuenta mil. Y al revés: si aparece "3800.00", el punto es
    decimal y "150.000" son ciento cincuenta.

    Devuelve None cuando el archivo no prueba nada o se contradice. None NO
    significa "usa el default del adaptador": significa que decide la
    estructura, que es lo único que no se puede equivocar por convención.

    Los avisos existen porque una lectura ambigua que cambia el resultado por
    un factor de mil no puede ser silenciosa. La corrupción parcial —unas
    filas bien y otras mal en el mismo archivo— no la detecta ningún cuadre
    de totales.
    """
    decimales: set[str] = set()
    miles: set[str] = set()
    ambiguos = 0

    for crudo in valores:
        try:
            limpio = _limpiar(crudo if crudo is not None else "")
        except ValueError:
            continue
        if limpio is None:
            continue
        forma = _forma(limpio[0])
        if forma is None:
            continue
        grupos, seps, idx = forma
        if not seps:
            continue
        # Un token malformado no vota: "1.2.3" no dice nada de la convención.
        if len(idx) > 1 or (idx and idx[0] != len(seps) - 1):
            continue
        # La MISMA regla que usa `parse_monto`, desde la misma función. Este
        # `or` es el arreglo de una regresión propia: la señal del tipo se
        # escribió solo en el parser, así que acá "1,234.500" metía la coma Y
        # el punto en `miles`, se tiraba la evidencia más fuerte del archivo,
        # se devolvía None SIN AVISO, y en ese mismo archivo "2.500" pasaba
        # de leerse 2,5 a leerse 2.500. Factor mil, con código de salida 0 —
        # y antes de "arreglar" el parser esa fila fallaba ruidosamente.
        idx = idx or _decimal_por_tipo(seps)
        if idx:
            decimales.add(seps[-1])
            miles.update(seps[:-1])
        elif len(seps) == 1:
            entero = grupos[0]
            if _relleno_de_ceros(entero):
                # "054.937" no vota como decimal: es un entero con relleno, y
                # dejarlo votar contaminaría la lectura del resto del archivo.
                miles.add(seps[0])
            elif len(entero) > 3 or entero == "0":
                decimales.add(seps[0])
            else:
                ambiguos += 1
        else:
            miles.update(seps)

    avisos: list[str] = []
    if len(decimales) > 1:
        avisos.append(
            "El archivo usa el punto Y la coma como separador decimal en filas "
            "distintas. No se deduce una convención: los montos ambiguos se "
            "leen por estructura (un separador con tres dígitos = miles). "
            "Revisa la columna de monto antes de dar el ledger por bueno."
        )
        return None, avisos

    sep = next(iter(decimales)) if decimales else None
    if sep and sep in miles:
        avisos.append(
            f"El archivo usa {sep!r} como separador decimal en unas filas y "
            f"como separador de miles en otras. Los montos ambiguos se leen "
            f"por estructura. Revisa la columna de monto."
        )
        return None, avisos

    if ambiguos:
        if sep:
            avisos.append(
                f"{ambiguos} monto(s) con un solo {sep!r} seguido de tres "
                f"dígitos se leyeron como DECIMALES, porque otras filas del "
                f"mismo archivo prueban que {sep!r} es el separador decimal. "
                f"Si en realidad eran miles, cada uno quedó dividido por mil: "
                f"compáralos contra el extracto original."
            )
        elif not miles:
            avisos.append(
                f"{ambiguos} monto(s) tienen un solo separador seguido de tres "
                f"dígitos y el archivo no trae ninguna otra fila que diga si es "
                f"de miles o decimal. Se leyeron como MILES, que es lo normal "
                f"en un extracto colombiano. Si tu archivo usa decimales de "
                f"tres cifras, cada uno quedó multiplicado por mil."
            )
    return sep, avisos


def detecta(cabeceras: list[str], nombre: str = "") -> bool:
    mapa = _mapear(cabeceras)
    return "fecha" in mapa and "monto" in mapa


# Secuencias que delatan un utf-8 leído como latin-1 o cp1252: la "é" de
# "descripción" en utf-8 son dos bytes que en latin-1 se ven como "Ã©".
MOJIBAKE = re.compile(r"[ÃÂ][\x80-\xbf]|ï»¿|â€")


def _saltar_preambulo(f) -> None:
    """Deja el archivo posicionado en la línea de la CABECERA.

    `leer_cabeceras` —que decide qué adaptador reclama el archivo— salta las
    líneas vacías; `csv.DictReader` no. Con una línea en blanco arriba, la
    detección veía `['Fecha','Documento','Descripcion','Valor']` y la
    importación veía `[]`, y el mensaje de error decía «no tiene columnas
    reconocibles. Columnas: []» — contradiciéndose con lo que el propio
    despachador acababa de leer.

    No es un caso raro: más de un banco colombiano encabeza el extracto con
    un preámbulo ("BANCOLOMBIA S.A. - EXTRACTO", "Cuenta: ...") seguido de
    una línea vacía.
    """
    while True:
        pos = f.tell()
        linea = f.readline()
        if not linea:                 # archivo vacío: que falle más adelante
            f.seek(0)
            return
        if linea.strip() and linea.count(",") + linea.count(";") >= 1:
            f.seek(pos)
            return
        if not linea.strip():
            continue
        # Línea con texto pero sin separadores: preámbulo del banco.


def abrir_csv(ruta: Path, avisos: list[str] | None = None):
    """Abre un CSV probando codificaciones, en vez de mutilar el texto.

    Con `errors="replace"` un extracto en latin-1 —que es lo que exporta más
    de un banco colombiano— perdía todas las tildes y con ellas las palabras
    que usan las reglas de clasificación. Peor: la detección del adaptador
    fallaba y el archivo caía al genérico.

    Ojo con la cadena de respaldo: latin-1 acepta CUALQUIER byte, así que
    nunca lanza `UnicodeDecodeError` y el `errors="replace"` del final es
    inalcanzable. Eso no es un problema de código muerto: significa que un
    utf-8 corrupto se lee sin error como mojibake y entra al ledger con las
    descripciones rotas, que son las que usan las reglas de clasificación.
    Por eso, cuando se llega a latin-1, se MIRA el texto y se avisa.
    """
    avisos = avisos if avisos is not None else []
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(ruta, newline="", encoding=encoding) as f:
                texto = f.read()
        except UnicodeDecodeError:
            continue
        # La revisión corre en TODAS las codificaciones, no solo en el
        # respaldo. El caso más común es el doble encoding: un utf-8 leído
        # como latin-1 y vuelto a guardar como utf-8. El archivo resultante
        # es utf-8 VÁLIDO —decodifica sin un solo error— y dice "RETENCIÃ³N".
        # Mirar solo la ruta de respaldo dejaba pasar justo ese.
        roto = MOJIBAKE.search(texto)
        if roto:
            avisos.append(
                f"{ruta.name} se leyó como {encoding} y el texto quedó con "
                f"caracteres rotos (por ejemplo {roto.group(0)!r}). Suele ser "
                f"un archivo utf-8 guardado dos veces con la codificación "
                f"equivocada. Las descripciones son lo que usan las reglas de "
                f"clasificación, así que revisa las categorías del ledger "
                f"antes de calcular."
            )
        return open(ruta, newline="", encoding=encoding)
    return open(ruta, newline="", encoding="utf-8", errors="replace")


def moneda_de(fila: dict, columna: str | None, defecto: str) -> str:
    """Moneda de una fila. Vacía NO es el defecto: es una fila ilegible.

    `(fila.get(c_moneda) or "USD")` parecía inofensivo y era un factor de
    ~4.000. La guarda de `ErrorSinRespaldo` solo dispara cuando falta la
    COLUMNA entera; una celda vacía en una fila suelta —lo normal en un
    export de plataforma de pagos— caía al defecto sin decir nada. En un
    archivo colombiano con una sola celda vacía, esa fila salía multiplicada
    por la TRM: corrupción parcial dentro del mismo archivo, que ningún
    cuadre de totales detecta.

    Es la misma regla que ya aplica a los montos: cuando el dato no está, no
    se supone. Se marca la fila y se cuenta.
    """
    if columna is None:
        return defecto
    crudo = (fila.get(columna) or "").strip().upper()
    if not crudo:
        raise ValueError(
            "la celda de moneda está vacía y el archivo SÍ trae columna de "
            "moneda. No se supone una: suponerla cambia el monto por el "
            "factor de la TRM. Complétala en el CSV."
        )
    if not re.fullmatch(r"[A-Z]{3}", crudo):
        raise ValueError(
            f"{crudo!r} no es un código de moneda ISO de tres letras (COP, "
            f"USD, EUR)."
        )
    return crudo


def aviso_de_filas_saltadas(nombre: str, malas: list[str], leidas: int) -> str:
    """Mensaje único para las filas que no se pudieron leer.

    Una celda mala en la fila 200 de un export abortaba el archivo entero y
    borraba doce meses de ingreso. Saltarla es lo correcto, pero saltarla en
    silencio es peor que abortar: el ledger queda incompleto y cuadra consigo
    mismo. Por eso el mensaje dice cuántas, cuáles y qué hacer.
    """
    muestra = "; ".join(malas[:3])
    resto = f" (y {len(malas) - 3} más)" if len(malas) > 3 else ""
    return (
        f"{nombre}: {len(malas)} fila(s) de {leidas + len(malas)} no se pudieron "
        f"leer y NO están en el ledger. {muestra}{resto}. Corrígelas en el CSV y "
        f"vuelve a importar: mientras tanto faltan movimientos."
    )


def importar(ruta: Path, mapa: dict[str, str] | None = None,
             avisos: list[str] | None = None) -> list[Movimiento]:
    avisos = avisos if avisos is not None else []
    with abrir_csv(ruta, avisos) as f:
        _saltar_preambulo(f)
        lector = csv.DictReader(f)
        cols = mapa or _mapear(lector.fieldnames or [])
        if "fecha" not in cols or "monto" not in cols:
            raise ValueError(
                f"No pude identificar las columnas de fecha y monto en {ruta.name}. "
                f"Columnas: {lector.fieldnames}. Pasa un mapeo explícito: "
                f"importar(ruta, {{'fecha': 'MiColumnaFecha', 'monto': 'MiColumnaValor'}})"
            )
        # Se lee el archivo completo antes de convertir un solo monto: la
        # convención de separadores es una propiedad del ARCHIVO y ninguna
        # celda por separado la puede resolver.
        filas = list(lector)
        sep, avisos_sep = convencion_del_archivo(
            fila.get(cols["monto"], "") for fila in filas
        )
        conv_fecha, avisos_fecha = convencion_de_fecha(
            fila.get(cols["fecha"], "") for fila in filas
        )
        avisos += [f"{ruta.name}: {a}" for a in avisos_sep + avisos_fecha]

        movimientos = []
        descartadas = 0
        malas: list[str] = []
        for i, fila in enumerate(filas, start=2):
            crudo = (fila.get(cols["fecha"]) or "").strip()
            if not crudo:
                continue
            try:
                moneda = moneda_de(fila, cols.get("moneda"), "COP")
                fecha = parse_fecha(crudo, conv_fecha)
                monto = parse_monto(fila.get(cols["monto"], "0"), sep, moneda)
            except ValueError as e:
                malas.append(f"línea {i}: {e}")
                continue
            if monto == 0:
                # Las filas en cero se descartan, pero no en silencio: si un
                # extracto entero sale vacío, saber cuántas se botaron es la
                # diferencia entre "no había movimientos" y "se leyó mal la
                # columna de monto".
                descartadas += 1
                continue
            movimientos.append(Movimiento(
                fecha=fecha,
                descripcion=(fila.get(cols.get("descripcion", ""), "") or "").strip(),
                monto_origen=monto,
                moneda=moneda,
                contraparte=(fila.get(cols.get("contraparte", ""), "") or "").strip(),
                categoria="desconocido",
                fuente=ruta.name,
            ))
    if malas and not movimientos:
        raise ValueError(
            f"{ruta.name}: ninguna de las {len(malas)} filas con datos se pudo "
            f"leer. La primera dice — {malas[0]}. Casi siempre es la columna de "
            f"monto o de fecha mal identificada: columnas disponibles {cols}."
        )
    if malas:
        avisos.append(aviso_de_filas_saltadas(ruta.name, malas, len(movimientos)))
    if descartadas and not movimientos:
        raise ValueError(
            f"{ruta.name}: las {descartadas} filas con datos tienen monto cero. "
            f"Probablemente se identificó mal la columna de monto — columnas "
            f"disponibles: {cols}."
        )
    return movimientos
