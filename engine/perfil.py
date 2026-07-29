"""Carga y validación del perfil del contribuyente.

El perfil vive en <expediente>/perfil.toml, en la máquina del usuario, fuera
de control de versiones. Este módulo NO lo escribe ni lo transmite: solo lo
lee, valida que los números tengan sentido y reporta qué falta.

Todo campo ausente vale 0 y queda registrado como supuesto, para que la
salida distinga siempre entre "es cero" y "no lo sabemos todavía".
"""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Estructura esperada: sección -> {campo: valor por defecto}
ESQUEMA: dict[str, dict] = {
    "contribuyente": {
        "anio_gravable": 2025,
        "residente_fiscal": True,
        # None a propósito: no hay defecto honesto. Suponer "no comerciante"
        # es lo que hacía OBL-02 antes, afirmando sobre un hecho que nunca
        # vio. Sin el dato, el chequeo dice que no puede concluir.
        "es_comerciante": None,
    },
    "ingresos": {
        "rentas_trabajo_honorarios": 0,
        "rentas_capital": 0,
        "otras_rentas_no_laborales": 0,
        # Los tres de abajo NO los liquida este motor. Existen para que el
        # usuario los pueda declarar y el motor lo detecte y se detenga, en
        # vez de meterlos en la cédula equivocada y dar un número creíble y
        # equivocado. Ver validar().
        "rentas_laborales_salario": 0,
        "rentas_pension": 0,
        "ganancia_ocasional": 0,
    },
    "incrngo": {
        "aportes_obligatorios_salud_pension": 0,
        "componente_inflacionario": 0,
        "otros": 0,
    },
    "costos": {
        "pagos_a_contratistas": 0,
        "comisiones_plataforma": 0,
        "equipo_tecnologico": 0,
        "internet_software": 0,
        "arriendo_oficina": 0,
        "otros": 0,
    },
    "deducciones": {
        "gmf_pagado": 0,
        "intereses_vivienda": 0,
        "medicina_prepagada": 0,
        "aportes_voluntarios": 0,
        "compras_con_factura_electronica": 0,
        "dependientes": 0,
    },
    "descuentos": {
        "donaciones_certificadas_rte": 0,
    },
    "anticipos": {
        "retenciones_practicadas": 0,
        "saldo_a_favor_anio_anterior": 0,
    },
    "verificaciones": {
        "consignaciones_totales_anio": 0,
        "contratistas_con_pila_verificada": False,
        "tiene_documento_soporte_de_pagos": False,
    },
}

# Los tres tipos de renta de la cédula general. El orden es el del art. 335
# y siguientes, y es el que usa la atribución de costos del Decreto 1625
# art. 1.2.1.20.5.
TIPOS_DE_RENTA = (
    "rentas_trabajo_honorarios", "rentas_capital", "otras_rentas_no_laborales",
)

# Los dos tipos que produce una ACTIVIDAD. La renta de capital —rendimientos,
# arrendamientos, regalías— no lo es, y por eso no compite por los costos de
# operación cuando hay actividad de por medio. Ver
# `Perfil.tipo_por_defecto_de_costos`.
TIPOS_DE_ACTIVIDAD = ("rentas_trabajo_honorarios", "otras_rentas_no_laborales")

# A qué tipo de renta resta cada INCRNGO. `None` = no tiene tipo evidente.
ATRIBUCION_INCRNGO = {
    "aportes_obligatorios_salud_pension": "rentas_trabajo_honorarios",
    "componente_inflacionario": "rentas_capital",
    "otros": None,
}

