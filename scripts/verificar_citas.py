#!/usr/bin/env python3
"""Chequeo de citas normativas contra la fuente primaria. Solo stdlib.

Por qué existe
──────────────
Este repositorio fabricó una cita. Escribió entre guillemets, como texto del
Decreto 2231, una frase que no existe, con una URL que devolvía «norma no
disponible». Sobrevivió a la revisión humana y habría sobrevivido a cualquier
chequeo de enlaces del mercado, por dos razones que este script ataca de
frente:

  1. **El soft-404.** La URL muerta respondía 302 → `norma_error.php` → **HTTP
     200**. `lychee`, `markdown-link-check` y `curl -fL` la reportan sana. El
     estado HTTP no dice nada. Lo que dice algo es la URL FINAL: si la
     redirección te dejó en otro documento, la cita apunta a la nada.

  2. **El content drift.** Medido en la literatura jurídica: >70% de las URLs
     citadas en el Harvard Law Review 1999–2012 ya no llevan al material, y
     hasta el 75% del contenido cambió en tres años SIN que la URL muriera.
     Un documento normativo que se modifica deja la URL viva y la cita falsa.
     Contra eso no sirve el estado, sirve el hash del texto.

Qué comprueba, para cada bloque de knowledge/ con `url_verificada = true`:

  · que la URL final tras redirecciones sea la declarada y no una página de
    error conocida;
  · que cada string de `cita_literal` aparezca LITERALMENTE en el texto de
    esa página, normalizado;
  · que el sha256 del texto normalizado siga siendo el de `sha256_fuente`.
    Si cambió, la norma se modificó o el sitio la re-maquetó: en los dos
    casos alguien tiene que volver a leerla.

Qué NO hace: no corre en `make test`. Una prueba con red no puede poner en
rojo la aritmética del motor — un DNS caído no es un error de liquidación.
Va en un job semanal aparte (.github/workflows/citas.yml).

Uso
───
    python3 scripts/verificar_citas.py              # chequea, sale 1 si falla
    python3 scripts/verificar_citas.py --registrar  # imprime los sha256 a pegar
    python3 scripts/verificar_citas.py --anio 2026
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import ssl
import sys
import tomllib
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
KNOWLEDGE = RAIZ / "knowledge"

AGENTE = "renta-co/verificar-citas (+https://github.com/, solo lectura)"
TIMEOUT = 30

# Formas conocidas de que una fuente colombiana devuelva 200 sobre nada.
# La primera es la que dejó pasar la cita fabricada de este repo.
PAGINAS_DE_ERROR = (
    "norma_error.php",
    "/error",
    "404.htm",
)
TEXTO_DE_ERROR = (
    "norma no disponible",
    "la norma solicitada no",
    "página no encontrada",
    "documento no encontrado",
)


class ExtractorDeTexto(HTMLParser):
    """Saca el texto visible. Sin dependencias, y determinista.

    El determinismo importa más que la fidelidad: el sha256 de la salida es
    la única defensa contra el content drift, y un extractor que dependa del
    orden de un dict o de un `set` produciría un hash distinto cada corrida
    y el chequeo se apagaría solo por ruidoso — que es exactamente cómo se
    apagó el hook de privacidad de este repo.
    """

    # Solo elementos que SÍ tienen etiqueta de cierre. `meta` y `link` son
    # vacíos: HTMLParser nunca les entrega un `handle_endtag`, así que
    # incluirlos dejaba el contador de salto arriba PARA SIEMPRE desde el
    # primer `<meta>` del documento. Primera versión de este script: la Ley
    # 2277 en el normograma de la DIAN —360 KB de texto— extraía cadena
    # vacía, el sha256 daba el del string vacío y la cita «no aparecía en la
    # fuente». Un extractor que devuelve nada acusa de fabricada una cita
    # correcta, que es el falso positivo más caro que podía tener este script.
    IGNORADOS = {"script", "style", "noscript", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._piezas: list[str] = []
        self._saltando = 0

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            # Red de seguridad contra el HTML mal balanceado de los gestores
            # normativos: pase lo que pase antes, el cuerpo se lee.
            self._saltando = 0
        elif tag in self.IGNORADOS:
            self._saltando += 1

    def handle_endtag(self, tag):
        if tag in self.IGNORADOS and self._saltando:
            self._saltando -= 1

    def handle_data(self, data):
        if not self._saltando:
            self._piezas.append(data)

    def texto(self) -> str:
        return " ".join(self._piezas)


def normalizar(texto: str) -> str:
    """Texto comparable: sin entidades, sin NBSP, sin dobles espacios.

    NFKC colapsa las comillas tipográficas y los espacios raros que meten
    los gestores documentales. Sin eso, una cita copiada del PDF y otra del
    HTML de la misma norma no coinciden aunque digan lo mismo.
    """
    texto = html.unescape(texto)
    texto = unicodedata.normalize("NFKC", texto)
    texto = texto.replace(" ", " ").replace("​", "")
    texto = "".join(
        " " if unicodedata.category(c) in ("Zs", "Cf") else c for c in texto
    )
    return re.sub(r"\s+", " ", texto).strip()


# Paquetes de raíces del sistema, en orden. NO se desactiva la verificación
# en ningún caso: un chequeo de citas que acepte cualquier certificado deja
# de poder afirmar de qué servidor vino el texto, que es la mitad del punto.
PAQUETES_DE_RAICES = ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt")


def _contexto() -> ssl.SSLContext:
    """Contexto TLS que funciona sin `certifi`.

    Python de Homebrew apunta a `/opt/homebrew/etc/openssl@3/cert.pem`, que
    en muchas máquinas es un symlink roto: la verificación falla con
    CERTIFICATE_VERIFY_FAILED mientras `curl` baja el documento sin
    problema. Cargar el paquete del sistema resuelve eso sin dependencias.
    """
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca", 0):
        return ctx
    for ruta in PAQUETES_DE_RAICES:
        if Path(ruta).exists():
            try:
                ctx.load_verify_locations(cafile=ruta)
                return ctx
            except ssl.SSLError:
                continue
    return ctx


def _decodificar(crudo: bytes) -> str:
    # Los sitios normativos colombianos declaran mal el charset con
    # frecuencia; latin-1 como respaldo evita perder el documento entero.
    try:
        return crudo.decode("utf-8")
    except UnicodeDecodeError:
        return crudo.decode("latin-1")


def _por_curl(url: str) -> tuple[str, bytes]:
    """Respaldo para servidores que sirven la cadena TLS incompleta.

    `www.funcionpublica.gov.co` —la fuente primaria de las dos citas más
    importantes de este repo— manda el certificado de hoja y el intermedio
    de Sectigo, pero no encadena hasta una raíz que OpenSSL tenga:
    `unable to verify the first certificate`. Los navegadores y `curl` no lo
    notan porque persiguen el AIA del certificado y bajan el intermedio que
    falta; OpenSSL no lo hace, así que `urllib` falla donde `curl` funciona.

    curl SIGUE verificando: no se le pasa `-k` ni `--insecure`. Un chequeo de
    citas que acepte cualquier certificado no puede afirmar de qué servidor
    salió el texto, y esa afirmación es la mitad del valor del chequeo.
    """
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        destino = Path(f.name)
    try:
        r = subprocess.run(
            ["curl", "-sSL", "--max-time", str(TIMEOUT), "-A", AGENTE,
             "--write-out", "%{url_effective}", "--output", str(destino), url],
            capture_output=True, text=True, timeout=TIMEOUT + 10,
        )
        if r.returncode != 0:
            raise urllib.error.URLError(
                f"urllib falló por la cadena TLS y curl también: "
                f"{r.stderr.strip() or r.returncode}"
            )
        return r.stdout.strip() or url, destino.read_bytes()
    except FileNotFoundError:
        raise urllib.error.URLError(
            "el servidor sirve una cadena TLS incompleta y no hay `curl` "
            "para perseguir el AIA. Instálalo o verifica esta cita a mano."
        ) from None
    finally:
        destino.unlink(missing_ok=True)


def descargar(url: str) -> tuple[str, str]:
    """Devuelve (url_final, texto_normalizado). Lanza en fallo de red."""
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_contexto()) as r:
            url_final, crudo = r.geturl(), r.read()
    except urllib.error.URLError as e:
        if not isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            raise
        url_final, crudo = _por_curl(url)
    p = ExtractorDeTexto()
    p.feed(_decodificar(crudo))
    return url_final, normalizar(p.texto())


def bloques_citables(anio: int) -> dict[str, dict]:
    """Bloques con `url_verificada = true`, por ruta con puntos."""
    with open(KNOWLEDGE / f"ag{anio}" / "parametros.toml", "rb") as f:
        datos = tomllib.load(f)
    encontrados: dict[str, dict] = {}

    def recorrer(nodo, ruta=""):
        if not isinstance(nodo, dict):
            return
        if nodo.get("url_verificada") is True:
            encontrados[ruta] = nodo
        for k, v in nodo.items():
            recorrer(v, f"{ruta}.{k}" if ruta else k)

    recorrer(datos)
    return encontrados


def revisar(ruta: str, bloque: dict) -> tuple[list[str], str | None]:
    """Devuelve (problemas, sha256_medido)."""
    problemas: list[str] = []
    url = bloque.get("url", "")
    if not url:
        return [f"{ruta}: declara url_verificada sin url"], None

    citas = bloque.get("cita_literal") or []
    if isinstance(citas, str):
        citas = [citas]
    if not citas:
        problemas.append(
            f"{ruta}: url_verificada = true sin `cita_literal`. La bandera "
            f"afirma que alguien abrió la fuente; sin el texto copiado nadie "
            f"puede volver a comprobarlo."
        )

    try:
        url_final, texto = descargar(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        return [f"{ruta}: no se pudo descargar {url} → {e}"], None

    # (1) soft-404: la URL final, no el estado.
    if any(marca in url_final for marca in PAGINAS_DE_ERROR):
        problemas.append(
            f"{ruta}: SOFT-404. {url} terminó en {url_final}, que es una "
            f"página de error. Devolvió HTTP 200 igual — por eso el estado "
            f"no sirve como chequeo."
        )
    elif url_final.split("#")[0] != url.split("#")[0]:
        problemas.append(
            f"{ruta}: la URL redirige a otro documento.\n"
            f"    declarada: {url}\n"
            f"    final:     {url_final}"
        )
    bajo = texto[:4000].lower()
    if any(m in bajo for m in TEXTO_DE_ERROR):
        problemas.append(
            f"{ruta}: el cuerpo de {url_final} dice que la norma no está "
            f"disponible, aunque respondió 200."
        )

    # (2) la cita, literal.
    for cita in citas:
        aguja = normalizar(str(cita))
        if aguja and aguja not in texto:
            problemas.append(
                f"{ruta}: esta cita NO aparece en la fuente:\n"
                f"    «{aguja[:160]}{'…' if len(aguja) > 160 else ''}»\n"
                f"    Una cita literal no se reconstruye de memoria — el texto "
                f"dice «setecientos noventa (790) UVT», no «790 UVT». Cópiala "
                f"del original o borra la bandera url_verificada."
            )

    # (3) content drift.
    medido = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    esperado = str(bloque.get("sha256_fuente", "") or "")
    if not esperado:
        problemas.append(
            f"{ruta}: sin `sha256_fuente`. Corre --registrar y pega el valor; "
            f"sin él, un cambio de la norma que no rompa la URL pasa invisible."
        )
    elif esperado != medido:
        problemas.append(
            f"{ruta}: CONTENT DRIFT. El texto de {url_final} cambió desde que "
            f"se verificó ({bloque.get('verificado_el', 'fecha sin declarar')}).\n"
            f"    registrado: {esperado}\n"
            f"    hoy:        {medido}\n"
            f"    La URL sigue viva y las citas pueden seguir apareciendo. "
            f"Reléela: puede haberse modificado el artículo que se cita."
        )
    return problemas, medido


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--anio", type=int, action="append",
                    help="año gravable (repetible); por defecto, todos")
    ap.add_argument("--registrar", action="store_true",
                    help="imprime los sha256 medidos para pegarlos en el TOML")
    args = ap.parse_args(argv)

    anios = args.anio or sorted(
        int(p.name[2:]) for p in KNOWLEDGE.glob("ag*")
        if (p / "parametros.toml").exists() and p.name[2:].isdigit()
    )

    total = 0
    problemas: list[str] = []
    hashes: list[tuple[str, str, str]] = []
    for anio in anios:
        for ruta, bloque in sorted(bloques_citables(anio).items()):
            total += 1
            print(f"  · ag{anio} {ruta} …", flush=True)
            fallos, medido = revisar(ruta, bloque)
            problemas += [f"ag{anio} · {f}" for f in fallos]
            if medido:
                hashes.append((f"ag{anio}", ruta, medido))

    print()
    if args.registrar:
        print("sha256_fuente medidos — pégalos en el bloque correspondiente:")
        for anio, ruta, h in hashes:
            print(f'  {anio} [{ruta}]  sha256_fuente = "{h}"')
        print()

    if not total:
        print("No hay ningún bloque con url_verificada = true.")
        print("Cobertura de citas: 0. Eso no es verde, es que no hay nada que")
        print("chequear — que era el estado real del repo cuando fabricó una.")
        return 1

    if problemas:
        print(f"✗ {len(problemas)} problema(s) sobre {total} bloque(s) citados:\n")
        for p in problemas:
            print(f"  {p}\n")
        return 1

    print(f"✓ {total} bloque(s) citados: URL final correcta, cita literal "
          f"presente y texto sin cambios.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
