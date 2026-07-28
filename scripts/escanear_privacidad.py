#!/usr/bin/env python3
"""Escáner de datos personales para renta-co.

Busca cédulas, NIT, cuentas, tarjetas, correos, teléfonos, direcciones y
nombres del perfil en archivos de texto. Enmascara todo lo que reporta.

    python scripts/escanear_privacidad.py expediente/04-entregables/
    python scripts/escanear_privacidad.py --perfil expediente/perfil.toml README.md
    python scripts/escanear_privacidad.py --staged        # lo que va a entrar al commit

Código de salida 1 si encuentra algo — sirve como hook de pre-commit.
Sin dependencias externas.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

EXTENSIONES = {".md", ".txt", ".csv", ".toml", ".json", ".yaml", ".yml",
               ".py", ".js", ".ts", ".html", ".sql", ".ini", ".cfg", ""}

# Directorios que nunca se escanean
IGNORAR = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}


def luhn(numero: str) -> bool:
    digitos = [int(d) for d in numero if d.isdigit()][::-1]
    total = 0
    for i, d in enumerate(digitos):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0 and len(digitos) >= 13


# Palabras que, cerca de un número, lo convierten en identificador.
CONTEXTO_IDENTIFICADOR = re.compile(
    r"\b(?:c[eé]dula|c\.?c\.?|nit|identificaci[oó]n|documento|pasaporte|"
    r"cuenta|ahorros|corriente|tarjeta|titular|contribuyente|declarante)\b",
    re.IGNORECASE,
)

PATRONES = [
    ("NIT",
     re.compile(r"\b\d{3}[.\s]?\d{3}[.\s]?\d{3}\s?-\s?\d\b"),
     None),
    ("tarjeta",
     re.compile(r"\b(?:\d[ -]?){13,19}\b"),
     lambda m: luhn(m)),
    # Número con separadores de miles. En un expediente tributario esto es
    # casi siempre un MONTO ("90.000.000"), no una cédula, así que solo se
    # reporta si hay una palabra de contexto en la línea o si tiene cuatro o
    # más grupos —una cédula colombiana los tiene, un monto casi nunca—.
    ("cédula",
     re.compile(r"\b\d{1,3}(?:[.\s]\d{3}){2,3}\b"),
     "contexto"),
    # Secuencia larga de dígitos SIN separadores. Un monto en prosa casi
    # siempre lleva separadores; una cédula o un número de cuenta copiados de
    # un sistema no. Se reporta siempre.
    ("cédula o documento",
     re.compile(r"\b\d{8,10}\b"),
     None),
    ("cuenta bancaria",
     re.compile(r"\b\d{9,20}\b"),
     None),
    ("correo",
     re.compile(r"\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
     None),
    ("teléfono",
     re.compile(r"(?:\+?57[\s-]?)?\b3\d{2}[\s-]?\d{3}[\s-]?\d{4}\b"),
     None),
    ("dirección",
     re.compile(r"\b(?:calle|carrera|cra|kra|kr|avenida|av|diagonal|dg|transversal|tv)\.?\s*\d+[\w\s#\-]{0,20}",
                re.IGNORECASE),
     None),
    ("ruta de usuario",
     re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+"),
     None),
]

# Cosas que parecen datos personales y no lo son. Se borran de la línea
# ANTES de aplicar los patrones.
#
# El más importante de esta lista es el de montos: en un expediente
# tributario "$3.585.528" aparece en cada párrafo y tiene exactamente la
# forma de una cédula. Sin esta exclusión el escáner reporta cientos de
# falsos positivos y la gente deja de leerlo, que es peor que no tenerlo.
FALSOS_POSITIVOS = re.compile(
    r"\$\s?\d[\d.,]*"                          # montos en pesos: $3.585.528
    r"|\b\d[\d.,]*\s*(?:UVT|COP|USD|EUR)\b"    # 1.340 UVT, 3800.00 USD
    r"|\b(?:19|20)\d{2}\b"                     # años
    r"|\b\d{4}-\d{2}-\d{2}\b"                  # fechas ISO
    r"|\bUVT\b|\bart\.?\s*\d+|\bnum\.?\s*\d+"  # referencias normativas
    r"|\b(?:1625|2277|000167|000193|000238)\b",  # normas citadas con frecuencia
    re.IGNORECASE,
)

# Archivo opcional con globs a excluir, uno por línea. Sirve para tests con
# cadenas de prueba y para documentación con ejemplos enmascarados.
ARCHIVO_IGNORADOS = ".privacidadignore"


def enmascarar(texto: str) -> str:
    if "@" in texto:
        usuario, _, dominio = texto.partition("@")
        return f"{usuario[:1]}{'*' * max(len(usuario) - 1, 3)}@{dominio}"
    digitos = [c for c in texto if c.isdigit()]
    if len(digitos) <= 4:
        return "X" * len(texto)
    visibles = 3
    salida, vistos = [], 0
    total = len(digitos)
    for c in texto:
        if c.isdigit():
            vistos += 1
            salida.append(c if vistos <= 1 or vistos > total - visibles else "X")
        else:
            salida.append(c)
    return "".join(salida)


def nombres_del_perfil(ruta: Path) -> list[str]:
    """Extrae cadenas del perfil que puedan ser nombres propios."""
    if not ruta or not ruta.exists():
        return []
    with open(ruta, "rb") as f:
        datos = tomllib.load(f)

    nombres: list[str] = []

    def recorrer(nodo):
        if isinstance(nodo, dict):
            for v in nodo.values():
                recorrer(v)
        elif isinstance(nodo, list):
            for v in nodo:
                recorrer(v)
        elif isinstance(nodo, str) and len(nodo) > 3:
            for palabra in nodo.split():
                limpia = palabra.strip(".,;:()\"'")
                if len(limpia) > 3 and limpia[0].isupper() and limpia.isalpha():
                    nombres.append(limpia)

    recorrer(datos)
    return sorted(set(nombres))


def escanear(ruta: Path, nombres: list[str]) -> list[tuple[int, str, str]]:
    try:
        texto = ruta.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return []

    hallazgos = []
    for n, linea in enumerate(texto.splitlines(), start=1):
        limpia = FALSOS_POSITIVOS.sub(" ", linea)
        hay_contexto = bool(CONTEXTO_IDENTIFICADOR.search(linea))
        vistos_en_linea = set()
        for etiqueta, patron, validador in PATRONES:
            for m in patron.finditer(limpia):
                bruto = m.group(0).strip()
                if validador == "contexto":
                    grupos = len(re.split(r"[.\s]", bruto))
                    if not hay_contexto and grupos < 4:
                        continue
                elif validador and not validador(bruto):
                    continue
                clave = (bruto, etiqueta)
                if clave in vistos_en_linea:
                    continue
                vistos_en_linea.add(clave)
                hallazgos.append((n, etiqueta, enmascarar(bruto)))
        for nombre in nombres:
            if re.search(rf"\b{re.escape(nombre)}\b", linea):
                hallazgos.append((n, "nombre del perfil", nombre[0] + "*" * (len(nombre) - 1)))
    return hallazgos


def globs_ignorados(raiz: Path) -> list[str]:
    archivo = raiz / ARCHIVO_IGNORADOS
    if not archivo.exists():
        return []
    return [
        linea.strip()
        for linea in archivo.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    ]


def esta_ignorado(ruta: Path, globs: list[str]) -> bool:
    from fnmatch import fnmatch

    texto = str(ruta).lstrip("./")
    return any(fnmatch(texto, g) or fnmatch(ruta.name, g) for g in globs)


def archivos_de(objetivos: list[str], staged: bool) -> list[Path]:
    if staged:
        try:
            salida = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                capture_output=True, text=True, check=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("✗ No se pudo leer el índice de git.")
            return []
        return [Path(p) for p in salida.split("\n") if p.strip() and Path(p).exists()]

    rutas: list[Path] = []
    for objetivo in objetivos:
        p = Path(objetivo)
        if p.is_dir():
            rutas += [
                f for f in p.rglob("*")
                if f.is_file()
                and f.suffix.lower() in EXTENSIONES
                and not IGNORAR & set(f.parts)
            ]
        elif p.is_file():
            rutas.append(p)
    return rutas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Busca datos personales antes de compartir o commitear."
    )
    ap.add_argument("objetivos", nargs="*", default=["."],
                    help="Archivos o directorios a escanear")
    ap.add_argument("--perfil", type=Path, default=None,
                    help="perfil.toml, para también buscar nombres propios")
    ap.add_argument("--staged", action="store_true",
                    help="Escanear solo lo que va a entrar al commit")
    args = ap.parse_args(argv)

    nombres = nombres_del_perfil(args.perfil) if args.perfil else []
    archivos = archivos_de(args.objetivos or ["."], args.staged)

    globs = globs_ignorados(Path("."))
    if globs:
        antes = len(archivos)
        archivos = [a for a in archivos if not esta_ignorado(a, globs)]
        omitidos = antes - len(archivos)
        if omitidos:
            print(f"({omitidos} archivo(s) omitidos por {ARCHIVO_IGNORADOS})")

    if not archivos:
        print("No hay archivos que escanear.")
        return 0

    total = 0
    for archivo in sorted(archivos):
        hallazgos = escanear(archivo, nombres)
        if not hallazgos:
            continue
        print(f"\n{archivo}")
        for linea, etiqueta, muestra in hallazgos:
            print(f"  línea {linea:>4}  {etiqueta:<18} {muestra}")
        total += len(hallazgos)

    print()
    if total:
        print(f"⚠ {total} posible(s) dato(s) personal(es) en {len(archivos)} archivo(s).")
        print()
        print("  La pregunta que importa: ¿a dónde va este archivo?")
        print("    · Se queda en expediente/  → está bien, ahí debe estar.")
        print("    · Va al contador           → lo necesita; confirma el destinatario.")
        print("    · Va a un repo o a un issue → quítalo o reemplázalo por un placeholder.")
        print()
        print("  Algunos hallazgos serán falsos positivos (cifras, referencias).")
        print("  Revisa antes de borrar nada.")
        return 1

    print(f"✓ Sin datos personales detectados en {len(archivos)} archivo(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
