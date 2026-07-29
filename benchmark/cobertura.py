"""Cobertura del ESPACIO DE ENTRADA — la sexta capa.

Todas las capas anteriores miden si el motor acierta EN LOS CASOS QUE SE LE
DAN. Ninguna mide qué casos no se le dan nunca. Y ahí es donde estaba el
agujero que midió la ronda 7:

    · 14 campos del ESQUEMA no los ejercita ninguna de las 17 personas,
      entre ellos `compras_con_factura_electronica` —la deducción por la que
      escapó la mutación M87—, `es_comerciante` e `incrngo.otros`.
    · El tope conjunto muerde en 3 de 34 liquidaciones.
    · Los dos tramos superiores del art. 241 no se alcanzan nunca.
    · Las zonas de castigo del 241: 0 de 34.
    · `make ejemplo` corre el único perfil que no ejercita ninguna rama cara.

La cobertura de CÓDIGO no ve nada de esto: la línea que aplica el tope se
ejecuta siempre; lo que no pasa nunca es que el tope MUERDA. Un `if` que se
evalúa mil veces y siempre da False está cubierto al 100% y no está probado.

Por eso las regiones se declaran por su SIGNIFICADO TRIBUTARIO —«el tope
conjunto recorta», «la base cae en el tramo del 39%»— y no por líneas.

CÓMO SE AGREGA UNA REGIÓN

  Se agrega a REGIONES con un predicado sobre la liquidación, y el
  benchmark se pone rojo hasta que alguna persona la visite. Ese rojo es el
  punto: obliga a escribir la persona, no a bajar el umbral.

  Si una región es genuinamente inalcanzable, se borra con una explicación
  en el commit. Lo que NO se hace es dejarla en cero: una región declarada y
  vacía es una promesa de cobertura que nadie cumple, que es exactamente el
  estado que esta capa vino a hacer visible.
"""

from __future__ import annotations

from engine.depuracion import liquidar, zonas_de_castigo_241

# Campos del perfil que el benchmark tiene que ejercitar con un valor no
# nulo en alguna persona. No es «todos los del ESQUEMA»: los que están fuera
# de alcance (salario, pensión, ganancia ocasional) tienen sus propias
# guardas y meterlos acá exigiría personas que el motor rechaza a propósito.
CAMPOS_EXIGIDOS = (
    "ingresos.rentas_trabajo_honorarios",
    "ingresos.rentas_capital",
    "ingresos.otras_rentas_no_laborales",
    "incrngo.aportes_obligatorios_salud_pension",
    "incrngo.componente_inflacionario",
    "incrngo.otros",
    "costos.pagos_a_contratistas",
    "costos.comisiones_plataforma",
    "costos.equipo_tecnologico",
    "costos.internet_software",
    "costos.arriendo_oficina",
    "costos.otros",
    "deducciones.gmf_pagado",
    "deducciones.intereses_vivienda",
    "deducciones.medicina_prepagada",
    "deducciones.aportes_voluntarios",
    "deducciones.dependientes",
    # La deducción por la que escapó M87. Valía 0 en las 17 personas.
    "deducciones.compras_con_factura_electronica",
    "descuentos.donaciones_certificadas_rte",
    "anticipos.retenciones_practicadas",
    "anticipos.anticipo_anio_anterior",
)


def _tramo_del_241(L, par) -> int:
    """Índice del rango del art. 241 en que cae la base. −1 si no hay base."""
    if L.renta_liquida <= 0:
        return -1
    base_uvt = L.renta_liquida / par.uvt
    rangos = par.exigir("tarifa.rangos")
    for i, r in enumerate(rangos):
        if r["hasta_uvt"] == 0 or base_uvt <= r["hasta_uvt"]:
            return i
    return len(rangos) - 1


DEP_10 = "− Dependientes (10% renta de trabajo)"
DEP_72 = "− Dependientes (72 UVT c/u — FUERA del tope)"


def _renglon(L, concepto: str) -> float:
    for r in L.renglones:
        if r.concepto == concepto:
            return r.valor
    return 0.0


