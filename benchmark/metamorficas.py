"""Relaciones metamórficas — la quinta capa del benchmark.

Las otras cuatro capas comprueban NÚMEROS. Ésta comprueba RELACIONES entre
dos corridas del motor, y esa diferencia es la razón de que exista.

    Una relación metamórfica no pregunta «¿cuánto da?». Pregunta «si cambio
    esta entrada así, ¿cómo TIENE que moverse la salida?». La respuesta sale
    del Estatuto, no de ninguna implementación — así que sobrevive a que el
    motor y `referencia.py` compartan el mismo malentendido.

Ese es exactamente el punto ciego que diagnosticó la ronda 7:

    El diferencial corrió 80.000 perfiles contra la referencia y dio CERO
    divergencias con las dos implementaciones equivocadas, porque la
    referencia reimplementa la misma lectura de la norma. La independencia
    era aritmética, no de criterio. Es el resultado de Knight y Leveson
    (1986) sobre programación multiversión, reproducido dos veces en este
    repositorio.

La técnica está establecida para software fiscal: Rakha et al. (ICSE-SEIS
2023) extraen relaciones metamórficas de las publicaciones del IRS —leídas
con abogados, no del código— y encuentran defectos en software tributario
open source. El trabajo de seguimiento documenta el límite que acá importa:
una implementación con tarifa plana satisface la monotonía, así que la
monotonía sola no basta y hacen falta relaciones estructurales como la
homogeneidad en UVT.

    https://arxiv.org/abs/2205.04998
    https://arxiv.org/html/2509.13471

CÓMO SE ESCRIBE UNA RELACIÓN ACÁ

  1. Sale de un artículo. Si no puedes nombrar la norma que la obliga, no es
     una relación metamórfica: es una creencia sobre el código.
  2. Va sobre `renta_liquida`, no sobre `impuesto`, salvo que sepas lo que
     haces. El impuesto NO es monótono: la tabla del art. 241 tiene dos
     discontinuidades reales donde un peso más de base baja el impuesto, y
     el motor las detecta a propósito (`zonas_de_castigo_241`). Una relación
     de monotonía sobre el impuesto reporta la norma como si fuera un bug.
  3. El contraejemplo se imprime como un `perfil.toml` pegable. Un fallo que
     no se puede reproducir con `bin/renta calcular` no sirve de nada.

QUÉ ENCONTRÓ ESTA CAPA EL DÍA QUE SE ESCRIBIÓ

MR-BASE atrapó, en la primera corrida, que `min(opciones, key=impuesto)`
resolvía los empates por el ORDEN DE LA LISTA. Con el impuesto en cero —o
sea con la base bajo 1.090 UVT, que es media población objetivo— ganaba la
vía de 72 UVT pura por estar escrita primero, aunque dejara una base MAYOR.
Deducir un millón más subía la base declarada en $4.414.472, y esa base es
la que `renglones_al_210()` manda transcribir a la casilla. Ninguna de las
cuatro capas podía verlo: la referencia tenía los escenarios en el mismo
orden, ninguna ancla toca dependientes en el tramo del 0%, y no era una
mutación sino el código original.
"""

from __future__ import annotations

import random

from engine import perfil as PF
from engine.depuracion import liquidar

# Semilla fija: el proyecto promete determinismo y esta capa no lo puede
# romper. Se sube SOLO cuando está verde, y subirla es una decisión visible
# en el diff — igual que regenerar el inventario de privacidad.
#
# Va con guiones bajos, y no como ocho dígitos corridos, porque esa forma es
# exactamente la de una cédula: el escáner de privacidad la reportaba como
# dato personal de confianza ALTA y rompía el build.
#
# La primera versión de este comentario transcribía la semilla mala para
# explicar el problema, y volvió a romper el build por la misma razón. Van
# seis veces en este proyecto que un artefacto dispara al detector que el
# propio proyecto escribió — dos de ellas en el texto que explicaba el
# arreglo. La regla, ya escrita en `test_ninguna_ruta_de_esta_maquina...`:
# **descríbelo, no lo transcribas.**
SEMILLA = 2026_07_29

DEDUCCIONES_DENTRO_DEL_TOPE = (
    "gmf_pagado", "intereses_vivienda", "medicina_prepagada",
    "aportes_voluntarios",
)
CAMPOS_DE_COSTO = (
    "pagos_a_contratistas", "comisiones_plataforma", "equipo_tecnologico",
    "internet_software", "arriendo_oficina", "otros",
)


