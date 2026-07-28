"""Carga de parámetros tributarios por año gravable.

Los parámetros viven en knowledge/<agXXXX>/parametros.toml, cada cifra con
su fuente citada. Un año puede heredar de otro (meta.hereda_de) mientras
sus valores no se hayan verificado — los valores heredados quedan marcados
para que el motor pueda advertirlo en la salida.

Sin dependencias externas. Requiere Python 3.11+ por tomllib.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
KNOWLEDGE = RAIZ / "knowledge"


class ParametrosNoEncontrados(Exception):
    pass


class Parametros:
    """Parámetros de un año gravable, con trazabilidad de herencia."""

    def __init__(self, datos: dict, heredados: set[str], anio: int):
        self._d = datos
        self.heredados = heredados
        self.anio_gravable = anio

    # ---- acceso ------------------------------------------------------

    def get(self, ruta: str, defecto=None):
        """Lee por ruta con puntos: get('topes.gmf.porcentaje_deducible')."""
        nodo = self._d
        for parte in ruta.split("."):
            if not isinstance(nodo, dict) or parte not in nodo:
                return defecto
            nodo = nodo[parte]
        return nodo

    def exigir(self, ruta: str):
        valor = self.get(ruta)
        if valor is None:
            raise KeyError(f"Falta el parámetro '{ruta}' para AG{self.anio_gravable}")
        return valor

    @property
    def uvt(self) -> int:
        return self.exigir("uvt.valor")

    def cop(self, uvt: float) -> float:
        """Convierte UVT a pesos."""
        return uvt * self.uvt

    def fuente(self, ruta: str) -> str:
        """Devuelve la fuente citada del bloque que contiene esa ruta."""
        partes = ruta.split(".")
        while partes:
            f = self.get(".".join(partes) + ".fuente")
            if f:
                return f
            partes.pop()
        return "sin fuente citada"

    @property
    def completo(self) -> bool:
        return bool(self.get("meta.completo", True))

    def advertencias(self) -> list[str]:
        avisos = []
        if not self.completo:
            avisos.append(
                f"Los parámetros de AG{self.anio_gravable} están marcados como "
                f"INCOMPLETOS. Sirven para planeación, no para una declaración real. "
                f"{self.get('meta.nota', '')}".strip()
            )
        if self.heredados:
            base = self.get("meta.hereda_de", "otro año")
            avisos.append(
                f"{len(self.heredados)} bloque(s) heredados de {base} sin verificar "
                f"para AG{self.anio_gravable}: {', '.join(sorted(self.heredados))}."
            )
        if not self.get("plazos.tabla_cargada", False):
            avisos.append(
                "La tabla de plazos día-por-día no está cargada. Verifica tu fecha "
                "exacta en el portal de la DIAN antes de tomarla como definitiva."
            )
        return avisos


def _leer_toml(ruta: Path) -> dict:
    with open(ruta, "rb") as f:
        return tomllib.load(f)


def _fusionar(base: dict, encima: dict) -> tuple[dict, set[str]]:
    """Fusiona `encima` sobre `base`. Devuelve el resultado y qué se heredó."""
    resultado = dict(base)
    heredados = {k for k in base if k not in encima and k != "meta"}
    for clave, valor in encima.items():
        if (
            clave in resultado
            and isinstance(resultado[clave], dict)
            and isinstance(valor, dict)
        ):
            fusionado, sub = _fusionar(resultado[clave], valor)
            resultado[clave] = fusionado
            heredados |= {f"{clave}.{s}" for s in sub}
        else:
            resultado[clave] = valor
    return resultado, heredados


def cargar(anio_gravable: int, knowledge: Path | None = None) -> Parametros:
    """Carga los parámetros de un año gravable, resolviendo la herencia."""
    base_dir = knowledge or KNOWLEDGE
    carpeta = base_dir / f"ag{anio_gravable}"
    archivo = carpeta / "parametros.toml"

    if not archivo.exists():
        disponibles = sorted(
            p.name for p in base_dir.glob("ag*") if (p / "parametros.toml").exists()
        )
        raise ParametrosNoEncontrados(
            f"No hay parámetros para el año gravable {anio_gravable}. "
            f"Disponibles: {', '.join(disponibles) or 'ninguno'}. "
            f"Para agregarlo, crea {archivo} — mira el de ag2025 como plantilla."
        )

    datos = _leer_toml(archivo)
    heredados: set[str] = set()

    padre = datos.get("meta", {}).get("hereda_de")
    if padre:
        anio_padre = int(str(padre).replace("ag", ""))
        p = cargar(anio_padre, base_dir)
        datos, heredados = _fusionar(p._d, datos)
        # el meta del hijo siempre manda
        datos["meta"] = _leer_toml(archivo)["meta"]

    return Parametros(datos, heredados, anio_gravable)


def anios_disponibles(knowledge: Path | None = None) -> list[int]:
    base_dir = knowledge or KNOWLEDGE
    return sorted(
        int(p.name[2:])
        for p in base_dir.glob("ag*")
        if (p / "parametros.toml").exists() and p.name[2:].isdigit()
    )
