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

    def __init__(self, datos: dict, heredados: set[str], anio: int,
                 padre_incompleto: bool = False):
        self._d = datos
        self.heredados = heredados
        self.anio_gravable = anio
        self.padre_incompleto = padre_incompleto

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
        """Fuente citada del bloque que contiene esa ruta.

        Solo sube UN nivel: hasta el bloque que declara el valor. Subiendo
        hasta la raíz devolvía la fuente de un bloque padre para una cifra
        que el hijo cambió, o sea citaba una norma que no la respalda.
        """
        partes = ruta.split(".")
        if len(partes) > 1:
            f = self.get(".".join(partes[:-1]) + ".fuente")
            if f:
                return f
        return "sin fuente citada"

    @property
    def completo(self) -> bool:
        """Un año heredado no puede ser más completo que su padre."""
        if not bool(self.get("meta.completo", True)):
            return False
        return not self.padre_incompleto

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
            bloques = sorted({h.split(".")[0] for h in self.heredados})
            avisos.append(
                f"{len(bloques)} bloque(s) heredados de {base} sin verificar para "
                f"AG{self.anio_gravable}: {', '.join(bloques)}. Verifícalos contra "
                f"la norma antes de usar este año para una declaración real."
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


# Bloques que NUNCA se heredan: su contenido es específico del año y
# mostrarlo copiado del año anterior no es incompleto, es falso.
NO_HEREDABLES = {"plazos"}


def _fusionar(base: dict, encima: dict, raiz: bool = True) -> tuple[dict, set[str]]:
    """Fusiona `encima` sobre `base`. Devuelve el resultado y qué se heredó.

    `meta` se excluye en la raíz: el meta del hijo siempre reemplaza al del
    padre, así que reportar sus claves como heredadas es un falso positivo
    que infla la advertencia y le quita valor a la que sí importa.
    """
    resultado = dict(base)
    if raiz:
        for bloque in NO_HEREDABLES:
            resultado.pop(bloque, None)
    heredados = {
        k for k in resultado
        if k not in encima and not (raiz and k == "meta")
    }
    for clave, valor in encima.items():
        if (
            clave in resultado
            and isinstance(resultado[clave], dict)
            and isinstance(valor, dict)
        ):
            if raiz and clave == "meta":
                resultado[clave] = valor
                continue
            fusionado, sub = _fusionar(resultado[clave], valor, raiz=False)
            resultado[clave] = fusionado
            heredados |= {f"{clave}.{s}" for s in sub}
        else:
            resultado[clave] = valor
    return resultado, heredados


def cargar(anio_gravable: int, knowledge: Path | None = None,
           visitados: set[int] | None = None) -> Parametros:
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

    padre_incompleto = False
    padre = datos.get("meta", {}).get("hereda_de")
    if padre:
        try:
            anio_padre = int(str(padre).lower().replace("ag", ""))
        except ValueError:
            raise ParametrosNoEncontrados(
                f"meta.hereda_de = {padre!r} en {archivo} no es un año gravable. "
                f"Se escribe como 'ag2025'."
            ) from None
        if anio_padre == anio_gravable or anio_padre in (visitados or set()):
            raise ParametrosNoEncontrados(
                f"Ciclo de herencia en knowledge/: ag{anio_gravable} vuelve a "
                f"ag{anio_padre}. Revisa meta.hereda_de."
            )
        p = cargar(anio_padre, base_dir, (visitados or set()) | {anio_gravable})
        padre_incompleto = not p.completo
        datos, heredados = _fusionar(p._d, datos)
        # el meta del hijo siempre manda
        datos["meta"] = _leer_toml(archivo)["meta"]

    par = Parametros(datos, heredados, anio_gravable, padre_incompleto)
    _validar_tarifa(par, archivo)
    return par


def _validar_tarifa(par: Parametros, archivo: Path) -> None:
    """La tabla del art. 241 tiene que estar completa y ser contigua.

    `_fusionar` reemplaza las listas enteras, así que un hijo que declare un
    solo `[[tarifa.rangos]]` borra los otros seis en silencio y el motor
    liquida impuesto cero para cualquier base. Un año gravable sin tarifa
    válida no debe cargarse.
    """
    rangos = par.get("tarifa.rangos")
    if not rangos:
        raise ParametrosNoEncontrados(f"{archivo} no define tarifa.rangos.")
    if len(rangos) < 2:
        # Una tabla de un solo rango es lo que queda cuando un hijo declara
        # un `[[tarifa.rangos]]` y la fusión reemplaza la lista del padre.
        # Con tarifa 0 en ese rango único, el motor liquida cero para
        # cualquier base — en silencio, y sin aparecer como heredado.
        raise ParametrosNoEncontrados(
            f"{archivo}: la tarifa tiene {len(rangos)} rango(s). El art. 241 "
            f"tiene siete; una tabla así suele ser una lista que reemplazó a "
            f"la del año padre en vez de completarla."
        )
    tarifas = [r.get("tarifa", 0) for r in rangos]
    if tarifas != sorted(tarifas):
        raise ParametrosNoEncontrados(
            f"{archivo}: las tarifas marginales deben ir de menor a mayor."
        )
    if tarifas[-1] <= 0:
        raise ParametrosNoEncontrados(
            f"{archivo}: la tarifa del último rango es {tarifas[-1]}. Con eso "
            f"el impuesto sería cero para cualquier base."
        )
    if rangos[0].get("desde_uvt") != 0:
        raise ParametrosNoEncontrados(
            f"{archivo}: la tarifa debe empezar en 0 UVT, empieza en "
            f"{rangos[0].get('desde_uvt')}."
        )
    if rangos[-1].get("hasta_uvt") not in (0, None):
        raise ParametrosNoEncontrados(
            f"{archivo}: el último rango de la tarifa debe ser abierto "
            f"(hasta_uvt = 0)."
        )
    for anterior, siguiente in zip(rangos, rangos[1:]):
        if anterior.get("hasta_uvt") != siguiente.get("desde_uvt"):
            raise ParametrosNoEncontrados(
                f"{archivo}: hueco en la tarifa entre {anterior.get('hasta_uvt')} "
                f"y {siguiente.get('desde_uvt')} UVT."
            )


def anios_disponibles(knowledge: Path | None = None) -> list[int]:
    base_dir = knowledge or KNOWLEDGE
    return sorted(
        int(p.name[2:])
        for p in base_dir.glob("ag*")
        if (p / "parametros.toml").exists() and p.name[2:].isdigit()
    )