# Campos cuya ausencia cambia materialmente el resultado.
CRITICOS = [
    ("ingresos.rentas_trabajo_honorarios", "No hay ingresos por honorarios cargados."),
    (
        "deducciones.dependientes",
        "Dependientes en 0. Verifica padres, hermanos, cónyuge e hijos: "
        "cada uno vale 72 UVT FUERA del tope del 40%.",
    ),
    (
        "incrngo.aportes_obligatorios_salud_pension",
        "Aportes obligatorios de salud y pensión en 0. Si cotizaste, son "
        "INCRNGO y restan antes del tope del 40%. Busca las planillas PILA.",
    ),
    (
        "deducciones.gmf_pagado",
        "GMF en 0. Pide el certificado de 4x1000 a CADA banco: el 50% es deducible.",
    ),
    (
        "verificaciones.consignaciones_totales_anio",
        "Consignaciones totales sin cuantificar. Es el insumo del riesgo R-01 "
        "(pérdida de la calidad de no responsable de IVA).",
    ),
]


@dataclass
class Perfil:
    datos: dict
    ruta: Path | None = None
    supuestos: list[str] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)

    # ---- acceso ------------------------------------------------------

    def get(self, ruta: str, defecto=0):
        nodo = self.datos
        for parte in ruta.split("."):
            if not isinstance(nodo, dict) or parte not in nodo:
                return defecto
            nodo = nodo[parte]
        return nodo

    def set(self, ruta: str, valor):
        partes = ruta.split(".")
        nodo = self.datos
        for parte in partes[:-1]:
            nodo = nodo.setdefault(parte, {})
        nodo[partes[-1]] = valor

    def copia_con(self, **cambios) -> "Perfil":
        """Copia con campos cambiados. Para la tabla de sensibilidad."""
        nuevo = Perfil(copy.deepcopy(self.datos), self.ruta, list(self.supuestos))
        for ruta, valor in cambios.items():
            nuevo.set(ruta.replace("__", "."), valor)
        return nuevo

    @property
    def anio_gravable(self) -> int:
        return int(self.get("contribuyente.anio_gravable", 2025))

    # ---- agregados ---------------------------------------------------

    # Solo los que entran a la cédula general. Salario, pensión y ganancia
    # ocasional se excluyen a propósito: si aparecen, validar() detiene el
    # cálculo en vez de sumarlos a una base que no les corresponde.
    INGRESOS_CEDULA_GENERAL = (
        "rentas_trabajo_honorarios", "rentas_capital", "otras_rentas_no_laborales",
    )

    @property
    def ingresos_brutos(self) -> float:
        return sum(self.get(f"ingresos.{k}") for k in self.INGRESOS_CEDULA_GENERAL)

    @property
    def total_incrngo(self) -> float:
        return sum(self.get(f"incrngo.{k}") for k in ESQUEMA["incrngo"])

    @property
    def total_costos(self) -> float:
        return sum(self.get(f"costos.{k}") for k in ESQUEMA["costos"])

    # ---- atribución por tipo de renta --------------------------------
    #
    # El Decreto 1625 art. 1.2.1.20.5 inciso final (adicionado por el
    # Decreto 2231 de 2023) no topa los costos contra la cédula: los topa
    # POR CADA TIPO DE RENTA contra los ingresos menos los INCRNGO de ESE
    # tipo. Para poder aplicarlo hay que saber a qué tipo pertenece cada
    # peso, y el perfil no lo preguntaba.

    def incrngo_por_tipo(self) -> dict[str, float]:
        """Reparte los INCRNGO entre los tipos de renta.

        Los aportes obligatorios los hace quien percibe honorarios: van a
        rentas de trabajo. El componente inflacionario es de rendimientos
        financieros (arts. 38 a 40 ET): va a rentas de capital. `otros` no
        tiene tipo evidente, así que se atribuye al tipo con ingresos si
        hay uno solo, y si no, queda sin atribuir — el mismo criterio que
        los costos.
        """
        por_tipo = {t: 0.0 for t in TIPOS_DE_RENTA}
        sin_atribuir = 0.0
        for campo, tipo in ATRIBUCION_INCRNGO.items():
            valor = self.get(f"incrngo.{campo}")
            if not valor:
                continue
            if tipo is None:
                sin_atribuir += valor
            else:
                por_tipo[tipo] += valor
        unico = self.tipo_unico_con_ingresos()
        if sin_atribuir:
            # Sin tipo único no se reparte: se deja fuera del techo, que es
            # el lado seguro (un INCRNGO mal atribuido SUBE el techo de otro
            # tipo y deja pasar costos que la norma rechaza).
            if unico:
                por_tipo[unico] += sin_atribuir
        return por_tipo

    def tipo_unico_con_ingresos(self) -> str | None:
        """El único tipo de renta con ingresos, si es que hay uno solo."""
        con_ingresos = [t for t in TIPOS_DE_RENTA if self.get(f"ingresos.{t}") > 0]
        return con_ingresos[0] if len(con_ingresos) == 1 else None

    def tipo_por_defecto_de_costos(self) -> str | None:
        """A qué tipo de renta pertenecen los costos cuando nadie lo dijo.

        Los seis campos de `[costos]` —contratistas, comisión de plataforma,
        equipo, internet, arriendo de oficina y otros— son costos de una
        ACTIVIDAD. Una actividad produce rentas de trabajo por honorarios o
        rentas no laborales; no produce rentas de capital, que son
        rendimientos, arrendamientos y regalías. Por eso la renta de capital
        no compite por estos costos cuando hay una actividad de por medio.

        Si el contribuyente tiene ingresos de UNA sola actividad, ahí van.
        Si tiene de las dos y no declaró `[costos.atribucion]`, no se
        adivina: devuelve None y el techo no se aplica sobre esa parte, con
        el chequeo R-11 diciéndolo. Y si no tiene actividad ninguna, se cae
        al único tipo con ingresos que haya.
        """
        actividad = [t for t in TIPOS_DE_ACTIVIDAD if self.get(f"ingresos.{t}") > 0]
        if len(actividad) == 1:
            return actividad[0]
        if actividad:
            return None
        return self.tipo_unico_con_ingresos()

    def costos_por_tipo(self) -> tuple[dict[str, float], float]:
        """Reparte los costos entre los tipos de renta.

        Devuelve (por_tipo, sin_atribuir). Tres fuentes, en este orden:

        1. `[costos.atribucion]` del perfil, si el usuario la escribió.
        2. Si no, `tipo_por_defecto_de_costos()`: la única actividad con
           ingresos que tenga el contribuyente.
        3. Si tiene las dos actividades y no declaró la atribución, el costo
           queda SIN ATRIBUIR. No se adivina y no se prorratea: el motor no
           aplica el techo sobre esa parte y lo dice.

        El orden importa. Adivinar hacia el lado equivocado sube el impuesto
        de alguien que no lo debe, y eso es tan grave como bajarlo.
        """
        declarada = self.datos.get("costos", {}).get("atribucion", {})
        if not isinstance(declarada, dict):
            declarada = {}
        unico = self.tipo_por_defecto_de_costos()

        por_tipo = {t: 0.0 for t in TIPOS_DE_RENTA}
        sin_atribuir = 0.0
        for campo in ESQUEMA["costos"]:
            valor = self.get(f"costos.{campo}")
            if not valor:
                continue
            tipo = declarada.get(campo) or unico
            if tipo in por_tipo:
                por_tipo[tipo] += valor
            else:
                sin_atribuir += valor
        return por_tipo, sin_atribuir

    def _suma_patrimonio(self, grupo: str) -> float:
        """Suma un grupo del patrimonio ignorando lo que no sea un número.

        Tolerante a propósito: `cargar()` llama a `revisar_faltantes()`, que
        lee estas dos propiedades, ANTES de que nadie haya podido validar
        nada. Con un `valor = "350.000.000"` —el punto de miles, otra vez, y
        en el campo donde es más probable— esto reventaba con un TypeError
        crudo y sin mensaje. Lo que no es número se ignora acá y `validar()`
        lo reporta con el mensaje que explica cómo se escriben los miles en
        TOML.
        """
        partidas = self.datos.get("patrimonio", {}).get(grupo, [])
        if not isinstance(partidas, list):
            return 0.0
        return sum(
            p["valor"] for p in partidas
            if isinstance(p, dict) and isinstance(p.get("valor"), (int, float))
            and not isinstance(p["valor"], bool)
        )

    @property
    def patrimonio_bruto(self) -> float:
        return self._suma_patrimonio("activos")

    @property
    def pasivos(self) -> float:
        return self._suma_patrimonio("pasivos")