# Las vías de dependientes se detectan por los RENGLONES y no por el texto de
# `dependientes_via`. Ese texto es prosa para el humano —«10% de la renta de
# trabajo por uno (dentro del tope) + 72 UVT por los otros 3 (fuera)»— y una
# compuerta que dependa de su redacción se apaga sola en cuanto alguien
# mejore la frase. Es el mismo error que ya se cometió con la guarda de citas
# que solo miraba las comillas angulares.
REGIONES = {
    "el tope conjunto RECORTA": lambda L, par: L.rechazado_por_tope > 0,
    "el tope conjunto NO recorta": lambda L, par: L.rechazado_por_tope == 0,
    "hay costos rechazados por tipo de renta": lambda L, par: bool(
        getattr(L, "costos_rechazados_por_tipo", 0)),
    "impuesto cero (tramo del 0%)": lambda L, par: L.impuesto == 0,
    "saldo A FAVOR del contribuyente": lambda L, par: L.saldo < 0,
    "saldo A PAGAR": lambda L, par: L.saldo > 0,
    "vía dependientes: 72 UVT pura": lambda L, par: (
        _renglon(L, DEP_72) > 0 and _renglon(L, DEP_10) == 0),
    "vía dependientes: 10% pura": lambda L, par: (
        _renglon(L, DEP_10) > 0 and _renglon(L, DEP_72) == 0),
    "vía dependientes: MIXTA": lambda L, par: (
        _renglon(L, DEP_10) > 0 and _renglon(L, DEP_72) > 0),
}
# Un tramo del art. 241 por rango: los dos de arriba no se visitaban nunca.
for _i in range(7):
    REGIONES[f"base en el tramo {_i} del art. 241"] = (
        lambda L, par, i=_i: _tramo_del_241(L, par) == i
    )


def _liquidaciones(par, personas, construir):
    for persona in personas:
        p = construir(persona)
        for ruta in ("A", "B"):
            yield persona["id"], ruta, p, liquidar(p, par, ruta)


def correr(par, personas, construir) -> list[str]:
    """Devuelve la lista de huecos. Vacía = todas las regiones visitadas."""
    visitas = {nombre: [] for nombre in REGIONES}
    campos_vistos: set[str] = set()
    liquidaciones = list(_liquidaciones(par, personas, construir))

    for pid, ruta, p, L in liquidaciones:
        for campo in CAMPOS_EXIGIDOS:
            if p.get(campo):
                campos_vistos.add(campo)
        for nombre, predicado in REGIONES.items():
            try:
                if predicado(L, par):
                    visitas[nombre].append(f"{pid}/{ruta}")
            except Exception:                              # noqa: BLE001
                pass

    huecos = []
    for nombre, quienes in sorted(visitas.items()):
        if not quienes:
            huecos.append(
                f"REGIÓN SIN VISITAR: «{nombre}». Ninguna de las "
                f"{len(personas)} personas la alcanza en ninguna de las dos "
                f"rutas, así que el motor nunca se probó ahí."
            )
    for campo in CAMPOS_EXIGIDOS:
        if campo not in campos_vistos:
            huecos.append(
                f"CAMPO SIN EJERCITAR: `{campo}` vale 0 en las "
                f"{len(personas)} personas. La aritmética que lo usa no la "
                f"comprueba nadie — es la clase de la mutación M87, que "
                f"escapó por `compras_con_factura_electronica`."
            )

    # Las zonas de castigo del art. 241 son parte de la salida del motor y
    # ninguna persona caía en una. No es un hueco de prueba sino de
    # DOCUMENTACIÓN: si el motor las anuncia, alguna persona tiene que estar
    # dentro para que el aviso se haya visto funcionar alguna vez.
    zonas = zonas_de_castigo_241(par)
    if zonas:
        dentro = [
            f"{pid}/{ruta}" for pid, ruta, _, L in liquidaciones
            if any(a <= L.renta_liquida <= b for a, b, *_ in zonas)
        ]
        if not dentro:
            huecos.append(
                f"REGIÓN SIN VISITAR: las {len(zonas)} zonas de castigo del "
                f"art. 241. El motor las calcula y las anuncia, y ninguna "
                f"persona cae en una: el aviso nunca se vio funcionar."
            )
    return huecos


def informe(par, personas, construir) -> str:
    """Tabla legible de qué visita qué. Para mirar, no para la compuerta."""
    visitas = {nombre: [] for nombre in REGIONES}
    for pid, ruta, _p, L in _liquidaciones(par, personas, construir):
        for nombre, predicado in REGIONES.items():
            try:
                if predicado(L, par):
                    visitas[nombre].append(f"{pid}/{ruta}")
            except Exception:                              # noqa: BLE001
                pass
    filas = []
    for nombre, quienes in visitas.items():
        marca = "✓" if quienes else "✗"
        muestra = ", ".join(quienes[:4]) + ("…" if len(quienes) > 4 else "")
        filas.append(f"  {marca} {nombre:<42} {len(quienes):>3}  {muestra}")
    return "\n".join(filas)