# ---------------------------------------------------------------------
# Generación por REGIONES
# ---------------------------------------------------------------------
#
# Muestrear uniforme no sirve: la ronda 7 midió que las 17 personas del
# benchmark dejan sin visitar el tramo alto del art. 241, las dos zonas de
# castigo, y `compras_con_factura_electronica` —que es justamente la
# deducción por la que escapó la mutación M87—. Un generador que no apunte a
# las regiones incómodas confirma que todo está bien en las cómodas.

def _perfil(datos: dict) -> PF.Perfil:
    base = {"contribuyente": {"anio_gravable": 2025, "residente_fiscal": True}}
    for clave, valor in datos.items():
        seccion, campo = clave.split(".", 1)
        base.setdefault(seccion, {})[campo] = valor
    completos, supuestos = PF._completar(base)
    return PF.Perfil(completos, None, supuestos)


def generar(rng: random.Random, uvt: int) -> PF.Perfil:
    """Un perfil aleatorio, sesgado hacia donde el motor cambia de rama.

    Los pesos de las opciones no son estéticos: `tramo_cero` y `tope_saturado`
    salen mucho porque son las regiones donde vivían los defectos que las
    otras capas no vieron.
    """
    forma = rng.choice([
        "tramo_cero", "tramo_cero", "tope_saturado", "tope_saturado",
        "dos_actividades", "capital_y_actividad", "tramo_alto", "libre",
    ])

    d: dict = {}
    if forma == "tramo_cero":
        # Base bajo 1.090 UVT: el impuesto da cero y los escenarios empatan.
        d["ingresos.rentas_trabajo_honorarios"] = rng.randrange(20, 75) * 1_000_000
    elif forma == "tramo_alto":
        d["ingresos.rentas_trabajo_honorarios"] = rng.randrange(400, 2_000) * 1_000_000
    elif forma == "dos_actividades":
        d["ingresos.rentas_trabajo_honorarios"] = rng.randrange(30, 200) * 1_000_000
        d["ingresos.otras_rentas_no_laborales"] = rng.randrange(10, 150) * 1_000_000
    elif forma == "capital_y_actividad":
        d["ingresos.rentas_trabajo_honorarios"] = rng.randrange(5, 60) * 1_000_000
        d["ingresos.rentas_capital"] = rng.randrange(50, 500) * 1_000_000
    else:
        d["ingresos.rentas_trabajo_honorarios"] = rng.randrange(60, 400) * 1_000_000

    if forma == "tope_saturado":
        # Los aportes voluntarios son la única palanca que llega al 30% del
        # ingreso, así que es la que satura el tope de 1.340 UVT.
        ingreso = d["ingresos.rentas_trabajo_honorarios"]
        d["deducciones.aportes_voluntarios"] = int(ingreso * rng.uniform(0.20, 0.30))
        d["deducciones.medicina_prepagada"] = 16 * 12 * uvt

    for campo in DEDUCCIONES_DENTRO_DEL_TOPE:
        clave = f"deducciones.{campo}"
        if clave not in d and rng.random() < 0.45:
            d[clave] = rng.randrange(1, 25) * 1_000_000
    # Esta entra aparte y con probabilidad alta: valía 0 en las 17 personas
    # del benchmark, y es la deducción por la que M87 escapó.
    if rng.random() < 0.6:
        d["deducciones.compras_con_factura_electronica"] = rng.randrange(1, 300) * 1_000_000
    d["deducciones.dependientes"] = rng.randrange(0, 6)

    for campo in CAMPOS_DE_COSTO:
        if rng.random() < 0.35:
            d[f"costos.{campo}"] = rng.randrange(1, 60) * 1_000_000

    if rng.random() < 0.5:
        d["incrngo.aportes_obligatorios_salud_pension"] = rng.randrange(1, 40) * 1_000_000
    if rng.random() < 0.25:
        d["incrngo.componente_inflacionario"] = rng.randrange(1, 10) * 1_000_000
    if rng.random() < 0.3:
        d["anticipos.retenciones_practicadas"] = rng.randrange(1, 30) * 1_000_000

    return _perfil(d)


def _como_toml(p: PF.Perfil) -> str:
    """El contraejemplo, pegable en un `perfil.toml`. Un fallo que no se
    puede reproducir con `bin/renta calcular` no sirve de nada."""
    lineas = []
    for seccion in ("ingresos", "incrngo", "costos", "deducciones", "anticipos"):
        campos = {k: v for k, v in p.datos.get(seccion, {}).items()
                  if isinstance(v, (int, float)) and v}
        if not campos:
            continue
        lineas.append(f"[{seccion}]")
        lineas += [f"{k} = {int(v):_}" for k, v in sorted(campos.items())]
        lineas.append("")
    return "\n".join(lineas)


# ---------------------------------------------------------------------
# Las relaciones
# ---------------------------------------------------------------------