def _completar(datos: dict) -> tuple[dict, list[str]]:
    """Rellena con defectos y devuelve la lista de supuestos aplicados."""
    supuestos = []
    resultado = copy.deepcopy(datos)
    for seccion, campos in ESQUEMA.items():
        resultado.setdefault(seccion, {})
        for campo, defecto in campos.items():
            if campo not in resultado[seccion]:
                resultado[seccion][campo] = defecto
                # Todos los defectos se registran, no solo los que valen 0 o
                # False. Los dos que no lo son —anio_gravable y
                # residente_fiscal— son justamente los que deciden si el
                # motor aplica: un perfil sin bloque [contribuyente] producía
                # una liquidación completa de residente sin una sola
                # advertencia.
                marca = " ← DECIDE SI ESTE MOTOR APLICA" if seccion == "contribuyente" else ""
                supuestos.append(f"{seccion}.{campo} = {defecto} (no informado){marca}")
    resultado.setdefault("patrimonio", {})
    resultado["patrimonio"].setdefault("activos", [])
    resultado["patrimonio"].setdefault("pasivos", [])
    return resultado, supuestos


# Campos numéricos que NO son pesos, y por lo tanto sí pueden no ser enteros
# o quedar fuera de la banda de plausibilidad de un monto.
NO_SON_PESOS = {"contribuyente.anio_gravable", "deducciones.dependientes"}

