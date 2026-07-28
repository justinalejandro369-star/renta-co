"""Serie TRM diaria — Banco de la República vía datos.gov.co.

El art. 288 ET exige convertir cada operación en moneda extranjera a la TRM
de SU fecha de realización. No a un promedio anual, no a la de cierre. En
2025 la TRM osciló 19% entre mínimo y máximo: usar un promedio mueve la base
gravable en millones.

Privacidad: lo único que sale de tu máquina es un rango de fechas — y hay
que ser preciso sobre cuál: son la fecha del primer y del último movimiento
en moneda extranjera de tu ledger, así que revelan cuándo empezaste y
terminaste de facturar. En corridas incrementales, los días nuevos. Como toda
petición HTTP, también llega tu IP. No se envía ningún monto, nombre ni
identificador. La serie se cachea localmente y a partir de ahí funciona sin
red: con `--sin-red` no se hace ninguna petición.
"""

from __future__ import annotations

import csv
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

FUENTE = "https://www.datos.gov.co/resource/32sa-8pi3.json"
NOMBRE_CACHE = "trm-cache.csv"


class SinTRM(Exception):
    pass


def _parse_fecha(texto: str) -> date:
    texto = texto.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto[: len(fmt) + 6], fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha no reconocida: {texto!r}")


def descargar(desde: date, hasta: date, timeout: int = 30) -> dict[date, float]:
    """Descarga la serie oficial. Solo se envía el rango de fechas."""
    params = urllib.parse.urlencode({
        "$where": f"vigenciadesde >= '{desde:%Y-%m-%d}' AND vigenciadesde <= '{hasta:%Y-%m-%d}'",
        "$limit": "50000",
        "$select": "valor,vigenciadesde,vigenciahasta",
    })
    url = f"{FUENTE}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            filas = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise SinTRM(
            f"No se pudo descargar la TRM ({e}). Opciones: reintenta, o descarga "
            f"la serie manualmente de {FUENTE} y guárdala como CSV con columnas "
            f"'fecha,trm' en tu expediente."
        ) from e

    serie: dict[date, float] = {}
    for fila in filas:
        try:
            valor = float(fila["valor"])
            d = _parse_fecha(fila["vigenciadesde"])
            h = _parse_fecha(fila.get("vigenciahasta") or fila["vigenciadesde"])
        except (KeyError, ValueError):
            continue
        # una vigencia puede cubrir varios días (fines de semana, festivos)
        while d <= h:
            serie[d] = valor
            d += timedelta(days=1)
    if not serie:
        raise SinTRM(f"La fuente no devolvió datos para {desde} — {hasta}.")
    return serie


def leer_cache(ruta: Path) -> dict[date, float]:
    if not ruta.exists():
        return {}
    serie = {}
    with open(ruta, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            try:
                serie[_parse_fecha(fila["fecha"])] = float(fila["trm"])
            except (KeyError, ValueError):
                continue
    return serie


def escribir_cache(ruta: Path, serie: dict[date, float]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "trm"])
        for d in sorted(serie):
            w.writerow([d.isoformat(), f"{serie[d]:.2f}"])


class TRM:
    """Serie TRM con caché local. Se puede usar totalmente offline."""

    def __init__(self, serie: dict[date, float], desde_cache: bool = False):
        if not serie:
            raise SinTRM("Serie TRM vacía.")

        self.serie = serie
        self.desde_cache = desde_cache
        # Fechas para las que hubo que retroceder a un día anterior. Se
        # registran para que el ledger pueda decirlo: el art. 288 exige la
        # TRM de la fecha de realización, y una TRM suplida es una posición,
        # no un dato. Antes se rellenaba en silencio hasta 7 días atrás y la
        # columna del ledger mostraba el valor viejo como si fuera del día.
        self.suplidas: dict[date, tuple[date, float]] = {}

    @classmethod
    def para(cls, desde: date, hasta: date, cache: Path | None = None,
             permitir_red: bool = True) -> "TRM":
        serie = leer_cache(cache) if cache else {}
        faltan = [
            desde + timedelta(days=i)
            for i in range((hasta - desde).days + 1)
            if desde + timedelta(days=i) not in serie
        ]
        if faltan and permitir_red:
            serie.update(descargar(min(faltan), max(faltan)))
            if cache:
                escribir_cache(cache, serie)
            # Verificar que la descarga cerró los huecos. La fuente puede
            # devolver un rango parcial, y sin este chequeo el objeto se
            # construía igual y `de()` rellenaba hacia atrás sin avisar.
            quedan = [d for d in faltan if d not in serie]
            if quedan:
                cubiertos = sum(
                    1 for d in quedan
                    if any((d - timedelta(days=i)) in serie for i in range(1, 5))
                )
                if cubiertos < len(quedan):
                    raise SinTRM(
                        f"La descarga dejó {len(quedan) - cubiertos} día(s) sin "
                        f"TRM ni un día hábil cercano. Primero: {min(quedan)}. "
                        f"Reintenta, o carga la serie a mano en el caché."
                    )
            return cls(serie)
        if faltan:
            raise SinTRM(
                f"Faltan {len(faltan)} día(s) en el caché de TRM y la red está "
                f"desactivada. Primer día faltante: {min(faltan)}."
            )
        return cls(serie, desde_cache=True)

    def de(self, fecha: date) -> float:
        """TRM de una fecha.

        Si no hay dato —fin de semana o festivo— usa el último día hábil
        previo, que es lo correcto: esa TRM sigue vigente. Pero deja registro
        de cuántos días retrocedió, porque no es lo mismo tomar la del viernes
        para un sábado que rellenar un hueco de cinco días porque la descarga
        vino incompleta.
        """
        if fecha in self.serie:
            return self.serie[fecha]
        for atras in range(1, 8):
            previo = fecha - timedelta(days=atras)
            if previo in self.serie:
                self.suplidas[fecha] = (previo, self.serie[previo])
                return self.serie[previo]
        raise SinTRM(
            f"Sin TRM para {fecha} ni los 7 días anteriores. La serie está "
            f"incompleta: borra el caché y vuelve a descargarla."
        )

    def huecos_grandes(self, dias: int = 3) -> list[tuple[date, date, int]]:
        """Fechas donde hubo que retroceder más de `dias`.

        Un fin de semana largo son 3 o 4 días y es normal. Más que eso indica
        que la descarga vino incompleta, y con una oscilación del 19% en el
        año eso mueve la base gravable de verdad.
        """
        return [
            (fecha, origen, (fecha - origen).days)
            for fecha, (origen, _) in sorted(self.suplidas.items())
            if (fecha - origen).days > dias
        ]

    def rango(self) -> tuple[float, float]:
        vals = self.serie.values()
        return min(vals), max(vals)

    def promedio(self) -> float:
        return sum(self.serie.values()) / len(self.serie)