def _mr_mas_deduccion_no_sube_la_base(p, par, rng):
    """Toda deducción RESTA.

    Arts. 115, 119, 126-1, 126-4, 336 num. 3 y 387. No existe una lectura de
    la norma en la que SOLICITAR MÁS deducción deje una base gravable mayor.
    Va sobre la base y no sobre el impuesto a propósito: el impuesto no es
    monótono por las discontinuidades del art. 241.

    Ésta es la que encontró el desempate por orden de lista.
    """
    campo = rng.choice(DEDUCCIONES_DENTRO_DEL_TOPE + ("compras_con_factura_electronica",))
    actual = p.get(f"deducciones.{campo}")
    p2 = p.copia_con(**{f"deducciones__{campo}": actual + 2_000_000})
    for ruta in ("A", "B"):
        a, b = liquidar(p, par, ruta), liquidar(p2, par, ruta)
        if b.renta_liquida > a.renta_liquida + 1:
            yield (f"ruta {ruta}: +$2.000.000 en {campo} SUBIÓ la base de "
                   f"${a.renta_liquida:,.0f} a ${b.renta_liquida:,.0f}. "
                   f"Vía antes {a.dependientes_via!r}, después "
                   f"{b.dependientes_via!r}")


def _mr_un_dependiente_mas_no_sube_la_base(p, par, rng):
    """Art. 336 num. 3 inciso 2 y art. 387: acreditar un dependiente más
    puede no agregar nada, pero nunca puede dejar una base MAYOR."""
    n = int(p.get("deducciones.dependientes"))
    if n >= 5:
        return
    p2 = p.copia_con(deducciones__dependientes=n + 1)
    for ruta in ("A", "B"):
        a, b = liquidar(p, par, ruta), liquidar(p2, par, ruta)
        if b.renta_liquida > a.renta_liquida + 1:
            yield (f"ruta {ruta}: pasar de {n} a {n + 1} dependientes SUBIÓ la "
                   f"base de ${a.renta_liquida:,.0f} a ${b.renta_liquida:,.0f}")


def _mr_incrngo_domina_a_la_deduccion(p, par, rng):
    """Un peso vale MÁS como INCRNGO que como deducción dentro del tope.

    Arts. 55 y 56: los INCRNGO restan ANTES del tope conjunto del art. 336
    num. 3 y no lo consumen. Una deducción dentro del tope compite contra él.
    Así que mover el mismo monto de la segunda al primero nunca puede dejar
    una base mayor. Es la afirmación que la propia plantilla del perfil le
    hace al usuario: «no los pongas como deducción — les quita valor».

    ⚠ ACOTADA, y la acotación es un hallazgo por sí sola.

    La primera versión de esta relación disparaba, y no por un bug del
    desempate sino por una interacción real: el techo de costos por tipo de
    renta se calcula como «ingresos del tipo − INCRNGO del tipo», así que
    meter un peso más al INCRNGO de las rentas de trabajo BAJA en un peso el
    techo de los costos de trabajo. Con el techo mordiendo, ese peso se
    pierde como costo y la base sube.

    O sea que la afirmación de la plantilla —«el INCRNGO siempre vale más»—
    deja de ser cierta en cuanto el techo por tipo muerde. Eso hay que
    decírselo al usuario y hoy nadie se lo dice; está en el HANDOFF.

    La relación se limita entonces a los casos donde el techo NO recorta,
    que es donde la afirmación sí se sostiene. Acotar una relación
    metamórfica es legítimo; acotarla sin decir por qué es esconder el caso
    que la rompe.
    """
    campo = rng.choice(DEDUCCIONES_DENTRO_DEL_TOPE)
    monto = p.get(f"deducciones.{campo}")
    if not monto:
        return
    incr = p.get("incrngo.aportes_obligatorios_salud_pension")
    p2 = p.copia_con(**{f"deducciones__{campo}": 0,
                        "incrngo__aportes_obligatorios_salud_pension": incr + monto})
    for ruta in ("A", "B"):
        a, b = liquidar(p, par, ruta), liquidar(p2, par, ruta)
        if a.costos_rechazados_por_tipo or b.costos_rechazados_por_tipo:
            continue
        if b.renta_liquida > a.renta_liquida + 1:
            yield (f"ruta {ruta}: mover ${monto:,.0f} de {campo} a INCRNGO "
                   f"SUBIÓ la base de ${a.renta_liquida:,.0f} a "
                   f"${b.renta_liquida:,.0f}")