MENSAJE_MILES = (
    "En TOML los miles se escriben con guion bajo, como 180_000_000, o sin "
    "separador. Nunca con puntos."
)


def _errores_de_monto(ruta: str, valor) -> list[str]:
    """Valida un campo en pesos: tipo, signo y forma.

    La validación de FORMA existe por el error de tipeo más caro del archivo,
    y el más natural para alguien que escribe pesos en Colombia:

        rentas_trabajo_honorarios = 180.000     # quiso decir 180 millones

    En TOML eso no es un error de sintaxis: es el float 180.0. Pasaba la
    validación con un ✓, el motor liquidaba sobre ciento ochenta pesos y
    devolvía "saldo $0" — la respuesta más cara que puede dar esta
    herramienta, entregada con el sello de validada puesto. El caso de dos
    grupos (180.000.000) sí reventaba, con un mensaje excelente que nunca se
    alcanzaba con un solo grupo.

    La señal es limpia: **un monto en pesos es un entero**. Nadie declara
    centavos ante la DIAN, y el art. 577 ET manda aproximar al múltiplo de
    mil más cercano. Un `float` en un campo de pesos es, casi siempre, un
    punto de miles que TOML se comió. Es la misma idea que la banda
    TRM_MINIMA/TRM_MAXIMA de trm.py: rechazar lo que no puede ser un dato.
    """
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        return [f"{ruta} debe ser un número, no {valor!r}. {MENSAJE_MILES}"]
    if valor < 0:
        return [f"{ruta} no puede ser negativo ({valor})"]
    if isinstance(valor, float) and not valor.is_integer():
        return [
            f"{ruta} = {valor} tiene decimales, y un monto en pesos es un "
            f"entero. {MENSAJE_MILES}"
        ]
    if isinstance(valor, float):
        # Entero pero escrito como float: `180.000` es float 180.0 y `180000`
        # es int. La diferencia de tipo es justo la huella del punto de miles.
        return [
            f"{ruta} = {valor:g} está escrito con punto decimal, así que TOML "
            f"lo leyó como {valor:g} y no como los {int(valor)}.000 que "
            f"probablemente querías decir. {MENSAJE_MILES}"
        ]
    return []


