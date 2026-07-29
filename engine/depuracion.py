"""Motor de depuración de la cédula general — persona natural residente.

Compara las dos rutas EXCLUYENTES del art. 336 num. 4 ET:

    RUTA A → restar costos y gastos procedentes
    RUTA B → restar la renta exenta del 25% (art. 206 num. 10 + par. 5)

y produce una tabla de sensibilidad que dice, en pesos, cuánto ahorra cada
palanca disponible. Determinista y sin dependencias externas: el mismo
perfil produce siempre el mismo resultado, y se puede recalcular a mano.

    from engine import perfil, parametros, depuracion
    p = perfil.cargar("./expediente")
    par = parametros.cargar(p.anio_gravable)
    resultado = depuracion.comparar(p, par)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .parametros import Parametros
from .perfil import TIPOS_DE_RENTA, Perfil

# Etiquetas legibles de los tres tipos de renta de la cédula general.
NOMBRE_TIPO = {
    "rentas_trabajo_honorarios": "rentas de trabajo",
    "rentas_capital": "rentas de capital",
    "otras_rentas_no_laborales": "otras rentas no laborales",
}

RUTAS = {
    "A": "Costos y gastos (art. 336 num. 4)",
    "B": "Renta exenta 25% (art. 206 num. 10)",
}


# ---------------------------------------------------------------------
# Tarifa
# ---------------------------------------------------------------------

def impuesto_241(base_cop: float, par: Parametros) -> float:
    """Impuesto del art. 241 sobre una base en pesos."""
    if base_cop <= 0:
        return 0.0
    base_uvt = base_cop / par.uvt
    for rango in par.exigir("tarifa.rangos"):
        hasta = rango["hasta_uvt"]
        if hasta == 0 or base_uvt <= hasta:
            uvt = (base_uvt - rango["desde_uvt"]) * rango["tarifa"] + rango["adicional_uvt"]
            return round(max(uvt, 0) * par.uvt)
    return 0.0


def tarifa_marginal(base_cop: float, par: Parametros) -> float:
    """Tarifa que paga el PRÓXIMO peso de base.

    El corte va con `<` y no con `<=`, al revés que `impuesto_241`. No es un
    descuido simétrico: son dos preguntas distintas.

      · `impuesto_241` pregunta en qué tramo cae ESTA base. Una base de
        exactamente 1.090 UVT está dentro del tramo del 0%, así que `<=`.
      · `tarifa_marginal` pregunta qué le cuesta el peso SIGUIENTE. Parado
        exactamente en 1.090 UVT, el siguiente peso ya paga 19%.

    Con `<=` devolvía la tarifa del tramo ANTERIOR justo en la frontera, y
    esta cifra sale impresa como insumo de planeación: quien está en el
    borde leía 0% y decidía con eso.
    """
    base_uvt = base_cop / par.uvt if par.uvt else 0
    for rango in par.exigir("tarifa.rangos"):
        hasta = rango["hasta_uvt"]
        if hasta == 0 or base_uvt < hasta:
            return rango["tarifa"]
    return 0.0


def aproximar_577(valor: float) -> int:
    """Al múltiplo de mil más cercano, como manda el art. 577 ET.

    «Los valores diligenciados en los formularios de las declaraciones
    tributarias deberán aproximarse al múltiplo de mil (1.000) más cercano.»

    El motor calcula al peso, que es lo correcto para comparar rutas y para
    auditar la cuenta. Pero lo que el usuario TRANSCRIBE al formulario 210 va
    aproximado, y la diferencia entre lo que el motor imprimía y lo que él
    escribía en la casilla la estaba resolviendo él de cabeza — contra la
    regla del proyecto de que la aritmética la hace el motor.

    Se usa `round`, que en Python redondea al par en el empate exacto (500).
    Da igual: el art. 577 no dice qué hacer con el empate y la DIAN acepta
    cualquiera de los dos, con una diferencia máxima de mil pesos.
    """
    return int(round(valor / 1000) * 1000)


def zonas_de_castigo_241(par: Parametros) -> list[tuple[float, float, float]]:
    """Tramos donde ganar un peso más de base BAJA el impuesto.

    La tabla del art. 241 no es continua: en cada frontera, el `adicional_uvt`
    del tramo siguiente viene redondeado a UVT enteras y no coincide con lo
    que acumuló el tramo anterior. En 8.670 UVT un peso más de base son
    $4.980 MENOS de impuesto.

    Esto es FIEL A LA NORMA —sale del propio texto de la tabla— y no hay nada
    que arreglar en el motor. Pero nada en la salida se lo advertía a quien
    queda parado justo ahí, que es exactamente a quien le sirve saberlo: le
    conviene renunciar a una deducción.

    Devuelve (desde_cop, hasta_cop, ahorro) por cada zona: quien tenga la
    renta líquida dentro de ese rango paga MÁS que si tuviera `hasta_cop + 1`.
    """
    zonas = []
    for rango in par.exigir("tarifa.rangos"):
        hasta = rango["hasta_uvt"]
        if not hasta:
            continue
        frontera = hasta * par.uvt
        arriba = impuesto_241(frontera + 1, par)
        if impuesto_241(frontera, par) <= arriba:
            continue
        # El punto donde el impuesto de este tramo alcanza al del siguiente.
        # Bisección en vez de despejar: no depende de la forma de la fórmula,
        # así que sigue valiendo si la tabla cambia de estructura.
        bajo, alto = rango["desde_uvt"] * par.uvt, frontera
        for _ in range(60):
            medio = (bajo + alto) / 2
            if impuesto_241(medio, par) > arriba:
                alto = medio
            else:
                bajo = medio
        zonas.append((alto, frontera, impuesto_241(frontera, par) - arriba))
    return zonas


def aviso_de_discontinuidad(base_cop: float, par: Parametros) -> str:
    """Aviso para quien cae dentro de una zona de castigo. Vacío si no."""
    for desde, hasta, ahorro in zonas_de_castigo_241(par):
        if desde <= base_cop <= hasta:
            return (
                f"Tu renta líquida gravable ({_cop(base_cop)}) cae en el "
                f"escalón del art. 241 que termina en {_cop(hasta)}. Con "
                f"{_cop(hasta + 1)} de base pagarías {_cop(ahorro)} MENOS de "
                f"impuesto, porque la tabla salta hacia abajo en esa "
                f"frontera. No es un error del cálculo: sale del redondeo a "
                f"UVT enteras del propio texto de la norma. Si estás sobre "
                f"ese borde, renunciar a una deducción pequeña te puede "
                f"salir más barato — revísalo con tu contador antes de "
                f"hacerlo, porque una deducción no solicitada no se recupera."
            )
    return ""


# ---------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------

@dataclass
class Renglon:
    concepto: str
    valor: float
    signo: int = 0        # -1 resta, +1 suma, 0 subtotal
    nota: str = ""
    fuente: str = ""      # normalmente una `Cita`: str con `.url`

    @property
    def url(self) -> str:
        """URL de la norma, vacía si la cita no vino de knowledge/."""
        return getattr(self.fuente, "url", "")


@dataclass
class Liquidacion:
    ruta: str
    renglones: list[Renglon] = field(default_factory=list)
    renta_liquida: float = 0
    impuesto: float = 0
    impuesto_neto: float = 0
    saldo: float = 0            # >0 a pagar, <0 a favor
    tope_conjunto: float = 0
    rechazado_por_tope: float = 0
    dependientes_via: str = ""
    costos_solicitados: float = 0
    costos_rechazados_por_tipo: float = 0
    costos_sin_atribuir: float = 0
    detalle_tope_costos: list = field(default_factory=list)

    def _r(self, concepto, valor, signo=0, nota="", fuente=""):
        self.renglones.append(Renglon(concepto, round(valor), signo, nota, fuente))
        return valor


# ---------------------------------------------------------------------
# Depuración de una ruta
# ---------------------------------------------------------------------

class Cita(str):
    """El texto de una cita normativa, con su URL y su estado de verificación.

    Es una SUBCLASE DE `str` a propósito. Los ~40 sitios que ya la imprimen,
    la comparan y la escriben al CSV siguen funcionando sin tocarlos; lo que
    gana es `.url`, que es lo único que le permite al contador ir a leer la
    norma en vez de creerle al renglón.

    Por qué hacía falta: `_fuente()` devolvía una cadena, así que la URL
    verificada de `knowledge/` —la que `scripts/verificar_citas.py` comprueba
    contra la fuente primaria cada semana— moría dentro del TOML y nunca
    llegaba ni a `escenarios.csv` ni al memo. El contador veía «ET art. 336
    num. 3» y tenía que buscarlo él.

    Y tenía una consecuencia de verificación: la mutación M55 —reemplazar
    `par.fuente(ruta)` por el literal de respaldo— ESCAPABA a todas las
    capas, porque después de la ronda 5 el literal y la cita de knowledge
    dicen exactamente lo mismo. Ninguna comparación de cadenas las distingue.
    La URL sí: el literal de Python no tiene ninguna.
    """

    url: str
    verificada: bool

    def __new__(cls, texto: str, url: str = "", verificada: bool = False):
        obj = super().__new__(cls, texto)
        obj.url = url or ""
        obj.verificada = bool(verificada)
        return obj


def _fuente(par: Parametros, ruta_valor: str, respaldo: str) -> Cita:
    """Cita normativa de un renglón, tomada de knowledge/.

    La cifra sale de `knowledge/<año>/parametros.toml` y la cita salía de un
    literal en Python, así que las dos podían divergir — y divergían. Tres
    ejemplos que encontró la ronda 5, todos con la cita del motor y la del
    knowledge apuntando a normas distintas para el MISMO número:

        medicina prepagada    motor: art. 387 num. 1
                          knowledge: art. 387 inciso 2 lit. a) y b)
        dependientes 72 UVT   motor: art. 336 par.
                          knowledge: art. 336 num. 3 inciso 2
        1% factura elect.     motor: art. 336 par. 4
                          knowledge: art. 336 numeral 5

    La que ve el contador en el CSV es la del motor, así que la del knowledge
    —que es la verificada, la que tiene URL y la que revisa el test de
    fuentes— no servía de nada. Ahora la cita viene del mismo sitio que la
    cifra, y el literal queda solo como respaldo para cuando un año gravable
    todavía no declare esa fuente.
    """
    citada = par.fuente(ruta_valor)
    if citada == "sin fuente citada":
        # El respaldo es un literal de Python: no tiene URL ni verificación,
        # y que se note es el punto. Un renglón sin URL es un renglón cuya
        # cita nadie puede comprobar de un clic.
        return Cita(respaldo)
    bloque = ".".join(ruta_valor.split(".")[:-1])
    return Cita(citada,
                par.get(f"{bloque}.url", ""),
                bool(par.get(f"{bloque}.url_verificada", False)))


def _costos_aceptados(p: Perfil, ruta: str) -> tuple[float, float, float, list]:
    """Costos que la Ruta A puede restar, después del techo por tipo de renta.

    El Decreto 1625 art. 1.2.1.20.5 inciso final (sustituido por el Decreto
    2231 de 2023) dice que los costos y gastos «en ningún caso podrán superar
    el valor de los ingresos» de SU tipo de renta, menos los INCRNGO de ese
    mismo tipo. El motor los restaba del total de la cédula, así que una
    pérdida en honorarios se comía las rentas de capital y bajaba el impuesto
    de alguien que sí lo debe. Con honorarios de $10.000.000, rentas de
    capital de $300.000.000 y costos de $200.000.000, la renta líquida daba
    $110.000.000 en vez de $300.000.000.

    Devuelve (aceptados, rechazados, sin_atribuir, detalle).

    Lo que queda SIN ATRIBUIR no se topa. Es deliberado: adivinar el tipo
    equivocado le sube el impuesto a alguien que no lo debe, y eso es tan
    grave como bajárselo. El chequeo R-11 lo dice en voz alta; el R-10
    reporta lo que sí se rechazó.
    """
    if ruta != "A" or not p.total_costos:
        return 0.0, 0.0, 0.0, []

    por_tipo, sin_atribuir = p.costos_por_tipo()
    incrngo_tipo = p.incrngo_por_tipo()

    aceptados = sin_atribuir
    rechazados = 0.0
    detalle = []
    for tipo in TIPOS_DE_RENTA:
        pedido = por_tipo.get(tipo, 0.0)
        if not pedido:
            continue
        techo = max(p.get(f"ingresos.{tipo}") - incrngo_tipo.get(tipo, 0.0), 0.0)
        pasa = min(pedido, techo)
        aceptados += pasa
        if pedido > pasa:
            rechazados += pedido - pasa
            detalle.append((tipo, pedido, techo))
    return aceptados, rechazados, sin_atribuir, detalle


def liquidar(p: Perfil, par: Parametros, ruta: str) -> Liquidacion:
    if ruta not in RUTAS:
        raise ValueError(f"Ruta '{ruta}' no válida. Usa 'A' o 'B'.")

    L = Liquidacion(ruta=ruta)
    uvt = par.uvt

    # --- 1. ingresos ---------------------------------------------------
    trabajo = p.get("ingresos.rentas_trabajo_honorarios")
    capital = p.get("ingresos.rentas_capital")
    otras = p.get("ingresos.otras_rentas_no_laborales")

    L._r("Rentas de trabajo (honorarios y compensación por servicios)", trabajo, +1,
         fuente="ET art. 335 y art. 103")
    L._r("Rentas de capital", capital, +1, fuente="ET art. 338")
    L._r("Otras rentas no laborales", otras, +1, fuente="ET art. 340")
    brutos = trabajo + capital + otras
    L._r("= Total ingresos brutos cédula general", brutos)

    # --- 2. INCRNGO ----------------------------------------------------
    incrngo = p.total_incrngo
    L._r(
        "− Ingresos no constitutivos de renta (INCRNGO)", incrngo, -1,
        nota="Aportes obligatorios de salud y pensión + componente inflacionario. "
             "Restan ANTES del tope del 40%: no lo consumen.",
        fuente="ET arts. 55 y 56",
    )
    netos = brutos - incrngo
    L._r("= Ingresos netos (base del límite del 40%)", netos)

    # --- 3. costos, solo ruta A ----------------------------------------
    costos, rechazo_costos, sin_atribuir, detalle_costos = _costos_aceptados(p, ruta)
    L.costos_solicitados = p.total_costos if ruta == "A" else 0
    L.costos_rechazados_por_tipo = rechazo_costos
    L.costos_sin_atribuir = sin_atribuir
    L.detalle_tope_costos = detalle_costos
    L._r(
        "− Costos y gastos procedentes", costos, -1,
        nota=("Cada uno exige factura o documento soporte, y los pagos a "
              "contratistas exigen verificar sus aportes a seguridad social "
              "(art. 108 par. 2 ET). No hay un tope global, pero sí uno POR "
              "TIPO DE RENTA: el costo de un tipo no puede superar sus "
              "ingresos menos sus INCRNGO." if ruta == "A"
              else "No aplica en Ruta B: son excluyentes con la renta exenta."),
        fuente="ET art. 336 num. 4",
    )
    # Renglón incondicional aunque valga cero: el comparativo imprime las dos
    # rutas lado a lado POR POSICIÓN, y un renglón condicional desalinea la
    # columna entera.
    L._r("  [costos rechazados por el tope por tipo de renta]", rechazo_costos, 0,
         nota="El Decreto 1625 art. 1.2.1.20.5 no topa los costos contra la "
              "cédula sino contra CADA tipo de renta. Lo que excede el techo "
              "de su tipo no se puede restar de otro: no genera pérdida "
              "trasladable a las demás rentas de la cédula.",
         fuente=_fuente(par, "topes.costos_por_tipo_de_renta.aplica",
                        "Decreto 1625 de 2016 art. 1.2.1.20.5 inciso final"))

    # --- 4. deducciones dentro del tope conjunto ------------------------
    gmf = p.get("deducciones.gmf_pagado") * par.exigir("topes.gmf.porcentaje_deducible")
    vivienda = min(
        p.get("deducciones.intereses_vivienda"),
        par.exigir("topes.intereses_vivienda.tope_uvt") * uvt,
    )
    prepagada = min(
        p.get("deducciones.medicina_prepagada"),
        par.exigir("topes.medicina_prepagada.tope_mensual_uvt")
        * par.get("topes.medicina_prepagada.meses", 12)
        * uvt,
    )
    voluntarios = min(
        p.get("deducciones.aportes_voluntarios"),
        brutos * par.exigir("topes.aportes_voluntarios.porcentaje_ingreso"),
        par.exigir("topes.aportes_voluntarios.tope_uvt") * uvt,
    )

    # --- 5. dependientes: dos vías excluyentes, se toma la mejor --------
    n_dep = int(p.get("deducciones.dependientes"))
    max_dep = par.exigir("topes.dependientes_72uvt.maximo_dependientes")
    # Las dos vías de dependientes aplican ÚNICAMENTE sobre rentas de
    # trabajo. El art. 336 num. 3 inciso 2 dice «el TRABAJADOR podrá
    # deducir», y el Decreto 1625 art. 1.2.1.20.3 es explícito: «aplican
    # únicamente a los ingresos provenientes de rentas de trabajo».
    #
    # `dep_10` ya se calculaba sobre `trabajo`; `dep_72` no dependía de él,
    # así que un perfil con $300.000.000 de otras rentas no laborales, CERO
    # honorarios y 4 dependientes recibía $14.342.112 de deducción a la que
    # no tiene derecho. La asimetría era un descuido, no una decisión.
    uvt_por_dep = par.exigir("topes.dependientes_72uvt.uvt_por_dependiente")
    dep_72 = 0.0
    if trabajo > 0:
        dep_72 = min(n_dep, max_dep) * uvt_por_dep * uvt

    # La exclusividad es POR DEPENDIENTE, no por contribuyente. El Decreto
    # 1625 art. 1.2.1.20.3 dice «un mismo dependiente solo dará lugar a una
    # de estas dos deducciones», no «el contribuyente solo podrá tomar una
    # de las dos». El motor evaluaba dos escenarios todo-o-nada y se perdía
    # el que casi siempre gana: tomar el 10% por UN dependiente —la del art.
    # 387 no depende de cuántos sean— y 72 UVT por CADA UNO de los demás.
    #
    # Con $180.000.000 de renta de trabajo y 4 dependientes, el motor
    # deducía $18.000.000 y la norma permite $28.756.584. Era un error
    # conservador, pero el repo promete en tres sitios que «calcula ambas y
    # toma la mejor», y no era la mejor.
    dep_72_resto = 0.0
    if trabajo > 0 and n_dep > 1:
        dep_72_resto = min(n_dep - 1, max_dep) * uvt_por_dep * uvt

    dep_10 = 0.0
    if n_dep > 0:
        dep_10 = min(
            trabajo * par.exigir("topes.dependientes_10pct.porcentaje_renta_trabajo"),
            par.exigir("topes.dependientes_10pct.tope_mensual_uvt")
            * par.get("topes.dependientes_10pct.meses", 12)
            * uvt,
        )

    # 1% de compras con factura electrónica
    fe = min(
        p.get("deducciones.compras_con_factura_electronica")
        * par.exigir("topes.deduccion_1pct_factura_electronica.porcentaje_compras"),
        par.exigir("topes.deduccion_1pct_factura_electronica.tope_uvt") * uvt,
    )

    # Qué deducción entra al tope conjunto y cuál no lo decide
    # `dentro_del_tope_conjunto` de parametros.toml, no una suma escrita a
    # mano acá.
    #
    # Los flags existían en knowledge/ desde el principio y NO LOS LEÍA
    # NADIE: la partición estaba cableada en esta función. Hoy coinciden, y
    # ese es el problema — es la misma clase de divergencia knowledge↔motor
    # que `_fuente()` cerró para las citas, esperando a que alguien corrija
    # un flag creyendo que cambia el cálculo y no pase nada.
    #
    # Las de dependientes NO van acá: se resuelven por escenario, más abajo,
    # porque la vía elegida decide cuál de las dos aplica.
    partidas = (
        ("topes.gmf", gmf),
        ("topes.intereses_vivienda", vivienda),
        ("topes.medicina_prepagada", prepagada),
        ("topes.aportes_voluntarios", voluntarios),
        ("topes.deduccion_1pct_factura_electronica", fe),
    )
    ded_fijas = sum(
        v for bloque, v in partidas
        if par.get(f"{bloque}.dentro_del_tope_conjunto", True)
    )
    fuera_fijas = sum(
        v for bloque, v in partidas
        if not par.get(f"{bloque}.dentro_del_tope_conjunto", True)
    )

    tope = max(
        min(
            netos * par.exigir("topes.conjunto_deducciones_exentas.porcentaje_ingresos_netos"),
            par.exigir("topes.conjunto_deducciones_exentas.tope_uvt") * uvt,
        ),
        0,
    )

    def evaluar(dep_dentro: float, dep_fuera: float):
        """Liquida una de las dos combinaciones de dependientes.

        La renta exenta se calcula ACÁ ADENTRO y no antes, porque su base
        depende de las deducciones —y las deducciones dependen de qué vía de
        dependientes se tome—.
        """
        ded_limitadas = ded_fijas + dep_dentro

        exenta = 0.0
        if ruta == "B":
            # Art. 206 num. 10 inciso 2: la base de la exención se calcula
            # UNA VEZ SE DETRAIGAN los INCRNGO, las deducciones y las rentas
            # exentas distintas de esta. No es el 25% del ingreso bruto.
            base = trabajo - incrngo - ded_limitadas - dep_fuera - fuera_fijas
            exenta = min(
                max(base, 0) * par.exigir("topes.renta_exenta_25.porcentaje"),
                par.exigir("topes.renta_exenta_25.tope_anual_uvt") * uvt,
            )

        solicitado = ded_limitadas + exenta
        aplicado = min(solicitado, tope)
        rechazado = solicitado - aplicado
        rl = max(netos - costos - aplicado - dep_fuera - fuera_fijas, 0)
        return {
            "impuesto": impuesto_241(rl, par),
            "renta_liquida": rl,
            "exenta": exenta,
            "dep_dentro": dep_dentro,
            "dep_fuera": dep_fuera,
            "aplicado": aplicado,
            "rechazado": rechazado,
        }

    # Las dos vías de dependientes también salen de su flag, no de una
    # constante de esta función.
    dep10_dentro = par.get("topes.dependientes_10pct.dentro_del_tope_conjunto", True)
    dep72_dentro = par.get("topes.dependientes_72uvt.dentro_del_tope_conjunto", False)

    def escenario(v10: float, v72: float):
        dentro = (v10 if dep10_dentro else 0.0) + (v72 if dep72_dentro else 0.0)
        fuera = (0.0 if dep10_dentro else v10) + (0.0 if dep72_dentro else v72)
        return evaluar(dentro, fuera)

    opciones = [("72 UVT por dependiente (fuera del tope)", escenario(0.0, dep_72))]
    if n_dep > 0:
        resto = min(n_dep - 1, max_dep)
        etiqueta = (
            "10% de la renta de trabajo (dentro del tope)" if resto == 0 else
            f"10% de la renta de trabajo por uno (dentro del tope) + 72 UVT "
            f"por los otros {resto} (fuera)"
        )
        opciones.append((etiqueta, escenario(dep_10, dep_72_resto)))

    # El desempate va en la clave, y no es cosmético.
    #
    # Con `key=o["impuesto"]` a secas, dos escenarios que empatan en impuesto
    # los resuelve el ORDEN DE LA LISTA. Y empatan siempre que el impuesto da
    # cero, o sea con la base bajo 1.090 UVT ($54.280.910), que es media
    # población objetivo de esta herramienta. Ganaba la vía de 72 UVT pura
    # por estar escrita primero, aunque dejara una base MAYOR.
    #
    # No cambia la plata —los dos pagan cero— pero sí cambia lo que el
    # contribuyente ESCRIBE: `renglones_al_210()` manda transcribir esa base
    # a la casilla «Renta líquida gravable». Reproducido con 90.000.000 de
    # honorarios y 2 dependientes: subir los aportes voluntarios en
    # $1.000.000 subía la base declarada de $49.064.472 a $53.478.944.
    # Deducir más y declarar más. Y la vía que imprime el CLI pedía soportes
    # de dos dependientes por 72 UVT cuando convenía el 10% por uno.
    #
    # El objetivo correcto es lexicográfico: primero el menor impuesto,
    # después la menor base. Una base más baja nunca perjudica —art. 236: es
    # la que se compara contra el patrimonio— y ante dos formas de pagar lo
    # mismo, se declara la que la norma permite.
    #
    # Lo encontró la capa de relaciones metamórficas el día que se escribió,
    # con la relación «más deducción nunca sube la base». Ninguna de las
    # cuatro capas anteriores podía verlo: `referencia.py` tenía los
    # escenarios en el MISMO orden.
    via, e = min(opciones, key=lambda o: (o[1]["impuesto"], o[1]["renta_liquida"]))
    L.dependientes_via = via if n_dep else "sin dependientes"
    renta_liquida = e["renta_liquida"]
    tope_aplicado, rechazado = e["aplicado"], e["rechazado"]

    # --- 6. renglones de deducciones -----------------------------------
    # Se emiten SIEMPRE los mismos renglones, en el mismo orden, aunque
    # valgan cero. El comparativo imprime las dos rutas lado a lado por
    # posición: un renglón condicional desalinea la columna entera y hace
    # que un número aparezca bajo la etiqueta de otro.
    L._r("− Renta exenta 25%", e["exenta"], -1,
         nota=("Base = rentas de trabajo − INCRNGO − deducciones (art. 206 "
               "num. 10 inciso 2). Tope 790 UVT ANUALES —no 240 UVT/mes, que "
               "es el texto derogado— y además compite dentro del tope "
               "conjunto del 40%." if ruta == "B"
               else "No aplica en Ruta A: es excluyente con los costos."),
         fuente="ET art. 206 num. 10, mod. Ley 2277 de 2022 art. 2")
    L._r("− GMF deducible (50% del 4x1000 pagado)", gmf, -1,
         fuente=_fuente(par, "topes.gmf.porcentaje_deducible", "ET art. 115"))
    L._r("− Intereses de vivienda", vivienda, -1,
         fuente=_fuente(par, "topes.intereses_vivienda.tope_uvt", "ET art. 119"))
    L._r("− Medicina prepagada", prepagada, -1,
         fuente=_fuente(par, "topes.medicina_prepagada.tope_mensual_uvt",
                        "ET art. 387"))
    L._r("− Aportes voluntarios AFP / AFC", voluntarios, -1,
         fuente=_fuente(par, "topes.aportes_voluntarios.tope_uvt",
                        "ET arts. 126-1 y 126-4"))
    L._r("− Dependientes (10% renta de trabajo)", e["dep_dentro"], -1,
         nota="Consume el tope del 40%. Excluyente con la de 72 UVT PARA EL "
              "MISMO DEPENDIENTE (Decreto 1625 art. 1.2.1.20.3): esta vía "
              "gasta uno, y los demás siguen valiendo 72 UVT cada uno. No "
              "depende de cuántos sean, así que solo tiene sentido gastar "
              "en ella al primero.",
         fuente=_fuente(par, "topes.dependientes_10pct.tope_mensual_uvt",
                        "ET art. 387"))

    # Subtotal explícito. Las plantillas `comparativo.md` y
    # `formulario-210.md` piden UNA casilla de «Deducciones» y el motor
    # emitía cinco renglones sueltos sin su suma, así que el modelo que llena
    # la plantilla tenía que sumarlos a mano — contra la primera regla de
    # AGENTS.md, y sobre las cifras que van al formulario.
    L._r("  = Subtotal deducciones dentro del tope", ded_fijas + e["dep_dentro"], 0,
         nota="GMF + vivienda + prepagada + AFP/AFC + dependientes por el 10%. "
              "Es lo que compite contra el tope del 40% junto con la renta "
              "exenta, y lo que va a la casilla única de «Deducciones» del "
              "210. NO incluye la renta exenta, que va en su propia casilla.")

    L._r("  [tope conjunto 40% / 1.340 UVT]", tope, 0,
         nota="Lo que exceda este tope se pierde.",
         fuente=_fuente(par, "topes.conjunto_deducciones_exentas.tope_uvt",
                        "ET art. 336 num. 3"))
    L._r("  [rechazado por el tope]", rechazado, 0,
         nota="Deducciones y rentas exentas solicitadas que el tope no dejó pasar.")
    L.tope_conjunto = tope
    L.rechazado_por_tope = rechazado

    L._r("− Dependientes (72 UVT c/u — FUERA del tope)", e["dep_fuera"], -1,
         nota="No consume el tope del 40% y no exige factura: solo acreditar "
              "la condición. Hasta 4 dependientes. Excluyente con la del 10% "
              "PARA EL MISMO DEPENDIENTE, no para el contribuyente: se puede "
              "tomar el 10% por uno y 72 UVT por los otros.",
         fuente=_fuente(par, "topes.dependientes_72uvt.uvt_por_dependiente",
                        "ET art. 336 num. 3 inciso 2, Ley 2277 de 2022 art. 7"))
    L._r("− Deducción 1% compras con factura electrónica", fe, -1,
         nota="Exige factura electrónica a tu NIT/cédula y pago electrónico.",
         fuente=_fuente(par, "topes.deduccion_1pct_factura_electronica.tope_uvt",
                        "ET art. 336 num. 5"))
    L._r("  = Subtotal deducciones fuera del tope", e["dep_fuera"] + fuera_fijas, 0,
         nota="Dependientes por 72 UVT + el 1% de factura electrónica. No "
              "compiten contra el tope del 40%: restan enteras.")

    # --- 8. impuesto ---------------------------------------------------
    L.renta_liquida = renta_liquida
    L._r("= RENTA LÍQUIDA GRAVABLE", renta_liquida)

    L.impuesto = impuesto_241(renta_liquida, par)
    L._r("IMPUESTO SOBRE LA RENTA", L.impuesto, +1,
         fuente=_fuente(par, "tarifa.rangos", "ET art. 241"))

    donado = p.get("descuentos.donaciones_certificadas_rte")
    descuento = min(
        donado * par.exigir("topes.descuento_donaciones.porcentaje_descuento"),
        L.impuesto * par.exigir("topes.descuento_donaciones.tope_porcentaje_impuesto"),
    )
    L._r("− Descuento por donaciones", descuento, -1,
         nota="Solo con certificado de entidad del Régimen Tributario Especial "
              "firmado por representante legal y contador o revisor fiscal.",
         fuente=_fuente(par, "topes.descuento_donaciones.porcentaje_descuento",
                        "ET art. 257"))

    L.impuesto_neto = max(L.impuesto - descuento, 0)
    L._r("= Impuesto neto de renta", L.impuesto_neto)

    retenciones = p.get("anticipos.retenciones_practicadas")
    saldo_favor_ant = p.get("anticipos.saldo_a_favor_anio_anterior")
    L._r("− Retenciones practicadas en el año", retenciones, -1,
         nota="Lo que terceros ya le giraron a la DIAN por cuenta tuya. Se "
              "imputa al impuesto, no a la base. Suma de los certificados de "
              "retención de cada pagador.",
         fuente="ET art. 373")
    L._r("− Saldo a favor del año anterior", saldo_favor_ant, -1,
         nota="Solo si no lo pediste en devolución ni lo imputaste ya.",
         fuente="ET art. 815")

    L.saldo = L.impuesto_neto - retenciones - saldo_favor_ant
    L._r("= SALDO A PAGAR" if L.saldo >= 0 else "= SALDO A FAVOR", abs(L.saldo))

    return L


# ---------------------------------------------------------------------
# Sensibilidad — cuánto vale cada palanca, en pesos
# ---------------------------------------------------------------------

# Qué le cuesta al contribuyente activar cada palanca. La tabla se ordena
# por ahorro, pero sin esta distinción es engañosa: "donar $5.400.000 para
# ahorrar $1.350.000" aparecía como palanca al lado de "pedir un certificado
# gratis", y son cosas opuestas.
PAPEL = "papel"            # conseguir un documento. No cuesta plata
CONDICION = "condicion"    # depende de un hecho que se cumple o no
DESEMBOLSO = "desembolso"  # exige sacar plata del bolsillo


@dataclass
class Palanca:
    etiqueta: str
    ahorro_a: float
    ahorro_b: float
    solo_ruta: str | None
    nota: str
    tipo: str = PAPEL
    costo: float = 0.0        # plata que hay que desembolsar, si aplica

    # Saldos de partida, para poder medir el ahorro REAL. Ver `ahorro_max`.
    base_a: float = 0.0
    base_b: float = 0.0
    saldo_a: float = 0.0
    saldo_b: float = 0.0

    @property
    def ahorro_max(self) -> float:
        """Lo que esta palanca ahorra DE VERDAD, desde donde está el usuario.

        Era `max(ahorro_a, ahorro_b)`, y eso sobreestima: el contribuyente no
        paga el mejor de los dos ahorros, paga el mejor de los dos SALDOS.
        La cuenta correcta es

            min(saldo_A, saldo_B) − min(saldo_A', saldo_B')

        y la anterior daba de más exactamente `diferencia_entre_rutas` cuando
        la palanca solo opera en la ruta que pierde. Medido sobre 600
        perfiles: 1.404 palancas sobreestimadas de ~2.400, y ninguna
        subestimada.

        No es un error cosmético: esta tabla se titula «cuánto vale cada
        palanca» y es el número con el que la gente decide si desembolsa. Una
        fila prometía $94.500.000 cuando el ahorro real eran $80.730.576, y
        el «PIERDES $170.063.585» de un desembolso eran en realidad
        $183.833.009. Además la tabla se ORDENA por este valor, así que la
        palanca que la encabezaba podía valer cero en la ruta que el motor
        recomienda dos pantallas más arriba.
        """
        return min(self.base_a, self.base_b) - min(self.saldo_a, self.saldo_b)

    @property
    def neto(self) -> float:
        """Ahorro menos lo que hay que desembolsar para conseguirlo."""
        return self.ahorro_max - self.costo

    @property
    def conviene(self) -> bool:
        """Un desembolso solo conviene si el ahorro supera lo desembolsado.

        Casi nunca pasa con donaciones (descuento del 25%) ni con prepagada.
        Sí pasa con los aportes voluntarios cuando la tarifa marginal es alta,
        porque la plata no se pierde: cambia de bolsillo.
        """
        return self.tipo != DESEMBOLSO or self.neto > 0


def _saldo(p: Perfil, par: Parametros, ruta: str) -> float:
    return liquidar(p, par, ruta).saldo


def sensibilidad(p: Perfil, par: Parametros) -> list[Palanca]:
    """Perturba una variable a la vez y mide el impuesto que ahorra.

    Las magnitudes de prueba se escalan al tamaño del contribuyente, para que
    la tabla sea informativa tanto para quien factura 50 M como para quien
    factura 500 M.
    """
    uvt = par.uvt
    base_a = _saldo(p, par, "A")
    base_b = _saldo(p, par, "B")
    ingreso = max(p.ingresos_brutos, 1)
    palancas: list[Palanca] = []

    def probar(etiqueta, cambios, nota, solo_ruta=None, tipo=PAPEL, costo=0.0):
        alt = p.copia_con(**cambios)
        pa, pb = _saldo(alt, par, "A"), _saldo(alt, par, "B")
        palancas.append(
            Palanca(etiqueta, base_a - pa, base_b - pb, solo_ruta, nota, tipo,
                    costo, base_a=base_a, base_b=base_b, saldo_a=pa, saldo_b=pb)
        )

    # --- dependientes ---------------------------------------------------
    # Una sola fila, no una por cada cantidad. Con frecuencia el 2º, 3º y 4º
    # dependiente valen exactamente lo mismo que el primero, y cuatro filas
    # con la misma cifra en una tabla titulada "cuánto vale cada palanca"
    # invitan a sumarlas cuando el valor marginal es cero.
    actuales = int(p.get("deducciones.dependientes"))
    max_dep = par.exigir("topes.dependientes_72uvt.maximo_dependientes")
    # Uno más que el tope de la deducción de 72 UVT: la del 10% consume un
    # dependiente DISTINTO (Decreto 1625 art. 1.2.1.20.3), así que el quinto
    # todavía sirve. Explorar solo hasta 4 escondía esa fila entera.
    max_util = max_dep + 1
    if actuales < max_util:
        por_cantidad = {}
        for n in range(actuales + 1, max_util + 1):
            alt = p.copia_con(deducciones__dependientes=n)
            sa, sb = _saldo(alt, par, "A"), _saldo(alt, par, "B")
            por_cantidad[n] = min(base_a, base_b) - min(sa, sb)
        mejor_ahorro = max(por_cantidad.values())
        # La cantidad MÍNIMA que alcanza el máximo: perseguir soportes de más
        # no aporta nada y cuesta trámites.
        suficientes = min(n for n, v in por_cantidad.items() if v == mejor_ahorro)

        # El motivo por el que sobran depende del caso, y decir el equivocado
        # es peor que no decir ninguno: de esa explicación el usuario deduce
        # qué esperar el año siguiente.
        alt = p.copia_con(deducciones__dependientes=suficientes)
        # La vía se consulta en la ruta que da el ahorro que se está
        # reportando. Mirar siempre la A daba una razón que contradecía la
        # cifra cuando ganaba la B.
        ahorro_a = base_a - _saldo(alt, par, "A")
        ruta_del_ahorro = "A" if ahorro_a >= base_b - _saldo(alt, par, "B") else "B"
        L_alt = liquidar(alt, par, ruta_del_ahorro)
        via = L_alt.dependientes_via
        if suficientes < max_util:
            # El motivo se lee del RESULTADO, no de la etiqueta de la vía.
            # Antes se deducía de si la cadena traía "10%", y ahora la vía
            # que gana casi siempre trae las dos cosas a la vez: la
            # explicación habría quedado fija en una de las dos ramas.
            motivo = ("tu base gravable ya llegó al tramo de tarifa 0%, así "
                      "que restar más no cambia el impuesto"
                      if L_alt.impuesto == 0
                      else "lo que agregarían no baja tu impuesto en la ruta "
                           "que te conviene")
            extra = f" Acreditar más de {suficientes} no agrega nada: {motivo}."
        else:
            # Con la vía de 72 UVT cada dependiente vale por separado. Quien
            # solo pueda acreditar uno necesita saber cuánto vale ESE uno, no
            # solo el total de cuatro.
            primero = por_cantidad[actuales + 1]
            extra = (f" Cada dependiente cuenta por separado: el primero vale "
                     f"{_cop(primero)} y los {suficientes - actuales} juntos, "
                     f"{_cop(mejor_ahorro)}."
                     if suficientes > actuales + 1 else "")
        probar(
            f"Acreditar {suficientes} dependiente(s) — hoy tienes {actuales}",
            {"deducciones__dependientes": suficientes},
            "FUERA del tope del 40%. No exige factura ni desembolso: se acredita "
            "la condición. Padres y hermanos con ingresos anuales < 260 UVT "
            "cuentan; hijos estudiando, hasta los 25 (Ley 2411 de 2024)." + extra,
            tipo=CONDICION,
        )

    # --- seguridad social ------------------------------------------------
    if not p.get("incrngo.aportes_obligatorios_salud_pension"):
        # base de cotización del independiente: 40% del ingreso, tarifa ~28,5%
        estimado = round(ingreso * 0.40 * 0.285)
        probar(
            f"Aportes obligatorios salud+pensión del año (~{_cop(estimado)})",
            {"incrngo__aportes_obligatorios_salud_pension": estimado},
            "Es INCRNGO, no deducción: resta ANTES del tope del 40% y no lo "
            "consume. Exige planillas PILA pagadas. Si ya cotizaste, es solo "
            "conseguir el papel; si no, es un desembolso que además cierra tu "
            "exposición ante la UGPP.",
            tipo=CONDICION,
        )

    # --- aportes voluntarios ----------------------------------------------
    if not p.get("deducciones.aportes_voluntarios"):
        techo = min(ingreso * 0.30, par.exigir("topes.aportes_voluntarios.tope_uvt") * uvt)
        probar(
            f"Aportes voluntarios AFP/AFC al tope (~{_cop(techo)})",
            {"deducciones__aportes_voluntarios": round(techo)},
            "⚠ Solo sirve si se hicieron ANTES del 31 de diciembre del año "
            "gravable. Si el año ya cerró, este número es tu costo de "
            "oportunidad para el año en curso. Es un desembolso, pero la plata "
            "no se pierde: queda en tu fondo, inmovilizada bajo las reglas de "
            "los arts. 126-1 y 126-4.",
            tipo=DESEMBOLSO, costo=round(techo),
        )

    # --- medicina prepagada -------------------------------------------------
    if not p.get("deducciones.medicina_prepagada"):
        techo = (par.exigir("topes.medicina_prepagada.tope_mensual_uvt")
                 * par.get("topes.medicina_prepagada.meses", 12) * uvt)
        probar(
            f"Medicina prepagada al tope ({_cop(techo)})",
            {"deducciones__medicina_prepagada": round(techo)},
            "Dentro del tope del 40%: en Ruta B compite contra la renta exenta y "
            "puede no agregar nada. Si YA la pagas, es solo pedir el "
            "certificado; contratarla para ahorrar impuesto casi nunca sale a "
            "cuenta.",
            tipo=DESEMBOLSO, costo=round(techo),
        )

    # --- intereses de vivienda ----------------------------------------------
    if not p.get("deducciones.intereses_vivienda"):
        techo = min(par.exigir("topes.intereses_vivienda.tope_uvt") * uvt, ingreso * 0.15)
        probar(
            f"Intereses de crédito de vivienda (~{_cop(techo)})",
            {"deducciones__intereses_vivienda": round(techo)},
            "Solo aplica si YA tienes crédito de vivienda: es pedirle el "
            "certificado al banco. Nadie se endeuda para deducir intereses.",
            tipo=CONDICION,
        )

    # --- costos, solo ruta A --------------------------------------------------
    if p.total_costos == 0:
        estimado = round(ingreso * 0.30)
        probar(
            f"Costos y gastos soportados (~{_cop(estimado)})",
            {"costos__otros": estimado},
            "SOLO RUTA A, y solo con costos que YA existen y estén soportados. "
            "Cada peso exige factura electrónica o documento soporte, y los "
            "pagos a contratistas exigen verificar sus aportes. Esto NO es una "
            "invitación a inventar gastos: si no ocurrieron, no van.",
            solo_ruta="A", tipo=CONDICION,
        )

    # --- factura electrónica ---------------------------------------------------
    if not p.get("deducciones.compras_con_factura_electronica"):
        compras = round(ingreso * 0.20)
        probar(
            f"Compras con factura electrónica a tu cédula (~{_cop(compras)})",
            {"deducciones__compras_con_factura_electronica": compras},
            "Deduce el 1%, tope 240 UVT, FUERA del tope del 40%. Sobre compras "
            "que ya hiciste: se trata de pedir la factura a tu NIT/cédula y "
            "pagar por medio electrónico, no de comprar más.",
            tipo=CONDICION,
        )

    # --- donaciones ------------------------------------------------------------
    if not p.get("descuentos.donaciones_certificadas_rte"):
        monto = round(ingreso * 0.03)
        probar(
            f"Donaciones certificadas a entidad del RTE (~{_cop(monto)})",
            {"descuentos__donaciones_certificadas_rte": monto},
            "Es DESCUENTO del 25% sobre el impuesto, no deducción. Ojo con la "
            "aritmética: donar $100 ahorra $25, así que como jugada fiscal "
            "SIEMPRE pierdes plata. Tiene sentido si ibas a donar de todas "
            "formas — y entonces lo que importa es exigir el certificado de "
            "una entidad del RTE, sin el cual la donación vale $0.",
            tipo=DESEMBOLSO, costo=monto,
        )

    # Primero lo que solo exige un papel o una condición ya cumplida, y
    # dentro de cada grupo por ahorro. Un desembolso que pierde plata en neto
    # se manda al final: se muestra para que se entienda por qué no conviene,
    # no como recomendación.
    orden = {PAPEL: 0, CONDICION: 0, DESEMBOLSO: 1}
    palancas.sort(key=lambda x: (orden[x.tipo], not x.conviene, -x.ahorro_max))
    return [x for x in palancas if x.ahorro_max > 0]


# ---------------------------------------------------------------------
# Verificaciones de obligación y riesgo
# ---------------------------------------------------------------------

def verificar_obligaciones(p: Perfil, par: Parametros) -> list[dict]:
    """Chequeos de umbral que no dependen del cálculo del impuesto."""
    uvt = par.uvt
    checks = []

    # ¿obligado a declarar?
    u = par.get("umbrales.obligado_a_declarar", {})
    disparadores = []
    if p.ingresos_brutos >= u.get("ingresos_brutos_uvt", 1400) * uvt:
        disparadores.append("ingresos brutos ≥ 1.400 UVT")
    if p.patrimonio_bruto >= u.get("patrimonio_bruto_uvt", 4500) * uvt:
        disparadores.append("patrimonio bruto ≥ 4.500 UVT")
    consig = p.get("verificaciones.consignaciones_totales_anio")
    if consig >= u.get("consignaciones_uvt", 1400) * uvt:
        disparadores.append("consignaciones ≥ 1.400 UVT")

    # Con el perfil a medias, "NO obligado" es el titular más peligroso que
    # puede dar esta herramienta: alguien lo lee, no declara, y la sanción por
    # extemporaneidad corre. Solo se afirma si están los tres insumos que el
    # perfil sí modela; los otros dos umbrales (consumos con tarjeta y compras
    # totales) no están en el perfil y por eso el mensaje los nombra aparte.
    faltan_insumos = [
        etiqueta for valor, etiqueta in (
            (p.ingresos_brutos, "ingresos"),
            (p.patrimonio_bruto, "patrimonio bruto"),
            (consig, "consignaciones"),
        ) if not valor
    ]

    if disparadores:
        estado = "SÍ"
        detalle = "Se cumple: " + "; ".join(disparadores)
        severidad = "info"
    elif faltan_insumos:
        estado = "NO SE PUEDE AFIRMAR TODAVÍA"
        detalle = (
            f"Ningún umbral se supera con lo cargado, pero falta(n) "
            f"{', '.join(faltan_insumos)}. Con el perfil a medias esto NO "
            f"significa que no tengas que declarar. Basta con superar UNO de "
            f"los cinco umbrales —ingresos, patrimonio, consignaciones, "
            f"consumos con tarjeta de crédito o compras totales, todos de "
            f"1.400 UVT salvo patrimonio, que es 4.500— y los dos últimos ni "
            f"siquiera están en el perfil. Complétalo antes de concluir."
        )
        severidad = "media"
    else:
        estado = "NO por los datos cargados"
        detalle = (
            "Ningún umbral superado. Verifica igual tus consumos con tarjeta de "
            "crédito y tus compras totales del año: son dos umbrales de 1.400 "
            "UVT que este motor no modela y que bastan por sí solos."
        )
        severidad = "info"

    checks.append({
        "id": "OBL-01",
        "titulo": "¿Obligado a declarar renta?",
        "estado": estado,
        "detalle": detalle,
        "severidad": severidad,
        "fuente": u.get("fuente", ""),
    })

    # ¿pierde la calidad de no responsable de IVA?
    #
    # El art. 437 par. 3 num. 6 no mide "todo lo que entró": mide las
    # consignaciones PROVENIENTES DE ACTIVIDADES GRAVADAS CON IVA. Omitir ese
    # calificador convierte una advertencia útil en una alarma falsa que
    # puede empujar a alguien a inscribirse como responsable de IVA sin que
    # le corresponda.
    iva = par.get("umbrales.no_responsable_iva", {})
    tope_iva = iva.get("consignaciones_uvt", 3500) * uvt
    tope_estado = iva.get("consignaciones_uvt_contratistas_del_estado", 4000) * uvt

    calificador = (
        "El campo consignaciones_totales_anio debe traer SOLO las "
        "consignaciones provenientes de actividades gravadas con IVA. Los "
        "traslados entre cuentas propias, los préstamos y el dinero de "
        "terceros en tránsito no cuentan. Si tu actividad es exportación de "
        "servicios (art. 481 lit. c) o está excluida, esa cifra puede ser cero "
        "aunque por tus cuentas pasen cientos de millones."
    )

    if consig == 0:
        estado, sev = "SIN CUANTIFICAR", "media"
        detalle = (
            f"No has cuantificado las consignaciones gravadas del año. El umbral "
            f"es {_cop(tope_iva)} ({_cop(tope_estado)} si tus ingresos vienen de "
            f"contratos con el Estado, par. 5). Se mide sobre consignaciones y "
            f"no sobre tu ingreso propio, así que quien recibe plata de clientes "
            f"y la redistribuye puede superarlo sin que su ingreso se acerque. "
            f"{calificador}"
        )
    elif consig > tope_iva:
        estado, sev = "UMBRAL SUPERADO", "alta"
        detalle = (
            f"Consignaciones gravadas {_cop(consig)} > {_cop(tope_iva)}. Si la "
            f"cifra está bien construida, pierdes la calidad de no responsable "
            f"de IVA: inscripción, facturación, declaraciones de IVA por período "
            f"y sanción por no declarar (art. 643 ET, no el 641, si nunca las "
            f"presentaste). Antes de aceptarlo, verifica dos cosas: que no estés "
            f"contando el mismo dinero dos veces —el giro en la plataforma y su "
            f"abono en el banco son un solo hecho— y que todo lo sumado provenga "
            f"de actividad gravada. {calificador} Resuélvelo con tu contador "
            f"ANTES de presentar renta."
        )
    else:
        margen = tope_iva - consig
        estado, sev = "DENTRO DEL UMBRAL", "info"
        detalle = (f"Consignaciones gravadas {_cop(consig)}, margen de "
                   f"{_cop(margen)}. {calificador}")

    checks.append({
        "id": "R-01",
        "titulo": "Calidad de no responsable de IVA (consignaciones gravadas)",
        "estado": estado,
        "detalle": detalle,
        "severidad": sev,
        "fuente": iva.get("fuente", "ET art. 437 par. 3 num. 6"),
    })

    # ¿supera el tope indicativo de costos del art. 336-1?
    tope_ind = par.get("topes.tope_indicativo_costos.porcentaje_ingresos_brutos", 0.60)
    if p.total_costos > p.ingresos_brutos * tope_ind and p.ingresos_brutos:
        checks.append({
            "id": "R-09",
            "titulo": "Costos por encima del tope indicativo del 60%",
            "estado": f"{p.total_costos / p.ingresos_brutos:.0%} de los ingresos brutos",
            "detalle": (
                f"Los costos ({_cop(p.total_costos)}) superan el 60% de los "
                f"ingresos brutos que el art. 336-1 ET fija como tope indicativo. "
                f"Superarlo es legítimo, pero obliga a indicarlo EXPRESAMENTE en "
                f"la declaración marcando la casilla informativa; no hacerlo "
                f"acarrea la sanción del art. 651 num. 1 lit. d). Además esos "
                f"costos deben estar soportados con factura electrónica, nómina "
                f"electrónica o documento equivalente ELECTRÓNICO — lo que choca "
                f"con la estrategia de documento soporte en físico. Míralo con tu "
                f"contador antes de decidir la Ruta A."
            ),
            "severidad": "alta",
            "fuente": "ET art. 336-1, adicionado por Ley 2277 de 2022 art. 60",
        })

    # ¿el techo de costos por tipo de renta recortó algo?
    #
    # Se reporta aunque gane la Ruta B: es un hecho de los DATOS, no del
    # camino elegido, y el usuario que ve "Ruta A: costos $200.000.000" en el
    # comparativo tiene que saber que la norma solo deja pasar una parte.
    _, rechazo_tipo, sin_atribuir, detalle_tipo = _costos_aceptados(p, "A")
    if rechazo_tipo > 0:
        renglones = "; ".join(
            f"{NOMBRE_TIPO[t]}: costos {_cop(pedido)} contra un techo de {_cop(techo)}"
            for t, pedido, techo in detalle_tipo
        )
        checks.append({
            "id": "R-10",
            "titulo": "Costos por encima del techo de su tipo de renta",
            "estado": f"{_cop(rechazo_tipo)} no se pueden restar",
            "detalle": (
                f"{renglones}. El Decreto 1625 art. 1.2.1.20.5 inciso final no "
                f"topa los costos contra la cédula: los topa contra los ingresos "
                f"menos los INCRNGO de CADA tipo de renta. El exceso no genera "
                f"pérdida que se pueda restar de otro tipo. Si crees que estos "
                f"costos pertenecen a otro tipo de renta, decláralo en "
                f"[costos.atribucion] del perfil.toml en vez de dejarlo al "
                f"criterio por defecto."
            ),
            "severidad": "alta",
            "fuente": _fuente(par, "topes.costos_por_tipo_de_renta.aplica",
                              "Decreto 1625 de 2016 art. 1.2.1.20.5 inciso final"),
        })

    if sin_atribuir > 0:
        checks.append({
            "id": "R-11",
            "titulo": "Costos sin tipo de renta: el techo no se les pudo aplicar",
            "estado": f"{_cop(sin_atribuir)} sin atribuir",
            "detalle": (
                f"Tienes ingresos de más de un tipo de renta y no dijiste a cuál "
                f"pertenece cada costo, así que el motor NO pudo aplicarles el "
                f"techo del Decreto 1625 art. 1.2.1.20.5. No los repartió a ojo "
                f"a propósito: atribuirlos al tipo equivocado te subiría el "
                f"impuesto sin que lo debas. Escribe el bloque "
                f"[costos.atribucion] en perfil.toml —una línea por campo de "
                f"[costos], con uno de {', '.join(TIPOS_DE_RENTA)}— y vuelve a "
                f"calcular. Mientras tanto, esta cifra puede estar restando de "
                f"más."
            ),
            "severidad": "media",
            "fuente": _fuente(par, "topes.costos_por_tipo_de_renta.aplica",
                              "Decreto 1625 de 2016 art. 1.2.1.20.5 inciso final"),
        })

    # ¿agente de retención?
    #
    # Esto devolvía "NO (perfil de servicios profesionales)" HARDCODEADO, sin
    # leer un solo campo del perfil, sobre un hecho —la calidad de
    # comerciante— que el motor nunca vio. Quien vende bienes y supera las
    # 30.000 UVT leía «NO» y omitía una obligación real.
    #
    # Y era incoherente con el estándar que el propio módulo se puso doce
    # líneas más arriba: OBL-01 se niega expresamente a decir «NO» sin
    # insumos, con un comentario que explica por qué sería el titular más
    # peligroso posible. Acá hacía lo contrario.
    ar = par.get("umbrales.agente_retencion_persona_natural", {})
    tope_ar = ar.get("uvt", 30_000) * uvt
    comerciante = p.get("contribuyente.es_comerciante", None)
    supera = max(p.ingresos_brutos, p.patrimonio_bruto) >= tope_ar

    if comerciante is False:
        estado_ar, sev_ar = "NO — no eres comerciante", "info"
        detalle_ar = (
            f"Declaraste que NO ejerces actos de comercio. El art. 368-2 exige "
            f"las DOS condiciones a la vez, así que no eres agente de retención "
            f"sin importar el monto. Si empiezas a vender bienes, revísalo."
        )
    elif comerciante is None:
        estado_ar, sev_ar = "NO SE PUEDE AFIRMAR — falta un dato", "media"
        detalle_ar = (
            f"El art. 368-2 exige DOS condiciones concurrentes: tener calidad de "
            f"COMERCIANTE, y superar 30.000 UVT ({_cop(tope_ar)}) de patrimonio o "
            f"ingresos del año anterior. Lo segundo "
            f"{'SÍ se cumple' if supera else 'no se cumple'} con lo cargado; lo "
            f"primero no está en el perfil. Quien presta servicios profesionales "
            f"no es comerciante en el sentido del art. 20 C.Co.; quien vende "
            f"bienes o ejerce actos de comercio, sí. Pon "
            f"`es_comerciante` en [contribuyente] para cerrar este chequeo."
        )
    elif supera:
        estado_ar, sev_ar = "SÍ — revísalo YA con tu contador", "alta"
        detalle_ar = (
            f"Eres comerciante y superas las 30.000 UVT ({_cop(tope_ar)}) de "
            f"patrimonio o ingresos. El art. 368-2 te hace agente de retención: "
            f"tienes que practicar retención, declararla y consignarla mes a mes. "
            f"No declararla tiene sanción propia y responsabilidad por el valor "
            f"dejado de retener (art. 370 ET)."
        )
    else:
        estado_ar, sev_ar = "NO — eres comerciante pero no superas el tope", "info"
        detalle_ar = (
            f"Eres comerciante, pero no superas las 30.000 UVT ({_cop(tope_ar)}) "
            f"de patrimonio ni de ingresos del año anterior. El art. 368-2 exige "
            f"las dos condiciones. Vigílalo: el umbral se mide sobre el año "
            f"ANTERIOR, así que un buen año te vuelve agente de retención al "
            f"siguiente."
        )

    checks.append({
        "id": "OBL-02",
        "titulo": "¿Eras agente de retención en la fuente?",
        "estado": estado_ar,
        "detalle": detalle_ar,
        "severidad": sev_ar,
        "fuente": ar.get("fuente", "ET art. 368-2"),
    })

    # costos sin verificación de aportes
    pagos_contratistas = p.get("costos.pagos_a_contratistas")
    if pagos_contratistas > 0 and not p.get("verificaciones.contratistas_con_pila_verificada"):
        checks.append({
            "id": "R-02",
            "titulo": "Costos por pagos a contratistas sin verificar aportes",
            "estado": "SIN VERIFICAR",
            "detalle": (
                f"Tienes {_cop(pagos_contratistas)} en pagos a contratistas. El "
                f"art. 108 par. 2 ET exige "
                f"verificar la afiliación y el pago de aportes a seguridad social de "
                f"cada contratista. Si no cotizaron, la DIAN puede rechazar la "
                f"totalidad del costo y la Ruta A pierde su fundamento. Pide la "
                f"planilla PILA de cada persona."
            ),
            "severidad": "alta",
            "fuente": "ET art. 108 par. 2",
        })

    return checks


def _chequeos_de_cierre(p: Perfil, par: Parametros,
                        mejor: Liquidacion) -> list[dict]:
    """R-15, R-16 y R-17: las tres cuentas que hace un contador y el motor no.

    Van APARTE de `verificar_obligaciones` y reciben la liquidación ya hecha,
    en vez de liquidar por dentro. `verificar_obligaciones` es una función
    barata sobre el perfil y hay tests que la llaman con un `Parametros`
    recortado a los bloques que ese chequeo necesita; meterle una liquidación
    completa adentro la volvía dependiente de TODO el archivo de parámetros y
    reventaba con un KeyError desde un test que no tenía nada que ver.

    Las tres dependen de datos que el perfil puede no traer, y las tres
    responden «NO SE PUEDE CONCLUIR» en ese caso en vez de suponer. La regla
    ya rige `es_comerciante` en OBL-02: suponer sobre un hecho que nunca se
    vio produce un veredicto con cara de cierto, que es la salida más cara
    que puede dar esta herramienta.
    """
    checks: list[dict] = []

    # ---- R-15 · renta por comparación patrimonial (arts. 236 y 237) ----
    #
    # Es la primera cuenta que la DIAN hace de forma automática, y el motor
    # no la corría. Si el patrimonio líquido creció más de lo que explican
    # las rentas declaradas, la diferencia se GRAVA como renta líquida.
    pl_hoy = p.patrimonio_bruto - p.pasivos
    pl_ayer = p.get("anio_anterior.patrimonio_liquido")
    cp = par.get("comparacion_patrimonial", {})
    if pl_ayer is None:
        checks.append({
            "id": "R-15",
            "titulo": "Comparación patrimonial (arts. 236 y 237) sin evaluar",
            "estado": "NO SE PUEDE CONCLUIR",
            "detalle": (
                f"Falta `anio_anterior.patrimonio_liquido` en el perfil, así "
                f"que no se puede correr la comparación patrimonial. Es la "
                f"primera cuenta automática que hace la DIAN: si tu patrimonio "
                f"líquido creció más de lo que explican las rentas que "
                f"declaraste, la diferencia se grava como renta líquida. Sácalo "
                f"de la casilla de patrimonio líquido de tu declaración del año "
                f"pasado ({p.anio_gravable - 1}); si no declaraste, ponlo en 0 "
                f"y déjalo dicho en el memo."
            ),
            "severidad": "media",
            "fuente": cp.get("fuente", "ET arts. 236 y 237"),
        })
    else:
        incremento = pl_hoy - pl_ayer
        # La fórmula es la del art. 237, no «la renta líquida a secas»:
        #
        #     justificado = renta gravable
        #                 + ganancia ocasional neta   ← fuera de alcance
        #                 + rentas exentas
        #                 − impuestos de renta PAGADOS durante el año
        #
        # Los dos últimos términos van en direcciones opuestas y la primera
        # versión de este chequeo no tenía ninguno: comparaba contra la renta
        # líquida sola, y por tanto acusaba de patrimonio injustificado a
        # quien tiene rentas exentas altas — que es el usuario de la Ruta B,
        # o sea media población objetivo.
        exentas = -sum(r.valor for r in mejor.renglones
                       if r.signo == -1 and "exenta" in r.concepto.lower())
        # Cota de «impuestos pagados durante el año». El perfil no tiene el
        # pago del saldo del año anterior, así que se usan las retenciones,
        # que sí son impuesto de renta pagado en el año. Queda dicho en el
        # detalle: subestimar este término hace que el chequeo avise de MÁS,
        # que en un chequeo de riesgo es el lado correcto del error.
        pagados = p.get("anticipos.retenciones_practicadas")
        justificado = mejor.renta_liquida + exentas - pagados
        sin_justificar = incremento - justificado
        if sin_justificar > 0:
            checks.append({
                "id": "R-15",
                "titulo": "El patrimonio creció más de lo que explican las rentas",
                "estado": f"REVISAR — {_cop(sin_justificar)} sin justificar",
                "detalle": (
                    f"Tu patrimonio líquido pasó de {_cop(pl_ayer)} a "
                    f"{_cop(pl_hoy)}: subió {_cop(incremento)}.\n"
                    f"Contra eso, la suma del art. 237 da {_cop(justificado)}: "
                    f"renta gravable {_cop(mejor.renta_liquida)} + rentas "
                    f"exentas {_cop(exentas)} − impuestos de renta pagados en "
                    f"el año {_cop(pagados)}. Quedan {_cop(sin_justificar)} sin "
                    f"explicar.\n"
                    f"⚠ Como «impuestos pagados» el motor solo puede ver tus "
                    f"retenciones. Si además pagaste el saldo de la "
                    f"declaración anterior, ese pago también resta y la "
                    f"diferencia sin justificar es MAYOR que la de arriba. Y "
                    f"la ganancia ocasional neta, que suma, está fuera del "
                    f"alcance de este motor.\n"
                    f"El art. 236 grava esa diferencia como renta líquida SALVO "
                    f"que demuestres una causa justificativa. Las que suelen "
                    f"serlo y este motor no ve: valorizaciones nominales de "
                    f"inmuebles (art. 237), herencias y donaciones —que van a "
                    f"ganancia ocasional, fuera del alcance de este motor—, "
                    f"préstamos recibidos (suben el activo y el pasivo a la "
                    f"vez), y los INCRNGO que ya restaste arriba.\n"
                    f"Si no encuentras una, la diferencia es ingreso no "
                    f"declarado y hay que declararlo. Reconstruye el patrimonio "
                    f"activo por activo con tu contador antes de presentar."
                ),
                "severidad": "alta",
                "fuente": cp.get("fuente", "ET arts. 236 y 237"),
            })
        else:
            checks.append({
                "id": "R-15",
                "titulo": "Comparación patrimonial",
                "estado": "CUADRA",
                "detalle": (
                    f"El patrimonio líquido subió {_cop(incremento)} y la suma "
                    f"del art. 237 —renta gravable {_cop(mejor.renta_liquida)} "
                    f"+ rentas exentas {_cop(exentas)} − impuestos pagados "
                    f"{_cop(pagados)}— da {_cop(justificado)}: el incremento "
                    f"está explicado. No hay renta por comparación patrimonial."
                ),
                "severidad": "info",
                "fuente": cp.get("fuente", "ET arts. 236 y 237"),
            })

    # ---- R-16 · beneficio de auditoría (art. 689-3) ----
    #
    # La palanca de planeación más grande que existe para este perfil, y el
    # repo no la mencionaba ni una vez: baja la firmeza de 36 meses a 6.
    ba = par.get("firmeza.beneficio_de_auditoria", {}) or {}
    anios = ba.get("anios_gravables") or []
    prorroga = par.get("firmeza.beneficio_de_auditoria.prorroga", {}) or {}
    anios = sorted(set(anios) | set(prorroga.get("anios") or []))
    neto_ayer = p.get("anio_anterior.impuesto_neto")
    piso = par.cop(ba.get("piso_impuesto_neto_uvt", 71))
    if p.anio_gravable not in anios:
        pass                                    # sin prórroga vigente, no aplica
    elif neto_ayer is None:
        checks.append({
            "id": "R-16",
            "titulo": "Beneficio de auditoría (art. 689-3) sin evaluar",
            "estado": "NO SE PUEDE CONCLUIR",
            "detalle": (
                f"Falta `anio_anterior.impuesto_neto` en el perfil. Con ese "
                f"dato el motor te dice si te conviene el beneficio de "
                f"auditoría: subiendo el impuesto neto un 35% frente al año "
                f"anterior, la declaración queda EN FIRME a los 6 meses en vez "
                f"de a los 36; con un 25%, a los 12 meses. Para un "
                f"independiente con ingresos creciendo suele estar al alcance "
                f"sin hacer nada distinto. Sácalo de la casilla «Impuesto neto "
                f"de renta» de tu declaración de {p.anio_gravable - 1}."
            ),
            "severidad": "media",
            "fuente": ba.get("fuente", "ET art. 689-3"),
        })
    elif neto_ayer < piso:
        checks.append({
            "id": "R-16",
            "titulo": "Beneficio de auditoría (art. 689-3)",
            "estado": "NO APLICA — el año anterior no llega al piso",
            "detalle": (
                f"El par. 2 del art. 689-3 lo excluye cuando el impuesto neto "
                f"del año contra el cual se compara es inferior a "
                f"{ba.get('piso_impuesto_neto_uvt', 71)} UVT ({_cop(piso)}). El "
                f"tuyo de {p.anio_gravable - 1} fue {_cop(neto_ayer)}. Tu "
                f"declaración queda en firme por la regla general del art. 714: "
                f"{par.get('firmeza.general.meses', 36)} meses."
            ),
            "severidad": "info",
            "fuente": ba.get("fuente", "ET art. 689-3"),
        })
    else:
        p35 = ba.get("incremento_firmeza_6_meses", 0.35)
        p25 = ba.get("incremento_firmeza_12_meses", 0.25)
        meta35, meta25 = neto_ayer * (1 + p35), neto_ayer * (1 + p25)
        neto = mejor.impuesto_neto
        if neto >= meta35:
            estado = "SÍ — firmeza en 6 meses, ya lo cumples"
            faltante = ""
        elif neto >= meta25:
            estado = "SÍ — firmeza en 12 meses"
            faltante = (f" Te faltan {_cop(meta35 - neto)} de impuesto neto "
                        f"para bajarla a 6 meses.")
        else:
            estado = "NO con el cálculo actual"
            faltante = (f" Te faltan {_cop(meta25 - neto)} para los 12 meses y "
                        f"{_cop(meta35 - neto)} para los 6.")
        checks.append({
            "id": "R-16",
            "titulo": "Beneficio de auditoría (art. 689-3)",
            "estado": estado,
            "detalle": (
                f"Tu impuesto neto de {p.anio_gravable} es {_cop(neto)} y el de "
                f"{p.anio_gravable - 1} fue {_cop(neto_ayer)}. Los umbrales son "
                f"{_cop(meta25)} (+{p25:.0%} → firmeza en 12 meses) y "
                f"{_cop(meta35)} (+{p35:.0%} → firmeza en 6 meses).{faltante}\n"
                f"⚠ Tres condiciones que se pierden al resumir y que muerden "
                f"acá: (1) presentación oportuna y PAGO TOTAL dentro del plazo "
                f"—un día tarde o pagar en cuotas y el beneficio se cae "
                f"entero—; (2) si la declaración arroja pérdida fiscal la DIAN "
                f"conserva la facultad de fiscalizarla aunque corra el término; "
                f"(3) no procede si se demuestra que las retenciones "
                f"declaradas son inexistentes — otra razón para conciliar la "
                f"exógena (R-17).\n"
                f"Renunciar a una deducción para alcanzar el umbral es una "
                f"decisión legítima de planeación, pero es un cambio de "
                f"posición: consúltalo con tu contador."
            ),
            "severidad": "info",
            "fuente": ba.get("fuente", "ET art. 689-3"),
        })

    # ---- R-17 · conciliación contra la información exógena ----
    if not p.get("verificaciones.exogena_descargada_y_conciliada"):
        checks.append({
            "id": "R-17",
            "titulo": "No has conciliado contra la información exógena",
            "estado": "PENDIENTE",
            "detalle": (
                "La exógena es lo que la DIAN YA SABE de ti antes de que "
                "declares: tus clientes, bancos y plataformas reportaron lo "
                "que te pagaron y lo que te retuvieron, y de ahí sale la "
                "declaración sugerida del Muisca.\n"
                "Un ingreso que un tercero reportó y tú no declaraste es una "
                "diferencia que la DIAN ve sin fiscalizar a nadie. Y una "
                "retención que tú declaras y nadie reportó es la causal "
                "expresa del art. 689-3 para perder el beneficio de auditoría.\n"
                "Descárgala del portal (Consulta de información exógena "
                "reportada por terceros), concíliala contra tu ledger con "
                "`templates/conciliacion-exogena.md`, y marca "
                "`verificaciones.exogena_descargada_y_conciliada = true`. Es la "
                "primera parada de cualquier contador y va ANTES de calcular, "
                "no después."
            ),
            "severidad": "alta",
            "fuente": par.get("exogena.fuente", "ET arts. 631 y 631-3"),
        })
    return checks


# ---------------------------------------------------------------------
# Comparación completa
# ---------------------------------------------------------------------

def renglones_al_210(L: Liquidacion, par: Parametros) -> list[tuple[str, int]]:
    """Las cifras que se transcriben al formulario, aproximadas al art. 577.

    Solo las que van a una casilla. El resto de la depuración es la
    trazabilidad de cómo se llegó a estas, y va al peso.

    EL REDONDEO SE ENCADENA, y ése es el arreglo
    ────────────────────────────────────────────
    La versión anterior aproximaba cada casilla POR SEPARADO desde la cifra
    al peso del motor. El resultado era que las cuatro casillas no cuadraban
    ENTRE SÍ: quien transcribiera la base al 210 y liquidara sobre ella —que
    es lo que hace el formulario, y lo que hace el validador de la DIAN—
    obtenía un impuesto distinto del que el motor le imprimía al lado.

    Medido sobre las 20 personas del benchmark: 3 de 40 liquidaciones
    discrepaban en $1.000. Poco dinero y mucho problema, porque es
    exactamente la clase de descuadre que un validador rechaza y que el
    contribuyente no sabe explicar.

    Acá el cálculo va HACIA ADELANTE desde la base ya aproximada, en el
    mismo orden en que el formulario lo hace:

        base_210      = aproximar(renta líquida)
        impuesto_210  = aproximar(art. 241 sobre base_210)      ← sobre la
                                                                  base YA
                                                                  aproximada
        neto_210      = impuesto_210 − descuentos_210
        saldo_210     = neto_210 − anticipos_210

    Así las casillas se reproducen unas de otras con la aritmética impresa
    en el propio formulario, que es la única especificación de este cálculo
    publicada por la autoridad. `benchmark/formulario210.py` la comprueba.
    """
    base = aproximar_577(L.renta_liquida)
    impuesto = aproximar_577(impuesto_241(base, par))
    # Descuentos y anticipos se derivan de la liquidación al peso y se
    # aproximan una sola vez; de ahí en adelante todo es aritmética entera
    # entre casillas, que es lo que el formulario permite verificar.
    descuentos = aproximar_577(L.impuesto - L.impuesto_neto)
    anticipos = aproximar_577(L.impuesto_neto - L.saldo)
    neto = max(impuesto - descuentos, 0)
    saldo = neto - anticipos
    return [
        ("Renta líquida gravable", base),
        ("Impuesto sobre la renta líquida", impuesto),
        ("Descuentos tributarios", descuentos),
        ("Impuesto neto de renta", neto),
        ("Anticipos y retenciones", anticipos),
        ("Saldo a pagar" if saldo >= 0 else "Saldo a favor", abs(saldo)),
    ]


def comparar(p: Perfil, par: Parametros) -> dict:
    a = liquidar(p, par, "A")
    b = liquidar(p, par, "B")
    mejor = "A" if a.saldo <= b.saldo else "B"

    return {
        "anio_gravable": p.anio_gravable,
        "uvt": par.uvt,
        "rutas": {"A": a, "B": b},
        "mejor_ruta": mejor,
        "diferencia_entre_rutas": abs(a.saldo - b.saldo),
        "sensibilidad": sensibilidad(p, par),
        "verificaciones": (verificar_obligaciones(p, par)
                           + _chequeos_de_cierre(
                               p, par, a if mejor == "A" else b)),
        "patrimonio_bruto": p.patrimonio_bruto,
        "pasivos": p.pasivos,
        "patrimonio_liquido": p.patrimonio_bruto - p.pasivos,
        "tarifa_marginal": tarifa_marginal(
            (a if mejor == "A" else b).renta_liquida, par
        ),
        # Lo que el usuario TRANSCRIBE al 210, ya aproximado al múltiplo de
        # mil del art. 577. Lo hacía él de cabeza, contra la regla de que la
        # aritmética la hace el motor.
        "al_formulario_210": renglones_al_210(a if mejor == "A" else b, par),
        "aviso_discontinuidad": aviso_de_discontinuidad(
            (a if mejor == "A" else b).renta_liquida, par
        ),
        "supuestos": p.supuestos,
        "faltantes": p.faltantes,
        "advertencias_parametros": par.advertencias(),
    }


def _cop(x: float) -> str:
    return f"${x:,.0f}".replace(",", ".")
