#!/usr/bin/env python3
"""Benchmark de renta-co.

Siete capas de verificación, de la más débil a la más fuerte. El conteo del
cierre se DERIVA de la tupla `CAPAS`, no está escrito a mano: este mismo
docstring decía «cuatro capas» con cinco corriendo, que es la clase de
desfase que ya le costó al catálogo de riesgos tres conteos distintos en
tres archivos.

  1. INVARIANTES   — propiedades que deben cumplirse siempre, sobre todas las
                     personas y sobre un barrido de miles de bases gravables.
  2. DIFERENCIAL   — el motor contra `benchmark/referencia.py`, una segunda
                     implementación escrita por separado desde la norma. Si
                     divergen, uno de los dos está mal.
  3. ANCLAS        — valores calculados a mano con el Estatuto en la mano.
                     Atrapan el caso en que ambas implementaciones se
                     equivocan igual.
  4. FRONTERAS     — los bordes de cada rango del art. 241. La tabla tiene
                     saltos por el redondeo que la propia norma ordena, y un
                     salto anómalo delata un `adicional_uvt` mal transcrito
                     que las tres capas anteriores no ven: cada una por
                     separado da un número consistente.
  5. METAMÓRFICAS  — relaciones entre DOS corridas, derivadas de la norma y
                     no de ninguna implementación. Es la única que sobrevive
                     a que el motor y la referencia compartan el mismo
                     malentendido, que fue el veredicto de la ronda 7:
                     80.000 perfiles diferenciales, cero divergencias, las
                     dos implementaciones equivocadas.
  6. COBERTURA     — qué regiones del espacio de ENTRADA no visita nadie. Las
                     cinco anteriores miden si el motor acierta en los casos
                     que se le dan; ésta mide cuáles no se le dan nunca. La
                     cobertura de línea no lo ve: el `if` del tope se ejecuta
                     siempre, lo que no pasaba nunca es que el tope MORDIERA.
  7. GOLDEN MASTER — el motor de hoy contra el motor de ayer, congelado en
                     `benchmark/golden.json`. Es la única que no pregunta
                     «¿esto está bien?» sino «¿esto cambió, y alguien lo
                     decidió?». Las dos peores regresiones de la ronda 7 las
                     introdujo la sesión que estaba arreglando el repo y
                     pasaron todas las capas de entonces, porque ninguna
                     comparaba contra el motor de ayer.

    python -m benchmark.correr
    python -m benchmark.correr --verbose

Código de salida 1 si algo falla.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark import cobertura, golden, metamorficas, referencia
from benchmark.personas import ANCLAS, PERSONAS
from engine import parametros as P
from engine import perfil as PF
from engine.depuracion import comparar, impuesto_241, liquidar

ANCHO = 88


def cop(x) -> str:
    return f"${x:,.0f}".replace(",", ".")


def linea(c="─"):
    print(c * ANCHO)


def titulo(t):
    print()
    linea("═")
    print(t)
    linea("═")


def via_dependientes(L) -> str:
    """La vía de dependientes que eligió el motor, en el vocabulario de la
    referencia.

    Vive en UN solo sitio a propósito: estaba copiada en `diferencial` y en
    `anclas`, y al aparecer la vía mixta se actualizó una y no la otra. El
    diferencial quedó verde y las anclas rojas por la misma liquidación.

    El orden importa: la vía mixta trae las DOS cadenas, así que hay que
    preguntar por ella primero o se confunde con la de 72.
    """
    tiene_10 = "10%" in L.dependientes_via
    tiene_72 = "72 UVT" in L.dependientes_via
    if tiene_10 and tiene_72:
        return "mixto"
    if tiene_72:
        return "72"
    return "10" if tiene_10 else "sin"


def construir_perfil(persona: dict) -> PF.Perfil:
    """Convierte las llaves con punto en el diccionario anidado del perfil."""
    datos: dict = {"contribuyente": {"anio_gravable": 2025, "residente_fiscal": True}}
    for clave, valor in persona["datos"].items():
        seccion, campo = clave.split(".", 1)
        datos.setdefault(seccion, {})[campo] = valor
    if persona.get("patrimonio") or persona.get("pasivos"):
        datos["patrimonio"] = {
            "activos": [{"nombre": n, "valor": v}
                        for n, v in persona.get("patrimonio", [])],
            "pasivos": [{"nombre": n, "valor": v}
                        for n, v in persona.get("pasivos", [])],
        }
    completos, supuestos = PF._completar(datos)
    return PF.Perfil(completos, None, supuestos)


# ---------------------------------------------------------------------
# Capa 1 — invariantes
# ---------------------------------------------------------------------

def invariantes(par) -> list[str]:
    fallos = []

    # Monotonía y no negatividad sobre un barrido fino de la tarifa.
    #
    # Las fronteras del art. 241 se excluyen a propósito. La tabla del
    # Estatuto redondea los UVT adicionales (116, 788, 2.296, 5.901, 10.352),
    # y ese redondeo produce saltos de unos pocos miles de pesos justo en
    # 1.700, 8.670 y 31.000 UVT: en dos de ellos el impuesto BAJA al subir la
    # base. No es un bug del motor — es la norma, y "corregirlo" sería
    # apartarse de ella. Se verifica aparte, en discontinuidades_del_241(),
    # para que quede documentado y no se confunda con una regresión.
    FRONTERAS = {1_090, 1_700, 4_100, 8_670, 18_970, 31_000}
    anterior = -1
    for uvt in range(0, 40_000, 7):
        imp = impuesto_241(uvt * par.uvt, par)
        if imp < 0:
            fallos.append(f"impuesto negativo en {uvt} UVT: {imp}")
            break
        cerca_de_frontera = any(abs(uvt - f) <= 7 for f in FRONTERAS)
        if imp < anterior and not cerca_de_frontera:
            fallos.append(f"impuesto NO monótono en {uvt} UVT: {imp} < {anterior}")
            break
        anterior = imp

    # La tarifa efectiva nunca puede superar la marginal máxima.
    for uvt in (2_000, 10_000, 50_000, 200_000):
        base = uvt * par.uvt
        efectiva = impuesto_241(base, par) / base
        if efectiva > 0.39:
            fallos.append(f"tarifa efectiva {efectiva:.4f} > 39% en {uvt} UVT")

    # Primer tramo exento.
    if impuesto_241(1_090 * par.uvt, par) != 0:
        fallos.append("el tramo hasta 1.090 UVT no está a tarifa 0%")

    # Por persona.
    for persona in PERSONAS:
        p = construir_perfil(persona)
        pid = persona["id"]
        for ruta in ("A", "B"):
            L = liquidar(p, par, ruta)
            if L.renta_liquida < 0:
                fallos.append(f"{pid}/{ruta}: renta líquida negativa")
            if L.impuesto < 0 or L.impuesto_neto < 0:
                fallos.append(f"{pid}/{ruta}: impuesto negativo")
            if L.impuesto_neto > L.impuesto:
                fallos.append(f"{pid}/{ruta}: impuesto neto > impuesto bruto")
            if L.rechazado_por_tope < -1:
                fallos.append(f"{pid}/{ruta}: rechazado por tope negativo")
            tope_max = min(
                p.ingresos_brutos - p.total_incrngo,
                1_340 * par.uvt,
            )
            if L.tope_conjunto > max(tope_max, 0) + 1:
                fallos.append(f"{pid}/{ruta}: tope conjunto por encima de lo legal")
            if L.impuesto > L.renta_liquida:
                fallos.append(f"{pid}/{ruta}: impuesto mayor que la base gravable")

        # La ruta elegida es la de menor saldo.
        r = comparar(p, par)
        a, b = r["rutas"]["A"].saldo, r["rutas"]["B"].saldo
        if r["mejor_ruta"] == "A" and a > b:
            fallos.append(f"{pid}: eligió A siendo B mejor")
        if r["mejor_ruta"] == "B" and b > a:
            fallos.append(f"{pid}: eligió B siendo A mejor")

        # Las verificaciones de riesgo y los agregados del comparativo NO se
        # aseveraban en ninguna capa: una mutación en verificar_obligaciones,
        # en tarifa_marginal o en el patrimonio pasaba el benchmark entero.
        ids = {v["id"] for v in r["verificaciones"]}
        if "OBL-01" not in ids or "R-01" not in ids:
            fallos.append(f"{pid}: faltan verificaciones básicas (OBL-01/R-01)")
        for v in r["verificaciones"]:
            if v["severidad"] not in ("alta", "media", "info"):
                fallos.append(f"{pid}/{v['id']}: severidad inválida {v['severidad']!r}")
            if not v.get("estado") or not v.get("detalle"):
                fallos.append(f"{pid}/{v['id']}: verificación sin estado o detalle")

        # Tarifa del PRÓXIMO peso, así que el corte va con `<` y no con
        # `<=`: parado exactamente en 1.090 UVT —el techo del tramo del
        # 0%— el siguiente peso ya paga 19%. `impuesto_241` sí usa `<=`,
        # porque responde otra pregunta: en qué tramo cae ESTA base.
        marginal = r["tarifa_marginal"]
        esperada = next(
            (x["tarifa"] for x in par.exigir("tarifa.rangos")
             if x["hasta_uvt"] == 0
             or r["rutas"][r["mejor_ruta"]].renta_liquida / par.uvt < x["hasta_uvt"]),
            None,
        )
        if marginal != esperada:
            fallos.append(f"{pid}: tarifa marginal {marginal} != {esperada}")

        # Contra el PERFIL, no contra el mismo diccionario que produjo la
        # cifra: comparar comparar()["liquido"] con comparar()["bruto"] menos
        # comparar()["pasivos"] es una tautología que no puede fallar.
        activos = sum(a["valor"] for a in p.datos["patrimonio"]["activos"])
        pasivos = sum(x["valor"] for x in p.datos["patrimonio"]["pasivos"])
        if round(r["patrimonio_bruto"]) != round(activos):
            fallos.append(f"{pid}: patrimonio bruto {r['patrimonio_bruto']} != {activos}")
        if round(r["pasivos"]) != round(pasivos):
            fallos.append(f"{pid}: pasivos {r['pasivos']} != {pasivos}")
        if round(r["patrimonio_liquido"]) != round(activos - pasivos):
            fallos.append(f"{pid}: patrimonio líquido no cuadra con el perfil")

        # Los renglones son lo que se copia al formulario: si cambian de
        # etiqueta o de orden, el comparativo deja de ser legible aunque los
        # totales sigan bien.
        for ruta in ("A", "B"):
            L = r["rutas"][ruta]
            if "SALDO" not in L.renglones[-1].concepto:
                fallos.append(f"{pid}/{ruta}: el último renglón no es el saldo")
            if not any("RENTA LÍQUIDA" in x.concepto for x in L.renglones):
                fallos.append(f"{pid}/{ruta}: falta el renglón de renta líquida")
            sin_fuente = [
                x.concepto for x in L.renglones
                if x.concepto.startswith("−") and not x.fuente and x.valor
            ]
            if sin_fuente:
                fallos.append(f"{pid}/{ruta}: renglones sin fuente: {sin_fuente[:2]}")

        # La sensibilidad nunca reporta ahorros no positivos, y viene
        # ordenada DENTRO de cada grupo. El orden entre grupos es
        # deliberado: primero lo que solo exige un papel, después lo que
        # exige desembolsar. Una palanca de $12 M que cuesta $56 M no puede
        # encabezar una lista titulada "cuánto vale cada palanca".
        from engine.depuracion import DESEMBOLSO

        sens = r["sensibilidad"]
        if any(x.ahorro_max <= 0 for x in sens):
            fallos.append(f"{pid}: sensibilidad con ahorro no positivo")

        gratis = [x.ahorro_max for x in sens if x.tipo != DESEMBOLSO]
        if gratis != sorted(gratis, reverse=True):
            fallos.append(f"{pid}: palancas sin desembolso desordenadas")

        tipos = [x.tipo for x in sens]
        primer_desembolso = next(
            (i for i, t in enumerate(tipos) if t == DESEMBOLSO), len(tipos)
        )
        if any(t != DESEMBOLSO for t in tipos[primer_desembolso:]):
            fallos.append(f"{pid}: los desembolsos no quedaron agrupados al final")

    return fallos


# ---------------------------------------------------------------------
# Capa 2 — diferencial contra la implementación de referencia
# ---------------------------------------------------------------------

CAMPOS = [
    ("renta_liquida", "renta_liquida"),
    ("impuesto", "impuesto"),
    ("impuesto_neto", "impuesto_neto"),
    ("saldo", "saldo"),
    ("tope_conjunto", "tope_conjunto"),
    ("rechazado_por_tope", "rechazado"),
]


def diferencial(par, verbose=False) -> list[str]:
    fallos = []
    for persona in PERSONAS:
        p = construir_perfil(persona)
        ref = referencia.comparar(persona["datos"])
        for ruta in ("A", "B"):
            L = liquidar(p, par, ruta)
            R = ref[ruta]
            for attr, clave in CAMPOS:
                mio = round(getattr(L, attr))
                suyo = round(R[clave])
                if abs(mio - suyo) > 1:          # 1 peso de tolerancia por redondeo
                    fallos.append(
                        f"{persona['id']}/{ruta} · {attr}: "
                        f"motor {cop(mio)} vs referencia {cop(suyo)} "
                        f"(dif {cop(mio - suyo)})"
                    )
            via_motor = via_dependientes(L)
            if via_motor != R["via_dependientes"]:
                fallos.append(
                    f"{persona['id']}/{ruta} · vía de dependientes: "
                    f"motor '{via_motor}' vs referencia '{R['via_dependientes']}'"
                )
        r = comparar(p, par)
        if r["mejor_ruta"] != ref["mejor"]:
            fallos.append(
                f"{persona['id']} · mejor ruta: motor {r['mejor_ruta']} "
                f"vs referencia {ref['mejor']}"
            )
    return fallos


# ---------------------------------------------------------------------
# Capa 3 — anclas calculadas a mano
# ---------------------------------------------------------------------

def anclas(par) -> list[str]:
    fallos = []
    por_id = {x["id"]: x for x in PERSONAS}
    for ancla in ANCLAS:
        persona = por_id[ancla["id"]]
        L = liquidar(construir_perfil(persona), par, ancla["ruta"])
        if ancla["campo"] == "via_dependientes":
            obtenido = via_dependientes(L)
        else:
            obtenido = round(getattr(L, ancla["campo"]))
        esperado = ancla["esperado"]
        ok = (obtenido == esperado if isinstance(esperado, str)
              else abs(obtenido - esperado) <= 1)
        if not ok:
            fallos.append(
                f"{ancla['id']}/{ancla['ruta']} · {ancla['campo']}: "
                f"esperado {esperado}, obtenido {obtenido}\n"
                f"      {ancla['razon']}"
            )
    return fallos


# ---------------------------------------------------------------------

def tabla(par):
    print(f"{'ID':<5}{'PERSONA':<34}{'RUTA':>5}{'RENTA LÍQ.':>17}{'SALDO':>17}")
    linea()
    for persona in PERSONAS:
        p = construir_perfil(persona)
        r = comparar(p, par)
        mejor = r["mejor_ruta"]
        L = r["rutas"][mejor]
        signo = "a pagar" if L.saldo >= 0 else "a favor"
        nombre = persona["nombre"][:33]
        print(f"{persona['id']:<5}{nombre:<34}{mejor:>5}"
              f"{cop(L.renta_liquida):>17}{cop(abs(L.saldo)):>17} {signo}")
    linea()


def discontinuidades_del_241(par) -> list[str]:
    """Mide los saltos en las fronteras del art. 241 y verifica que sigan
    dentro de lo que explica el redondeo de la norma.

    Si alguna crece mucho, es señal de que alguien tocó la tabla de tarifas.
    """
    hallazgos = []
    for frontera in (1_090, 1_700, 4_100, 8_670, 18_970, 31_000):
        base = frontera * par.uvt
        antes = impuesto_241(base - 1, par)
        despues = impuesto_241(base + 1, par)
        salto = despues - antes
        if abs(salto) > 6_000:
            hallazgos.append(
                f"salto anómalo de {salto:+,} pesos en {frontera:,} UVT — "
                f"revisa la tabla de tarifas".replace(",", ".")
            )
    return hallazgos


def rendimiento(par) -> float:
    inicio = time.perf_counter()
    for _ in range(20):
        for persona in PERSONAS:
            comparar(construir_perfil(persona), par)
    return (time.perf_counter() - inicio) / (20 * len(PERSONAS)) * 1000


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Benchmark de renta-co")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    par = P.cargar(2025)

    titulo(f"BENCHMARK renta-co · AG2025 · UVT {cop(par.uvt)} · "
           f"{len(PERSONAS)} personas")
    tabla(par)

    resultados = []
    # Las capas van en una lista con nombre para que el conteo del cierre se
    # DERIVE de ella. Estaba escrito «las cuatro capas pasan» a mano, y al
    # agregar la quinta el mensaje habría seguido diciendo cuatro — la misma
    # clase de desfase que el catálogo de riesgos, que llegó a tener tres
    # conteos distintos en tres archivos.
    CAPAS = (
        ("INVARIANTES", lambda: invariantes(par)),
        ("DIFERENCIAL (motor vs. referencia independiente)", lambda: diferencial(par, args.verbose)),
        ("ANCLAS (calculadas a mano con la norma)", lambda: anclas(par)),
        ("FRONTERAS DEL ART. 241 (saltos por redondeo de la norma)",
         lambda: discontinuidades_del_241(par)),
        ("RELACIONES METAMÓRFICAS (derivadas de la norma, no del código)",
         lambda: metamorficas.correr(par)),
        # Las cinco de arriba miden si el motor acierta en los casos que se
        # le dan. Ésta mide qué casos NO se le dan nunca — que es distinto y
        # ninguna cobertura de línea lo ve: el `if` del tope se ejecuta
        # siempre, lo que no pasaba nunca es que el tope MORDIERA.
        ("COBERTURA DEL ESPACIO DE ENTRADA (regiones, no líneas)",
         lambda: cobertura.correr(par, PERSONAS, construir_perfil)),
        # La única capa que no pregunta «¿esto está bien?» sino «¿esto cambió,
        # y alguien lo decidió?». Las dos peores regresiones de la ronda 7 las
        # introdujo la sesión que arreglaba el repo, y pasaron todas las capas
        # de entonces porque ninguna comparaba contra el motor de ayer.
        ("GOLDEN MASTER (el motor de hoy contra el de ayer)",
         lambda: golden.correr(par, PERSONAS, construir_perfil)),
    )
    for etiqueta, fn in CAPAS:
        fallos = fn()
        resultados.append((etiqueta, fallos))
        print()
        if fallos:
            print(f"✗ {etiqueta} — {len(fallos)} fallo(s)")
            for f in fallos:
                print(f"    · {f}")
        else:
            print(f"✓ {etiqueta}")

    # El benchmark solo corría AG2025, así que la herencia de parámetros —y
    # sus validaciones— no se ejercitaban nunca.
    print()
    otros = [a for a in P.anios_disponibles() if a != 2025]
    for anio in otros:
        try:
            p_otro = P.cargar(anio)
            personas_ok = sum(
                1 for persona in PERSONAS
                if comparar(construir_perfil(persona), p_otro)["rutas"]["A"].impuesto >= 0
            )
            print(f"  ✓ AG{anio} carga y liquida las {personas_ok} personas "
                  f"(UVT {cop(p_otro.uvt)}, {len(p_otro.advertencias())} advertencia(s))")
        except Exception as e:
            print(f"  ✗ AG{anio}: {e.__class__.__name__}: {e}")
            resultados.append((f"AG{anio}", [str(e)]))

    ms = rendimiento(par)
    print()
    print(f"  Rendimiento: {ms:.2f} ms por liquidación completa "
          f"(ambas rutas + sensibilidad + verificaciones)")

    total = sum(len(f) for _, f in resultados)
    print()
    linea("═")
    if total:
        print(f"✗ BENCHMARK FALLIDO — {total} problema(s)")
        linea("═")
        return 1
    print(f"✓ BENCHMARK LIMPIO — las {len(CAPAS)} capas pasan")
    linea("═")
    return 0


if __name__ == "__main__":
    sys.exit(main())
