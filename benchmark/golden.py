"""Golden master — el motor de hoy contra el motor de ayer. Séptima capa.

Qué problema resuelve, exactamente
──────────────────────────────────
Las seis capas anteriores comprueban el motor contra una NORMA: invariantes,
una segunda implementación, anclas a mano, fronteras, relaciones, regiones.
Todas responden «¿esto está bien?».

Ésta responde otra pregunta, que ninguna de las otras hace: **«¿esto cambió,
y alguien lo decidió?»**

La diferencia no es teórica. Las dos peores regresiones de la ronda 7 las
introdujo la sesión que estaba arreglando el repo, y las dos pasaron las
capas de entonces:

  · La regla de los tres decimales entró en `parse_monto` y no en el votante
    que decide la convención del archivo. Resultado: factor mil con exit 0,
    donde antes esa fila fallaba ruidosamente. Una alarma convertida en un
    número callado.
  · El desempate por orden de lista en `min(key=impuesto)` movió la base
    declarada en $4.414.472 sin que ninguna capa lo viera.

Un golden master las habría reportado en el commit siguiente, no dos rondas
después: la cifra de alguna persona se movió, y nadie aprobó ese movimiento.

Por qué NO es redundante con las anclas
───────────────────────────────────────
Un ancla afirma «esta cifra vale $X y aquí está la cuenta a mano». Cubre 20
valores escogidos. El golden master no afirma NADA sobre si el valor es
correcto: afirma que no cambió sin permiso, y cubre las ~40 liquidaciones
completas con todos sus renglones. Es cobertura ancha y afirmación débil,
justo al revés que las anclas — por eso se suman en vez de sustituirse.

La regla de uso, y es la que da todo el valor
─────────────────────────────────────────────
**Toda diferencia es un fallo hasta que un humano la aprueba.** Aprobar es
regenerar el archivo:

    python3 -m benchmark.golden --aprobar

y MIRAR EL DIFF antes de commitear, igual que con
`scripts/privacidad-esperado.txt`. Un `--aprobar` reflejo convierte esta capa
en un archivo que se regenera solo, o sea en nada. Si el diff no se puede
explicar en el mensaje del commit, no es una mejora: es una regresión que
todavía no se entiende.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.depuracion import liquidar

ARCHIVO = Path(__file__).resolve().parent / "golden.json"

# Qué se congela de cada liquidación. Los renglones van completos y no solo
# los totales: la ronda 7 midió que dos personas del propio benchmark
# transcribirían un 210 que subdeclara porque un SUBTOTAL —no un total— sale
# antes de aplicar el tope. Un golden de totales no lo habría visto.
CAMPOS = ("renta_liquida", "impuesto", "impuesto_neto", "saldo",
          "tope_conjunto", "rechazado_por_tope", "costos_solicitados",
          "costos_rechazados_por_tipo", "dependientes_via")


def _instantanea(par, personas, construir) -> dict:
    salida: dict = {}
    for persona in personas:
        p = construir(persona)
        for ruta in ("A", "B"):
            L = liquidar(p, par, ruta)
            clave = f"{persona['id']}/{ruta}"
            fila = {}
            for campo in CAMPOS:
                valor = getattr(L, campo, None)
                # Los flotantes se redondean al peso antes de congelarlos: la
                # capa vigila decisiones, no el último bit de un double, y un
                # golden que cambie por ruido de coma flotante se desactiva
                # solo por ruidoso — que es como se apagó el hook de
                # privacidad de este repo.
                fila[campo] = round(valor) if isinstance(valor, float) else valor
            fila["renglones"] = {r.concepto: round(r.valor)
                                 for r in L.renglones
                                 if isinstance(r.valor, (int, float))}
            salida[clave] = fila
    return salida


def escribir(par, personas, construir) -> None:
    ARCHIVO.write_text(
        json.dumps(_instantanea(par, personas, construir),
                   indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def correr(par, personas, construir) -> list[str]:
    """Devuelve las diferencias contra el golden. Vacía = nada cambió."""
    if not ARCHIVO.exists():
        return [
            f"No existe {ARCHIVO.name}. Créalo con "
            f"`python3 -m benchmark.golden --aprobar` y MÍRALO antes de "
            f"commitearlo: es la línea base contra la que se van a comparar "
            f"todos los cambios siguientes."
        ]
    viejo = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    nuevo = _instantanea(par, personas, construir)

    fallos: list[str] = []
    for clave in sorted(set(viejo) | set(nuevo)):
        if clave not in viejo:
            fallos.append(f"{clave}: persona NUEVA, sin línea base. Aprueba "
                          f"para incorporarla.")
            continue
        if clave not in nuevo:
            fallos.append(f"{clave}: DESAPARECIÓ del corpus. Si se borró a "
                          f"propósito, apruébalo; si no, algo se rompió.")
            continue
        a, b = viejo[clave], nuevo[clave]
        for campo in CAMPOS:
            if a.get(campo) != b.get(campo):
                fallos.append(
                    f"{clave}.{campo}: {a.get(campo)!r} → {b.get(campo)!r}"
                )
        ra, rb = a.get("renglones", {}), b.get("renglones", {})
        for concepto in sorted(set(ra) | set(rb)):
            if ra.get(concepto) != rb.get(concepto):
                fallos.append(
                    f"{clave} renglón «{concepto}»: "
                    f"{ra.get(concepto, '—')!r} → {rb.get(concepto, '—')!r}"
                )
    if fallos:
        fallos.append(
            "── Toda diferencia es un fallo hasta que la apruebes. Si el "
            "cambio es correcto, explícalo en el mensaje del commit y corre "
            "`python3 -m benchmark.golden --aprobar`. Si no lo puedes "
            "explicar, no es una mejora: es una regresión que todavía no "
            "entiendes."
        )
    return fallos


def main(argv=None) -> int:
    import argparse
    import sys

    from benchmark.correr import construir_perfil
    from benchmark.personas import PERSONAS
    from engine import parametros as P

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--aprobar", action="store_true",
                    help="regenera la línea base. MIRA EL DIFF antes de commitear.")
    args = ap.parse_args(argv)
    par = P.cargar(2025)

    if args.aprobar:
        escribir(par, PERSONAS, construir_perfil)
        print(f"✓ {ARCHIVO.relative_to(ARCHIVO.parent.parent)} regenerado.")
        print("  Ahora MIRA EL DIFF. Cada línea que cambió es una decisión que")
        print("  estás tomando, y tiene que caber en el mensaje del commit.")
        return 0

    fallos = correr(par, PERSONAS, construir_perfil)
    for f in fallos:
        print(f"  · {f}")
    print()
    print(f"{'✗' if fallos else '✓'} golden master: "
          f"{len(fallos)} diferencia(s)")
    return 1 if fallos else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