def _mr_partir_un_costo_no_cambia_nada(p, par, rng):
    """El Decreto 1625 art. 1.2.1.20.5 topa los costos por TIPO DE RENTA, no
    por campo del perfil. Repartir el mismo costo entre dos campos que van al
    mismo tipo tiene que dar exactamente el mismo resultado.

    Sin esta relación, un techo aplicado por campo en vez de por tipo pasa
    inadvertido: los totales cuadran.
    """
    origen = rng.choice(CAMPOS_DE_COSTO)
    monto = p.get(f"costos.{origen}")
    if monto < 2:
        return
    destino = rng.choice([c for c in CAMPOS_DE_COSTO if c != origen])
    mitad = monto // 2
    p2 = p.copia_con(**{f"costos__{origen}": monto - mitad,
                        f"costos__{destino}": p.get(f"costos.{destino}") + mitad})
    for ruta in ("A", "B"):
        a, b = liquidar(p, par, ruta), liquidar(p2, par, ruta)
        if abs(a.renta_liquida - b.renta_liquida) > 1:
            yield (f"ruta {ruta}: partir ${monto:,.0f} de {origen} entre "
                   f"{origen} y {destino} cambió la base de "
                   f"${a.renta_liquida:,.0f} a ${b.renta_liquida:,.0f}")


def _mr_los_subtotales_particionan(p, par, rng):
    """Cada deducción va a UN lado del tope conjunto: ni a ninguno ni a los
    dos. Art. 336 num. 3.

    Es la CLASE de la mutación M87, que escapó teniendo test dedicado porque
    el test comprobaba «voltear el flag cambia el impuesto» y eso seguía
    siendo cierto con el 1% de factura electrónica contado a los dos lados.
    Acá corre sobre miles de perfiles en vez de sobre uno.
    """
    sueltos = (
        "− GMF deducible (50% del 4x1000 pagado)",
        "− Intereses de vivienda",
        "− Medicina prepagada",
        "− Aportes voluntarios AFP / AFC",
        "− Dependientes (10% renta de trabajo)",
        "− Dependientes (72 UVT c/u — FUERA del tope)",
        "− Deducción 1% compras con factura electrónica",
    )
    for ruta in ("A", "B"):
        v = {r.concepto: r.valor for r in liquidar(p, par, ruta).renglones}
        dentro = v["  = Subtotal deducciones dentro del tope"]
        fuera = v["  = Subtotal deducciones fuera del tope"]
        if dentro + fuera != sum(v[c] for c in sueltos):
            yield (f"ruta {ruta}: los subtotales suman "
                   f"${dentro + fuera:,.0f} y los renglones sueltos "
                   f"${sum(v[c] for c in sueltos):,.0f}")


def _mr_impuesto_nunca_supera_la_base(p, par, rng):
    """La tarifa marginal máxima del art. 241 es 39%. El impuesto no puede
    superar la renta líquida gravable, ni ser negativo."""
    for ruta in ("A", "B"):
        L = liquidar(p, par, ruta)
        if L.impuesto < 0 or L.renta_liquida < 0:
            yield f"ruta {ruta}: cifra negativa (imp {L.impuesto}, RLG {L.renta_liquida})"
        elif L.impuesto > L.renta_liquida:
            yield (f"ruta {ruta}: impuesto ${L.impuesto:,.0f} > base "
                   f"${L.renta_liquida:,.0f}")


RELACIONES = [
    ("más deducción nunca sube la base", _mr_mas_deduccion_no_sube_la_base),
    ("un dependiente más nunca sube la base", _mr_un_dependiente_mas_no_sube_la_base),
    ("el INCRNGO domina a la deducción", _mr_incrngo_domina_a_la_deduccion),
    ("partir un costo no cambia el resultado", _mr_partir_un_costo_no_cambia_nada),
    ("los subtotales particionan el tope", _mr_los_subtotales_particionan),
    ("el impuesto no supera la base", _mr_impuesto_nunca_supera_la_base),
]


def correr(par, casos: int = 1500, semilla: int | None = None) -> list[str]:
    """Devuelve la lista de violaciones. Vacía = la capa está verde."""
    rng = random.Random(SEMILLA if semilla is None else semilla)
    fallos: list[str] = []
    for i in range(casos):
        p = generar(rng, par.uvt)
        for etiqueta, relacion in RELACIONES:
            try:
                for detalle in relacion(p, par, rng):
                    fallos.append(
                        f"[{etiqueta}] caso {i}\n"
                        f"    {detalle}\n"
                        f"    perfil para reproducir:\n"
                        + "\n".join(f"      {l}" for l in _como_toml(p).splitlines())
                    )
            except Exception as e:                      # noqa: BLE001
                fallos.append(f"[{etiqueta}] caso {i} reventó: {e!r}\n{_como_toml(p)}")
            if len(fallos) >= 5:
                return fallos
    return fallos