def validar(perfil: Perfil, anios_disponibles: list[int] | None = None) -> list[str]:
    """Errores que impiden calcular. Distinto de 'faltantes', que solo avisan."""
    errores = []

    # --- 1. tipos. Va PRIMERO y corta: el resto de las validaciones hace
    #        aritmética, y un str en un campo numérico las revienta con un
    #        traceback justo cuando el usuario descuidado más necesita leer
    #        los mensajes que ya se habían recolectado.
    for seccion, campos in ESQUEMA.items():
        for campo, defecto in campos.items():
            if isinstance(defecto, bool) or not isinstance(defecto, (int, float)):
                continue
            ruta = f"{seccion}.{campo}"
            valor = perfil.get(ruta)
            if ruta in NO_SON_PESOS:
                if not isinstance(valor, (int, float)) or isinstance(valor, bool):
                    errores.append(
                        f"{ruta} debe ser un número, no {valor!r}. {MENSAJE_MILES}"
                    )
                elif valor < 0:
                    errores.append(f"{ruta} no puede ser negativo ({valor})")
                continue
            errores += _errores_de_monto(ruta, valor)

    # Patrimonio: la única sección con montos que NO está en ESQUEMA, porque
    # es una lista de longitud libre. Quedaba sin validar por completo, y
    # `cargar()` toca `patrimonio_bruto` antes de que nadie valide nada: un
    # `valor = "350.000.000"` reventaba con un TypeError crudo, sin mensaje,
    # en el campo donde el punto de miles es más probable. Y un activo
    # negativo pasaba en silencio — es la casilla que el art. 648 num. 1
    # sanciona al 200% por activos omitidos.
    for grupo in ("activos", "pasivos"):
        partidas = perfil.datos.get("patrimonio", {}).get(grupo, [])
        if not isinstance(partidas, list):
            errores.append(f"patrimonio.{grupo} debe ser una lista de partidas.")
            continue
        for i, partida in enumerate(partidas, start=1):
            if not isinstance(partida, dict):
                errores.append(
                    f"patrimonio.{grupo}[{i}] debe ser un bloque "
                    f"[[patrimonio.{grupo}]] con nombre y valor."
                )
                continue
            errores += _errores_de_monto(
                f"patrimonio.{grupo}[{i}].valor ({partida.get('nombre', 'sin nombre')})",
                partida.get("valor", 0),
            )

    if errores:
        return errores

    # --- 2. alcance del motor ------------------------------------------
    if not perfil.get("contribuyente.residente_fiscal", True):
        errores.append(
            "FUERA DE ALCANCE: el perfil dice que NO eres residente fiscal. Un "
            "no residente tributa por otras reglas (art. 247 ET, tarifa única "
            "sobre renta de fuente nacional) que este motor no implementa. "
            "Consulta con un contador público."
        )

    if perfil.get("ingresos.rentas_pension"):
        errores.append(
            "FUERA DE ALCANCE: hay renta de pensión. Las pensiones son exentas "
            "hasta 1.000 UVT mensuales (art. 206 num. 5 ET) y van por una regla "
            "distinta a la del 25% de rentas de trabajo. Este motor las "
            "liquidaría de más. Consulta con un contador público."
        )

    if perfil.get("ingresos.ganancia_ocasional"):
        errores.append(
            "FUERA DE ALCANCE: hay ganancia ocasional. Tributa en cédula aparte "
            "al 15% (art. 314 ET), no en la tabla del art. 241. Meterla como "
            "renta ordinaria sobreestima el impuesto en decenas de millones. "
            "Este motor todavía no la calcula: sepárala y llévala al contador."
        )

    if perfil.get("ingresos.rentas_laborales_salario"):
        errores.append(
            "FUERA DE ALCANCE: hay salario de una relación laboral. La opción "
            "entre costos y renta exenta del art. 336 num. 4 solo ata a quien "
            "percibe honorarios o compensación por servicios personales; un "
            "asalariado no detrae costos. Este motor está hecho para el perfil "
            "de independiente."
        )

    # --- 3. coherencia --------------------------------------------------
    dep = perfil.get("deducciones.dependientes")
    if dep != int(dep):
        errores.append(
            f"deducciones.dependientes = {dep} debe ser un número entero."
        )
    elif dep > 5:
        # Cinco, no cuatro. El art. 336 num. 3 inciso 2 topa en 4 la
        # deducción de 72 UVT, y el Decreto 1625 art. 1.2.1.20.3 prohíbe que
        # UN MISMO dependiente dé lugar a las dos deducciones — no que el
        # contribuyente tome una sola. Así que el quinto dependiente todavía
        # sirve: cuatro por 72 UVT y uno por el 10% del art. 387. Cortar en 4
        # le quitaba 72 UVT a quien tiene cinco.
        errores.append(
            f"deducciones.dependientes = {dep}. Más de 5 no cambia el "
            f"cálculo: el art. 336 num. 3 inciso 2 ET topa en 4 la deducción "
            f"de 72 UVT, y el 10% del art. 387 consume un dependiente más. "
            f"Pon máximo 5."
        )

    # `[costos.atribucion]` decide contra qué techo se compara cada costo
    # (Decreto 1625 art. 1.2.1.20.5). Una clave mal escrita ahí no rompe
    # nada visible: el costo simplemente deja de tener tipo y el techo no se
    # le aplica. Es una defensa que se apaga sola en silencio, así que se
    # valida.
    atribucion = perfil.datos.get("costos", {}).get("atribucion", {})
    if not isinstance(atribucion, dict):
        errores.append(
            "costos.atribucion debe ser un bloque [costos.atribucion] que "
            "asocie cada campo de costos a un tipo de renta."
        )
    else:
        for campo, tipo in atribucion.items():
            if campo not in ESQUEMA["costos"]:
                errores.append(
                    f"costos.atribucion.{campo} no es un campo de [costos]. "
                    f"Los que hay: {', '.join(sorted(ESQUEMA['costos']))}."
                )
            elif tipo not in TIPOS_DE_RENTA:
                errores.append(
                    f"costos.atribucion.{campo} = {tipo!r} no es un tipo de "
                    f"renta. Usa uno de: {', '.join(TIPOS_DE_RENTA)}."
                )

    anio = perfil.anio_gravable
    if anios_disponibles is not None and anio not in anios_disponibles:
        errores.append(
            f"No hay parámetros para el año gravable {anio}. Disponibles: "
            f"{', '.join(str(a) for a in anios_disponibles)}. Agrega "
            f"knowledge/ag{anio}/parametros.toml verificando cada cifra contra "
            f"la norma vigente."
        )

    if perfil.ingresos_brutos == 0 and perfil.patrimonio_bruto == 0:
        errores.append(
            "No hay ni ingresos ni patrimonio. Carga los datos antes de calcular."
        )

    return errores


