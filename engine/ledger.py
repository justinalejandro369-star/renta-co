"""Construcción del ledger: movimientos crudos → pesos con TRM diaria.

Un ledger es la lista de todos los movimientos del año gravable, cada uno
convertido a COP con la TRM de SU fecha, y clasificado en una categoría
tributaria. Es el insumo de la depuración y la prueba de dónde salió cada
cifra si la DIAN pregunta.

Categorías:
    ingreso_trabajo     honorarios, compensación por servicios
    ingreso_capital     rendimientos, dividendos, intereses
    costo               pago a contratista, comisión, insumo deducible
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
    "costo": "Costo o gasto deducible (solo Ruta A)",
    "gasto_personal": "Gasto personal — NO deducible",
    "traslado": "Traslado entre cuentas propias — ni ingreso ni gasto",
    "retencion": "Retención en la fuente practicada",
    "desconocido": "Sin clasificar",
}

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

    def filtrar_anio(self, anio: int) -> "Ledger":
        return Ledger(
            [m for m in self.movimientos if m.fecha.year == anio], list(self.avisos)
        )

    def avisos_de_signo(self) -> list[str]:
        """Categorías donde entradas y salidas se mezclan.

        Un reembolso dentro de los costos, o una retención reversada, netean
        con el resto. Es lo correcto, pero hay que decirlo: la cifra que sale
        no es la suma de los comprobantes, y el contador va a preguntar.
        """
        avisos = []
        for categoria, etiqueta in (("costo", "costos"),
                                    ("retencion", "retenciones")):
            entradas = [m for m in self.movimientos
                        if m.categoria == categoria and m.monto_cop > 0]
            if entradas:
                total = sum(m.monto_cop for m in entradas)
                avisos.append(
                    f"{len(entradas)} movimiento(s) de {etiqueta} vienen en "
                    f"POSITIVO por {total:,.0f} COP: se tratan como devoluciones "
                    f"y netean contra el total. Si en realidad están mal "
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


def leer_clasificacion_previa(ruta: Path) -> dict[tuple, str]:
    """Categorías que el usuario ya corrigió a mano en un ledger anterior.

    La herramienta le dice «arréglala ahí y vuelve a correr», y hasta ahora
    `importar` sobreescribía el archivo y tiraba esa corrección a la basura
    sin avisar. Era el único remedio que ofrecía para una clasificación
    equivocada, y no funcionaba.

    La llave es lo que identifica el movimiento con independencia de cómo se
    haya clasificado: fecha, monto de origen, moneda y archivo de origen.
    """
    if not ruta.exists():
        return {}
    previas: dict[tuple, str] = {}
    try:
        with open(ruta, newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                try:
                    clave = (
                        fila["fecha"],
                        f'{float(fila["monto_origen"]):.2f}',
                        fila["moneda"],
                        fila["fuente"],
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                if fila.get("categoria"):
                    previas[clave] = fila["categoria"]
    except OSError:
        return {}
    return previas


def aplicar_clasificacion_previa(ledger: Ledger, previas: dict[tuple, str]) -> int:
    """Reaplica las categorías corregidas a mano. Devuelve cuántas."""
    if not previas:
        return 0
    aplicadas = 0
    for m in ledger.movimientos:
        clave = (m.fecha.isoformat(), f"{m.monto_origen:.2f}", m.moneda, m.fuente)
        anterior = previas.get(clave)
        if anterior and anterior in CATEGORIAS and anterior != m.categoria:
            m.categoria = anterior
            aplicadas += 1
    return aplicadas


def escribir_sugerencia_perfil(ledger: Ledger, destino: Path) -> Path:
    """Escribe las cifras del ledger en formato perfil.toml, para copiar.

    NO sobrescribe el perfil del usuario. Ese paso —revisar cada cifra y
    decidir si entra— es del usuario, y es donde se atrapan las
    clasificaciones equivocadas. Antes este puente no existía: el mapeo del
    ledger al perfil quedaba a cargo del modelo, transcribiendo a mano, que
    es exactamente lo que el proyecto dice no hacer.
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
