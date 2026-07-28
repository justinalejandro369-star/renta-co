"""Construcción del ledger: movimientos crudos → pesos con TRM diaria.

Un ledger es la lista de todos los movimientos del año gravable, cada uno
convertido a COP con la TRM de SU fecha, y clasificado en una categoría
tributaria. Es el insumo de la depuración y la prueba de dónde salió cada
cifra si la DIAN pregunta.

Categorías:
    ingreso_trabajo     honorarios, compensación por servicios
    ingreso_capital     rendimientos, dividendos, intereses
    costo_contratista   pago a una persona — exige PILA (art. 108 par. 2)
    costo               comisión, insumo, otro gasto deducible
    gasto_personal      no deducible; se registra para no confundirlo con costo
    traslado            movimiento entre cuentas propias: NI ingreso NI gasto
    retencion           retención practicada por un tercero
    desconocido         requiere clasificación manual
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .trm import TRM

CATEGORIAS = {
    "ingreso_trabajo": "Renta de trabajo (honorarios / servicios)",
    "ingreso_capital": "Renta de capital",
    # `costo_contratista` existe separado de `costo` porque es el único que
    # dispara R-02, y R-02 es «el requisito que tumba más deducciones»: el
    # art. 108 par. 2 exige verificar los aportes a seguridad social de cada
    # contratista, y si no cotizaron la DIAN puede rechazar la TOTALIDAD del
    # costo, con lo que la Ruta A pierde su fundamento.
    #
    # Estaban fundidos en `costo`, así que `a_perfil()` los mandaba todos a
    # `costos.otros` y `verificar_obligaciones` —que mira
    # `costos.pagos_a_contratistas`— nunca emitía R-02 por el flujo que la
    # propia herramienta documenta. Verificado: dos contratistas y
    # $79.939.964 de costos, y el riesgo no aparecía en ninguna parte de la
    # salida. Los adaptadores YA distinguían el pago a contratista de la
    # comisión de plataforma y tiraban los dos a la misma categoría.
    "costo_contratista": "Pago a contratista (solo Ruta A — exige PILA, art. 108 par. 2)",
    "costo": "Otro costo o gasto deducible (solo Ruta A)",
    "gasto_personal": "Gasto personal — NO deducible",
    "traslado": "Traslado entre cuentas propias — ni ingreso ni gasto",
    "retencion": "Retención en la fuente practicada",
    "desconocido": "Sin clasificar",
}

# Las que se restan como costo en la Ruta A.
COSTOS = ("costo", "costo_contratista")

# El error más caro y más común del perfil freelance.
ADVERTENCIA_TRASLADO = (
    "Los traslados entre cuentas propias NO son ingreso. Contarlos infla la "
    "base gravable. Pero SÍ cuentan como consignación para el umbral de "
    "3.500 UVT de IVA — revisa ambas cosas."
)


@dataclass
class Movimiento:
    fecha: date
    descripcion: str
    monto_origen: float
    moneda: str = "COP"
    categoria: str = "desconocido"
    contraparte: str = ""
    fuente: str = ""          # de qué archivo salió
    trm: float | None = None
    monto_cop: float = 0.0

    def convertir(self, trm: TRM | None) -> "Movimiento":
        if self.moneda.upper() == "COP":
            self.trm = 1.0
            self.monto_cop = round(self.monto_origen)
        else:
            if trm is None:
                raise ValueError(
                    f"Movimiento en {self.moneda} el {self.fecha} sin serie TRM cargada."
                )
            self.trm = trm.de(self.fecha)
            self.monto_cop = round(self.monto_origen * self.trm)
        return self


@dataclass
class Ledger:
    movimientos: list[Movimiento] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def agregar(self, m: Movimiento) -> None:
        self.movimientos.append(m)

    def convertir(self, trm: TRM | None) -> "Ledger":
        for m in self.movimientos:
            m.convertir(trm)
        return self

    def total(self, categoria: str) -> float:
        return sum(m.monto_cop for m in self.movimientos if m.categoria == categoria)

    def resumen(self) -> dict[str, float]:
        """Total por categoría, incluyendo las que suman cero pero existen.

        Una categoría cuyos movimientos se cancelan entre sí desaparecía del
        resumen, que es exactamente lo que pasa con los traslados cuando se
        importan la plataforma y el banco.
        """
        return {
            c: self.total(c) for c in CATEGORIAS
            if any(m.categoria == c for m in self.movimientos)
        }

    def sin_clasificar(self) -> list[Movimiento]:
        return [m for m in self.movimientos if m.categoria == "desconocido"]

    def entradas_por_fuente(self) -> dict[str, float]:
        """Entradas positivas agrupadas por archivo de origen."""
        por_fuente: dict[str, float] = {}
        for m in self.movimientos:
            if m.monto_cop > 0:
                por_fuente[m.fuente] = por_fuente.get(m.fuente, 0) + m.monto_cop
        return por_fuente

    def consignaciones(self) -> dict:
        """Insumo para el umbral de 3.500 UVT — NO un número listo para usar.

        El art. 437 par. 3 num. 6 ET no habla de "todo lo que entró". Habla de
        «consignaciones bancarias, depósitos o inversiones financieras
        PROVENIENTES DE ACTIVIDADES GRAVADAS CON EL IMPUESTO SOBRE LAS
        VENTAS -IVA». Ese calificador decide el caso y se omite con
        frecuencia:

          · Un traslado entre cuentas propias no proviene de una actividad
            gravada.
          · Un préstamo recibido tampoco.
          · Si la actividad es exportación de servicios (art. 481 lit. c) o
            está excluida, el numerador puede ser CERO aunque por la cuenta
            pasen cientos de millones.

        Y hay un problema aritmético además del legal: si se importan el
        export de la plataforma Y el extracto bancario donde aterrizó ese
        mismo giro, el dinero se cuenta dos veces. Es el flujo que la propia
        herramienta recomienda, así que la duplicación es el caso normal, no
        el excepcional.

        Por eso esto devuelve un desglose con sus advertencias, y no un total
        que invite a compararlo con el umbral sin pensar.
        """
        por_fuente = self.entradas_por_fuente()
        bruto = sum(por_fuente.values())

        avisos = []
        if len(por_fuente) > 1:
            avisos.append(
                "Hay entradas de más de un archivo. Si importaste el export de "
                "la plataforma Y el extracto del banco donde aterrizó ese mismo "
                "giro, el dinero está contado dos veces. Revisa el desglose por "
                "fuente antes de comparar contra el umbral."
            )
        if any(m.categoria == "traslado" for m in self.movimientos):
            avisos.append(
                "Hay traslados entre cuentas propias. Consignan, pero NO "
                "provienen de una actividad gravada con IVA, así que no cuentan "
                "para el umbral del art. 437 par. 3 num. 6."
            )
        avisos.append(
            "Del total de arriba, para el umbral solo cuenta lo PROVENIENTE DE "
            "ACTIVIDADES GRAVADAS CON IVA. Si tu actividad es exportación de "
            "servicios (art. 481 lit. c) o está excluida, esa porción puede ser "
            "cero. Sepáralo con tu contador antes de concluir nada."
        )

        return {
            "entradas_brutas": round(bruto),
            "por_fuente": {k: round(v) for k, v in por_fuente.items()},
            "traslados": round(abs(self.total("traslado"))),
            "avisos": avisos,
            "listo_para_el_umbral": False,
        }

    def validar(self, trm=None) -> list[str]:
        avisos = list(self.avisos) + self.avisos_de_signo()
        if trm is not None:
            huecos = trm.huecos_grandes()
            if huecos:
                fecha, origen, dias = huecos[0]
                avisos.append(
                    f"{len(huecos)} movimiento(s) usaron una TRM de más de 3 días "
                    f"antes de su fecha (el peor: {fecha} tomó la del {origen}, "
                    f"{dias} días atrás). El art. 288 exige la TRM de la fecha de "
                    f"realización: revisa si la serie quedó incompleta antes de "
                    f"dar el ledger por bueno."
                )
        pendientes = self.sin_clasificar()
        if pendientes:
            avisos.append(
                f"{len(pendientes)} movimiento(s) sin clasificar por "
                f"{sum(abs(m.monto_cop) for m in pendientes):,.0f} COP. "
                f"Clasifícalos antes de calcular: un ingreso mal clasificado "
                f"cambia el impuesto."
                .replace(",", ".")
            )
        # Se cuentan los MOVIMIENTOS, no el total: un retiro y su abono se
        # cancelan y dejaban el total en cero, así que el aviso más
        # importante del módulo no se emitía justo en el caso que describe
        # —importar la plataforma y el banco a la vez—.
        if any(m.categoria == "traslado" for m in self.movimientos):
            avisos.append(ADVERTENCIA_TRASLADO)
        fechas = [m.fecha for m in self.movimientos]
        if fechas:
            anios = {f.year for f in fechas}
            if len(anios) > 1:
                avisos.append(
                    f"El ledger mezcla los años {sorted(anios)}. Filtra al año "
                    f"gravable antes de calcular."
                )
        return avisos

    def bloqueantes(self, trm=None) -> list[str]:
        """Los avisos que dejan el ledger INUTILIZABLE para calcular.

        `validar()` mezcla dos cosas distintas: lo que hay que leer y lo que
        hay que arreglar. La advertencia de traslados, por ejemplo, es
        pedagógica y sale siempre que haya un traslado — que es lo normal.

        La separación importa porque el código de salida de `importar` es la
        única señal que ve un agente que encadena `importar` con `calcular`.
        Estaba cableado solo a los fallos de archivo, así que un ledger con
        el 28% de las entradas sin clasificar salía 0. Verificado:
        17.550.000 COP sin clasificar, luz verde.
        """
        bloqueos = []
        pendientes = self.sin_clasificar()
        if pendientes:
            bloqueos.append(
                f"{len(pendientes)} movimiento(s) SIN CLASIFICAR por "
                f"{sum(abs(m.monto_cop) for m in pendientes):,.0f} COP. No están "
                f"sumados en ninguna cifra: clasifícalos en el ledger antes de "
                f"calcular.".replace(",", ".")
            )
        bloqueos += self.avisos_de_signo()
        fechas = [m.fecha for m in self.movimientos]
        if fechas and len({f.year for f in fechas}) > 1:
            bloqueos.append(
                f"El ledger mezcla los años {sorted({f.year for f in fechas})}. "
                f"Filtra al año gravable antes de calcular."
            )
        if trm is not None and trm.huecos_grandes():
            huecos = trm.huecos_grandes()
            fecha, origen, dias = huecos[0]
            bloqueos.append(
                f"{len(huecos)} movimiento(s) usaron una TRM de más de 3 días "
                f"antes de su fecha (el peor: {fecha} tomó la del {origen}). El "
                f"art. 288 exige la TRM de la fecha de realización."
            )
        return bloqueos

    def filtrar_anio(self, anio: int) -> "Ledger":
        return Ledger(
            [m for m in self.movimientos if m.fecha.year == anio], list(self.avisos)
        )

    # Signo que le corresponde a cada categoría, y cómo se llama el
    # movimiento que va al revés. `traslado` y `desconocido` no están: el
    # traslado es de dos patas por definición, y lo sin clasificar ya tiene
    # su propio aviso.
    SIGNO_ESPERADO = {
        "ingreso_trabajo": (+1, "ingresos de trabajo", "una devolución o una nota crédito"),
        "ingreso_capital": (+1, "ingresos de capital", "una reversión de rendimientos"),
        "costo": (-1, "costos", "un reembolso"),
        "costo_contratista": (-1, "pagos a contratistas", "un reembolso"),
        "gasto_personal": (-1, "gastos personales", "un reintegro"),
        "retencion": (-1, "retenciones", "una retención reversada"),
    }

    def avisos_de_signo(self) -> list[str]:
        """Categorías donde entradas y salidas se mezclan.

        Un reembolso dentro de los costos, o una retención reversada, netean
        con el resto. Es lo correcto, pero hay que decirlo: la cifra que sale
        no es la suma de los comprobantes, y el contador va a preguntar.

        Antes esto solo miraba `costo` y `retencion`, y ese hueco se componía
        con el de la clasificación de Deel: un pago SALIENTE clasificado como
        `ingreso_trabajo` metía 10.000.000 + (−3.000.000) = 7.000.000 y
        `validar()` devolvía lista vacía. La cifra equivocada llegaba al
        perfil sin una sola advertencia. Se revisan TODAS las categorías con
        signo esperado, que es la clase del problema.
        """
        avisos = []
        for categoria, (signo, etiqueta, ejemplo) in self.SIGNO_ESPERADO.items():
            contrarios = [m for m in self.movimientos
                          if m.categoria == categoria and m.monto_cop * signo < 0]
            if not contrarios:
                continue
            total = sum(abs(m.monto_cop) for m in contrarios)
            sentido = "NEGATIVO" if signo > 0 else "POSITIVO"
            avisos.append(
                f"{len(contrarios)} movimiento(s) de {etiqueta} vienen en "
                f"{sentido} por {total:,.0f} COP: se tratan como {ejemplo} y "
                f"netean contra el total. Si en realidad están mal "
                f"clasificados, corrígelos antes de calcular."
                .replace(",", ".")
            )
        return avisos

    @staticmethod
    def _neutralizar(valor: str) -> str:
        """Evita que Excel interprete una descripción como fórmula.

        El ledger se lo manda el usuario a su contador por correo. Una
        descripción que empiece por =, +, - o @ la ejecuta la hoja de
        cálculo al abrir el archivo, y esas descripciones vienen de un CSV
        de terceros que nadie revisó.

        El costo conocido: una descripción legítima que empiece por "-" o
        "+" —«-3000 devolución»— sale con un apóstrofo delante y se ve rota.
        Se acepta a propósito. Los cuatro caracteres son los que lista OWASP
        para inyección en CSV, y quitar el "-" y el "+" abre el vector real:
        `-1+1+cmd|' /C calc'!A1` empieza por guion. Una descripción fea es
        más barata que una fórmula ejecutándose en la máquina del contador.
        """
        texto = str(valor)
        return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto

    def escribir_csv(self, ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "fecha", "descripcion", "contraparte", "moneda",
                "monto_origen", "trm", "monto_cop", "categoria", "fuente",
            ])
            for m in sorted(self.movimientos, key=lambda x: x.fecha):
                w.writerow([
                    m.fecha.isoformat(),
                    self._neutralizar(m.descripcion),
                    self._neutralizar(m.contraparte),
                    m.moneda,
                    f"{m.monto_origen:.2f}", f"{m.trm:.2f}" if m.trm else "",
                    m.monto_cop, m.categoria, m.fuente,
                ])

    def a_perfil(self) -> dict:
        """Mapea el ledger a las secciones del perfil.toml."""
        return {
            "ingresos": {
                "rentas_trabajo_honorarios": round(self.total("ingreso_trabajo")),
                "rentas_capital": round(self.total("ingreso_capital")),
            },
            "costos": {
                # Los pagos a contratistas van a SU PROPIO campo, que es el
                # que dispara R-02. Fundidos en `otros`, el riesgo más caro
                # de la Ruta A no se emitía nunca por el flujo documentado.
                "pagos_a_contratistas": round(
                    -sum(m.monto_cop for m in self.movimientos
                         if m.categoria == "costo_contratista")
                ),
                # Suma de salidas, no valor absoluto del neto. Con abs() sobre
                # el total, un reembolso clasificado como costo restaba del
                # gasto deducible en vez de reducirlo explícitamente, y el
                # signo del resultado dependía de cuál pesara más.
                "otros": round(
                    -sum(m.monto_cop for m in self.movimientos
                         if m.categoria == "costo")
                ),
            },
            "anticipos": {
                # Salidas menos devoluciones, igual que en costos. Con
                # abs() por movimiento, una retención reversada sumaba en vez
                # de restar, y esta cifra se descuenta del impuesto.
                "retenciones_practicadas": round(
                    -sum(m.monto_cop for m in self.movimientos
                         if m.categoria == "retencion")
                ),
            },
            # consignaciones_totales_anio NO se llena desde el ledger: exige
            # separar por origen gravado con IVA y descartar duplicados entre
            # fuentes. Lo pone el usuario con su contador. Ver consignaciones().
        }


@dataclass
class Reclasificacion:
    """Qué pasó al reaplicar las correcciones del ledger anterior.

    Es un objeto y no un entero porque el entero solo sabía contar los
    éxitos, y el mensaje que lo imprimía estaba dentro de un `if aplicadas`.
    El caso que importa —CERO conservadas porque el archivo no se pudo
    leer— era exactamente el que no decía nada.
    """
    conservadas: int = 0
    perdidas: list[str] = field(default_factory=list)
    ilegibles: list[str] = field(default_factory=list)

    def resumen(self) -> str:
        partes = [f"{self.conservadas} clasificación(es) conservadas"]
        if self.perdidas:
            partes.append(f"{len(self.perdidas)} PERDIDAS")
        if self.ilegibles:
            partes.append(f"{len(self.ilegibles)} fila(s) ilegibles")
        return ", ".join(partes)

    def avisos(self) -> list[str]:
        avisos = []
        if self.ilegibles:
            avisos.append(
                f"{len(self.ilegibles)} fila(s) del ledger anterior no se "
                f"pudieron leer, así que sus clasificaciones se perdieron. La "
                f"primera: {self.ilegibles[0]}. Pasa casi siempre por abrir el "
                f"CSV en Excel y guardarlo con la configuración regional "
                f"española, que cambia el separador decimal."
            )
        if self.perdidas:
            muestra = "; ".join(self.perdidas[:3])
            resto = f" (y {len(self.perdidas) - 3} más)" if len(self.perdidas) > 3 else ""
            avisos.append(
                f"{len(self.perdidas)} clasificación(es) que habías corregido a "
                f"mano NO se pudieron reaplicar porque su movimiento ya no está "
                f"en el ledger nuevo: {muestra}{resto}. Vuelve a clasificarlas."
            )
        return avisos


def _clave_de(fecha: str, monto: str, moneda: str, fuente: str,
              descripcion: str = "") -> tuple:
    """Lo que identifica un movimiento con independencia de su categoría.

    La DESCRIPCIÓN entra porque es lo único que distingue dos filas que
    coinciden en fecha, monto, moneda y archivo. Sin ella, el desempate
    quedaba solo en el ordinal, y el ordinal se corre: si el usuario borra
    en Excel lo que parece un duplicado, la clasificación de la fila que
    dejó se la lleva OTRO movimiento y el reporte dice «1 conservada».
    Aplicar la categoría al movimiento equivocado y reportar éxito es peor
    que perderla.

    Se normaliza —sin espacios repetidos y en minúscula— porque Excel y los
    bancos cambian el espaciado sin cambiar el movimiento.
    """
    desc = " ".join(str(descripcion or "").split()).lower()
    return (fecha, monto, moneda, fuente, desc)


def _monto_canonico(texto) -> str:
    """Monto de origen como cadena comparable, tolerando locales.

    Se usa `parse_monto` en vez de `float()` porque el usuario abre el ledger
    en Excel para corregir categorías, y Excel lo vuelve a guardar en la
    configuración regional de la máquina: "1500000,00" reventaba `float()`,
    el `continue` se lo tragaba y se perdían TODAS las clasificaciones.
    """
    from .adapters.generico import parse_monto

    return f"{parse_monto(texto):.2f}"


def leer_clasificacion_previa(ruta: Path) -> tuple[dict[tuple, str], list[str]]:
    """Categorías que el usuario ya corrigió a mano en un ledger anterior.

    La herramienta le dice «arréglala ahí y vuelve a correr», y hasta ahora
    `importar` sobreescribía el archivo y tiraba esa corrección a la basura
    sin avisar. Era el único remedio que ofrecía para una clasificación
    equivocada, y no funcionaba.

    La llave identifica el movimiento con independencia de cómo se haya
    clasificado: fecha, monto de origen, moneda y archivo de origen. Y lleva
    además el ORDINAL dentro de su grupo de repetidas, porque dos
    transferencias del mismo monto el mismo día son lo más común de un
    extracto y, con la llave sola, el `dict` se quedaba con la última y se la
    imponía a las dos.

    Devuelve (previas, filas ilegibles). Las ilegibles se devuelven en vez de
    tragárselas: son clasificaciones perdidas y el usuario tiene que saberlo.
    """
    if not ruta.exists():
        return {}, []
    previas: dict[tuple, str] = {}
    ilegibles: list[str] = []
    repetidas: dict[tuple, int] = {}
    # `abrir_csv` y no `open(..., encoding="utf-8")`: el usuario abre este
    # archivo en Excel para corregir categorías —es lo que la herramienta le
    # dice que haga— y Excel en Windows lo guarda en cp1252, o con BOM si
    # elige "CSV UTF-8". Las descripciones colombianas siempre traen tildes,
    # así que el utf-8 duro reventaba con `UnicodeDecodeError`, que el
    # `except OSError` no atrapa: `importar` moría con un mensaje sin
    # archivo, sin causa y sin remedio, y moría igual en TODAS las corridas
    # siguientes. La función que resuelve esto vivía cinco archivos más allá.
    from .adapters.generico import abrir_csv

    try:
        with abrir_csv(ruta) as f:
            for n, fila in enumerate(csv.DictReader(f), start=2):
                try:
                    base = _clave_de(
                        fila["fecha"],
                        _monto_canonico(fila["monto_origen"]),
                        fila["moneda"],
                        fila["fuente"],
                        fila.get("descripcion", ""),
                    )
                except (KeyError, TypeError, ValueError) as e:
                    ilegibles.append(f"línea {n}: {e}")
                    continue
                ordinal = repetidas.get(base, 0)
                repetidas[base] = ordinal + 1
                if fila.get("categoria"):
                    previas[base + (ordinal,)] = fila["categoria"]
    except OSError as e:
        return {}, [f"{ruta.name} no se pudo abrir: {e}"]
    return previas, ilegibles


def aplicar_clasificacion_previa(
    ledger: Ledger, previas: dict[tuple, str], ilegibles: list[str] | None = None,
) -> Reclasificacion:
    """Reaplica las categorías corregidas a mano.

    Recorre el ledger en el mismo orden en que `escribir_csv` lo escribió
    —ordenado por fecha, y estable dentro del día— para que el ordinal de
    las repetidas signifique lo mismo de un lado y del otro.
    """
    resultado = Reclasificacion(ilegibles=list(ilegibles or []))
    if not previas:
        return resultado

    pendientes = dict(previas)
    repetidas: dict[tuple, int] = {}
    for m in sorted(ledger.movimientos, key=lambda x: x.fecha):
        base = _clave_de(m.fecha.isoformat(), f"{m.monto_origen:.2f}",
                         m.moneda, m.fuente, m.descripcion)
        ordinal = repetidas.get(base, 0)
        repetidas[base] = ordinal + 1
        anterior = pendientes.pop(base + (ordinal,), None)
        if anterior is None:
            continue
        if anterior not in CATEGORIAS:
            resultado.perdidas.append(
                f"{m.fecha} {m.descripcion[:30]}: categoría {anterior!r} no existe"
            )
            continue
        if anterior != "desconocido":
            resultado.conservadas += 1
        m.categoria = anterior

    # Lo que sobró son correcciones cuyo movimiento ya no está. Las que
    # decían "desconocido" no eran una corrección y no se reportan.
    for clave, categoria in pendientes.items():
        if categoria == "desconocido":
            continue
        fecha, monto, moneda, fuente, desc, _ = clave
        resultado.perdidas.append(
            f"{fecha} {monto} {moneda} de {fuente} ({desc[:30]}) → {categoria}")
    return resultado


def escribir_sugerencia_perfil(ledger: Ledger, destino: Path,
                               incidencias: list[str] | None = None) -> Path:
    """Escribe las cifras del ledger en formato perfil.toml, para copiar.

    NO sobrescribe el perfil del usuario. Ese paso —revisar cada cifra y
    decidir si entra— es del usuario, y es donde se atrapan las
    clasificaciones equivocadas. Antes este puente no existía: el mapeo del
    ledger al perfil quedaba a cargo del modelo, transcribiendo a mano, que
    es exactamente lo que el proyecto dice no hacer.

    `incidencias` son los archivos que no se importaron y las filas que se
    saltaron. Van en el ENCABEZADO, arriba de todo, porque este archivo es el
    que alguien abre para copiar cifras al perfil: si el ledger está
    incompleto, las cifras de acá lo están, y no hay forma de notarlo mirando
    los números —cuadran entre sí—.
    """
    p = ledger.a_perfil()
    pendientes = ledger.sin_clasificar()
    cons = ledger.consignaciones()

    lineas = [
        "#  SUGERENCIA generada por `renta importar` — NO es tu perfil.",
        "#",
        "#  Revisa cada cifra y cópiala a expediente/perfil.toml si estás de",
        "#  acuerdo. Si un número no cuadra, casi siempre es una clasificación",
        "#  equivocada en 02-datos/ledger.csv: arréglala ahí y vuelve a correr.",
        "",
    ]
    if incidencias:
        lineas += [
            "#  ═══════════════════════════════════════════════════════════════",
            f"#  ⚠ LA IMPORTACIÓN TUVO {len(incidencias)} PROBLEMA(S). Las cifras",
            "#    de abajo pueden estar INCOMPLETAS, y cuadran entre sí de todos",
            "#    modos: no hay forma de notarlo mirando los números.",
            "#",
        ]
        for inc in incidencias:
            lineas.append(f"#    · {inc}")
        lineas += [
            "#",
            "#    Arréglalo y vuelve a correr `renta importar` antes de copiar",
            "#    nada de aquí al perfil.",
            "#  ═══════════════════════════════════════════════════════════════",
            "",
        ]
    if pendientes:
        lineas += [
            f"#  ⚠ {len(pendientes)} movimiento(s) SIN CLASIFICAR no están sumados",
            "#    en ninguna cifra de abajo. Clasifícalos antes de usar esto.",
            "",
        ]

    for seccion, campos in p.items():
        lineas.append(f"[{seccion}]")
        for campo, valor in campos.items():
            # Formato TOML con guion bajo de miles: 180_000_000
            lineas.append(f"{campo} = {valor:_}")
        lineas.append("")

    lineas += [
        "# ── Consignaciones ───────────────────────────────────────────────",
        "#  NO se sugiere un valor a propósito. El umbral del art. 437 par. 3",
        "#  num. 6 solo cuenta lo PROVENIENTE DE ACTIVIDADES GRAVADAS CON IVA,",
        "#  y hay que descartar el mismo giro contado dos veces.",
        "#",
        f"#  Entradas brutas de todas las fuentes: {cons['entradas_brutas']:,}".replace(",", "."),
    ]
    for fuente, valor in cons["por_fuente"].items():
        lineas.append(f"#    · {fuente}: {valor:,}".replace(",", "."))
    for aviso in cons["avisos"]:
        lineas.append(f"#  {aviso}")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return destino


def comparar_trm_diaria_vs_promedio(ledger: Ledger, trm: TRM) -> dict:
    """Cuánta base gravable mueve usar promedio en vez de TRM diaria.

    El promedio se calcula sobre las fechas DEL LEDGER, no sobre el caché
    entero: el caché puede abarcar varios años y compararlo contra los
    ingresos de uno solo daba una diferencia inventada.

    Sirve para reconciliar cuando el contador usó promedio.
    """
    fechas = {m.fecha for m in ledger.movimientos if m.moneda.upper() != "COP"}
    valores = [trm.serie[f] for f in fechas if f in trm.serie]
    prom = sum(valores) / len(valores) if valores else trm.promedio()
    diaria = sum(
        m.monto_cop for m in ledger.movimientos
        if m.categoria.startswith("ingreso") and m.moneda.upper() != "COP"
    )
    promedio = sum(
        m.monto_origen * prom for m in ledger.movimientos
        if m.categoria.startswith("ingreso") and m.moneda.upper() != "COP"
    )
    minimo, maximo = trm.rango()
    return {
        "con_trm_diaria": round(diaria),
        "con_trm_promedio": round(promedio),
        "diferencia": round(diaria - promedio),
        "trm_promedio": round(prom, 2),
        "trm_minima": minimo,
        "trm_maxima": maximo,
        "oscilacion_pct": round((maximo - minimo) / minimo * 100, 1) if minimo else 0,
        "correcto": "TRM diaria — art. 288 ET",
    }
