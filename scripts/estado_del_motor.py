#!/usr/bin/env python3
"""Genera la sección de ESTADO del README desde los flags de knowledge/.

Por qué se genera y no se escribe
─────────────────────────────────
El escuadrón de producto midió la asimetría número uno de este repositorio:

    El README promete un producto terminado, y el motor confiesa al arrancar
    que hay normas que no implementa correctamente.

Las dos cosas eran ciertas a la vez. `motor_implementa_correctamente = false`
ya salía en el encabezado de `bin/renta calcular` —eso se arregló en la ronda
7— pero quien llega por GitHub lee el README y nunca corre el comando.

Escribir la sección a mano habría reproducido el problema en un mes: es
exactamente lo que le pasó al catálogo de riesgos, que llegó a tener tres
conteos distintos en tres archivos, y al docstring del benchmark, que decía
«cuatro capas» con cinco corriendo. Contar a mano no funciona.

Acá el README se genera del mismo TOML del que sale la advertencia del motor,
y un test comprueba que el bloque commiteado es idéntico al que produce este
script. Cuando alguien arregle una de las dos normas, el README se pone al
día en el mismo commit o el build se cae.

Uso
───
    python3 scripts/estado_del_motor.py            # imprime el bloque
    python3 scripts/estado_del_motor.py --escribir # lo inyecta en README.md
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
README = RAIZ / "README.md"

INICIO = "<!-- ESTADO:INICIO — generado por scripts/estado_del_motor.py, no lo edites a mano -->"
FIN = "<!-- ESTADO:FIN -->"

# Descripción corta de cada bloque marcado. Vive acá y no en el TOML porque
# es texto de PRODUCTO —qué le pasa al usuario— y no la norma. Si aparece un
# bloque nuevo sin entrada, el generador falla en vez de imprimir la ruta
# cruda: un renglón que dice `topes.dependientes_10pct` no le dice nada a
# quien está decidiendo si usar esto.
QUE_SIGNIFICA = {
    "topes.costos_por_tipo_de_renta": (
        "Techo de costos por tipo de renta",
        "El Decreto 1625 art. 1.2.1.20.5 lo exige cuando hay ingresos de MÁS "
        "DE UN tipo de renta de la cédula general, y el motor hace lo "
        "contrario: si hay dos actividades y el perfil no declara "
        "`[costos.atribucion]`, no lo aplica. Con un solo tipo de renta la "
        "norma dice que hay pérdida fiscal declarable, y el motor topa.",
    ),
    "topes.dependientes_10pct": (
        "Deducción del 10% por dependientes (art. 387)",
        "El motor evalúa la vía del 10% y la mezcla también para quien no "
        "tiene rentas laborales. El Consejo de Estado (Auto 21-ene-2025, exp. "
        "28541) sostiene que solo pueden aplicar la del art. 336 num. 3. Es "
        "una posición discutida, y el motor toma la favorable sin decirlo.",
    ),
}


def pendientes(anio: int = 2025) -> list[str]:
    """Rutas de knowledge/ con `motor_implementa_correctamente = false`."""
    with open(RAIZ / "knowledge" / f"ag{anio}" / "parametros.toml", "rb") as f:
        datos = tomllib.load(f)
    encontrados: list[str] = []

    def recorrer(nodo, ruta=""):
        if not isinstance(nodo, dict):
            return
        if nodo.get("motor_implementa_correctamente") is False:
            encontrados.append(ruta)
        for k, v in nodo.items():
            recorrer(v, f"{ruta}.{k}" if ruta else k)

    recorrer(datos)
    return sorted(encontrados)


def bloque(anio: int = 2025) -> str:
    rutas = pendientes(anio)
    lineas = [INICIO, "", "## Estado", ""]

    if not rutas:
        lineas += [
            "El motor implementa todas las normas que documenta en "
            "`knowledge/`. Eso **no** quiere decir que esté verificado por un "
            "contador: quiere decir que no hay ninguna divergencia declarada "
            "entre lo que el repositorio dice de la norma y lo que su código "
            "hace.",
            "",
            "Sigue siendo un borrador para revisar, no una declaración para "
            "presentar. Ver [DISCLAIMER.md](DISCLAIMER.md).",
            "",
            FIN,
        ]
        return "\n".join(lineas)

    lineas += [
        f"**Este motor declara {len(rutas)} norma(s) que NO implementa "
        f"correctamente.** No es una lista de deseos: sale de banderas en "
        f"`knowledge/ag{anio}/parametros.toml`, la misma advertencia que "
        f"imprime `bin/renta calcular` al arrancar, y esta sección se genera "
        f"de ahí — no se escribe a mano.",
        "",
    ]
    for ruta in rutas:
        titulo, detalle = QUE_SIGNIFICA.get(ruta, (None, None))
        if titulo is None:
            raise SystemExit(
                f"El bloque `{ruta}` está marcado como no implementado y no "
                f"tiene entrada en QUE_SIGNIFICA de {Path(__file__).name}. "
                f"Escribe qué le pasa AL USUARIO, no la ruta del TOML: un "
                f"renglón que dice «{ruta}» no le sirve a quien está "
                f"decidiendo si usar esto."
            )
        lineas += [f"- **{titulo}** — {detalle}", ""]

    lineas += [
        "Los dos renglones afectados salen marcados en la salida del motor. "
        "Mientras las banderas sigan en `false`, **esos renglones no sirven "
        "para una declaración real sin contador**.",
        "",
        "### Para qué SÍ sirve hoy",
        "",
        "Como **auditor de segunda opinión**: verificar que una declaración "
        "ya preparada incluye las deducciones que te corresponden, y que la "
        "conversión de cada ingreso en moneda extranjera usa la TRM oficial "
        "de su fecha. El camino de extracto a renglón del 210 es auditable "
        "línea por línea y tu contador lo puede objetar donde quiera.",
        "",
        "No como preparador que reemplace a un contador. Ver "
        "[DISCLAIMER.md](DISCLAIMER.md).",
        "",
        FIN,
    ]
    return "\n".join(lineas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--escribir", action="store_true",
                    help="inyecta el bloque en README.md entre los marcadores")
    args = ap.parse_args(argv)

    texto = bloque()
    if not args.escribir:
        print(texto)
        return 0

    readme = README.read_text(encoding="utf-8")
    if INICIO not in readme or FIN not in readme:
        raise SystemExit(
            f"README.md no tiene los marcadores. Pon esto donde quieras la "
            f"sección:\n\n{INICIO}\n{FIN}\n"
        )
    antes = readme.split(INICIO)[0]
    despues = readme.split(FIN, 1)[1]
    README.write_text(antes + texto + despues, encoding="utf-8")
    print("✓ README.md actualizado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