def revisar_faltantes(perfil: Perfil) -> list[str]:
    """Campos en cero que probablemente deberían tener valor."""
    avisos = []
    for ruta, mensaje in CRITICOS:
        if not perfil.get(ruta):
            avisos.append(mensaje)
    if not perfil.patrimonio_bruto:
        avisos.append(
            "Patrimonio bruto en 0. Es obligatorio declararlo y los activos "
            "omitidos que la DIAN detecte se gravan como renta líquida (art. 239-1 ET)."
        )
    return avisos


def cargar(ruta: Path | str) -> Perfil:
    ruta = Path(ruta)
    if ruta.is_dir():
        ruta = ruta / "perfil.toml"
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta}. Corre /renta-co:setup, o copia "
            f"templates/perfil.ejemplo.toml y llénalo."
        )
    try:
        with open(ruta, "rb") as f:
            crudo = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(
            f"{ruta} no es TOML válido: {e}\n"
            f"El error más frecuente es escribir los montos con puntos de "
            f"miles, como se escriben en Colombia. En TOML eso no es un "
            f"número: usa guion bajo (180_000_000) o nada. El otro error "
            f"común es dejar un [encabezado sin cerrar."
        ) from e

    datos, supuestos = _completar(crudo)
    perfil = Perfil(datos, ruta, supuestos)
    perfil.faltantes = revisar_faltantes(perfil)
    return perfil
