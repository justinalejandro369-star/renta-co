"""Carga y validación del perfil del contribuyente.

El perfil vive en <expediente>/perfil.toml, en la máquina del usuario, fuera
de control de versiones. Este módulo NO lo escribe ni lo transmite: solo lo
lee, valida que los números tengan sentido y reporta qué falta.

Todo campo ausente vale 0 y queda registrado como supuesto, para que la
salida distinga siempre entre "es cero" y "no lo sabemos todavía".
"""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Estructura esperada: sección -> {campo: valor por defecto}
ESQUEMA: dict[str, dict] = {
    "contribuyente": {
        "anio_gravable": 2025,
        "residente_fiscal": True,
    },
    "ingresos": {
        "rentas_trabajo_honorarios": 0,
        "rentas_capital": 0,
        "otras_rentas_no_laborales": 0,
    },
    "incrngo": {
        "aportes_obligatorios_salud_pension": 0,
        "componente_inflacionario": 0,
        "otros": 0,
    },
    "costos": {
        "pagos_a_contratistas": 0,
        "comisiones_plataforma": 0,
        "equipo_tecnologico": 0,
        "internet_software": 0,
        "arriendo_oficina": 0,
        "otros": 0,
    },
    "deducciones": {
        "gmf_pagado": 0,
        "intereses_vivienda": 0,
        "medicina_prepagada": 0,
        "aportes_voluntarios": 0,
        "compras_con_factura_electronica": 0,
        "dependientes": 0,
    },
    "descuentos": {
        "donaciones_certificadas_rte": 0,
    },
    "anticipos": {
        "retenciones_practicadas": 0,
        "saldo_a_favor_anio_anterior": 0,
    },
    "verificaciones": {
        "consignaciones_totales_anio": 0,
        "contratistas_con_pila_verificada": False,
        "tiene_documento_soporte_de_pagos": False,
    },
}

# Campos cuya ausencia cambia materialmente el resultado.
CRITICOS = [
    ("ingresos.rentas_trabajo_honorarios", "No hay ingresos por honorarios cargados."),
    (
        "deducciones.dependientes",
        "Dependientes en 0. Verifica padres, hermanos, cónyuge e hijos: "
        "cada uno vale 72 UVT FUERA del tope del 40%.",
    ),
    (
        "incrngo.aportes_obligatorios_salud_pension",
        "Aportes obligatorios de salud y pensión en 0. Si cotizaste, son "
        "INCRNGO y restan antes del tope del 40%. Busca las planillas PILA.",
    ),
    (
        "deducciones.gmf_pagado",
        "GMF en 0. Pide el certificado de 4x1000 a CADA banco: el 50% es deducible.",
    ),
    (
        "verificaciones.consignaciones_totales_anio",
        "Consignaciones totales sin cuantificar. Es el insumo del riesgo R-01 "
        "(pérdida de la calidad de no responsable de IVA).",
    ),
]


@dataclass
class Perfil:
    datos: dict
    ruta: Path | None = None
    supuestos: list[str] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)

    # ---- acceso ------------------------------------------------------

    def get(self, ruta: str, defecto=0):
        nodo = self.datos
        for parte in ruta.split("."):
            if not isinstance(nodo, dict) or parte not in nodo:
                return defecto
            nodo = nodo[parte]
        return nodo

    def set(self, ruta: str, valor):
        partes = ruta.split(".")
        nodo = self.datos
        for parte in partes[:-1]:
            nodo = nodo.setdefault(parte, {})
        nodo[partes[-1]] = valor

    def copia_con(self, **cambios) -> "Perfil":
        """Copia con campos cambiados. Para la tabla de sensibilidad."""
        nuevo = Perfil(copy.deepcopy(self.datos), self.ruta, list(self.supuestos))
        for ruta, valor in cambios.items():
            nuevo.set(ruta.replace("__", "."), valor)
        return nuevo

    @property
    def anio_gravable(self) -> int:
        return int(self.get("contribuyente.anio_gravable", 2025))

    # ---- agregados ---------------------------------------------------

    @property
    def ingresos_brutos(self) -> float:
        return sum(self.get(f"ingresos.{k}") for k in ESQUEMA["ingresos"])

    @property
    def total_incrngo(self) -> float:
        return sum(self.get(f"incrngo.{k}") for k in ESQUEMA["incrngo"])

    @property
    def total_costos(self) -> float:
        return sum(self.get(f"costos.{k}") for k in ESQUEMA["costos"])

    @property
    def patrimonio_bruto(self) -> float:
        return sum(a.get("valor", 0) for a in self.datos.get("patrimonio", {}).get("activos", []))

    @property
    def pasivos(self) -> float:
        return sum(p.get("valor", 0) for p in self.datos.get("patrimonio", {}).get("pasivos", []))


def _completar(datos: dict) -> tuple[dict, list[str]]:
    """Rellena con defectos y devuelve la lista de supuestos aplicados."""
    supuestos = []
    resultado = copy.deepcopy(datos)
    for seccion, campos in ESQUEMA.items():
        resultado.setdefault(seccion, {})
        for campo, defecto in campos.items():
            if campo not in resultado[seccion]:
                resultado[seccion][campo] = defecto
                if defecto in (0, False):
                    supuestos.append(f"{seccion}.{campo} = {defecto} (no informado)")
    resultado.setdefault("patrimonio", {})
    resultado["patrimonio"].setdefault("activos", [])
    resultado["patrimonio"].setdefault("pasivos", [])
    return resultado, supuestos


def validar(perfil: Perfil) -> list[str]:
    """Errores que impiden calcular. Distinto de 'faltantes', que solo avisan."""
    errores = []

    if not perfil.get("contribuyente.residente_fiscal", True):
        errores.append(
            "El perfil dice que NO eres residente fiscal. Un no residente tributa "
            "por otras reglas (art. 247 ET, tarifa única sobre renta de fuente "
            "nacional) que este motor no implementa. Consulta con un contador."
        )

    for seccion, campos in ESQUEMA.items():
        for campo, defecto in campos.items():
            if not isinstance(defecto, bool) and isinstance(defecto, (int, float)):
                valor = perfil.get(f"{seccion}.{campo}")
                if not isinstance(valor, (int, float)) or isinstance(valor, bool):
                    errores.append(f"{seccion}.{campo} debe ser un número, no {valor!r}")
                elif valor < 0:
                    errores.append(f"{seccion}.{campo} no puede ser negativo ({valor})")

    dep = perfil.get("deducciones.dependientes")
    if isinstance(dep, (int, float)) and dep > 4:
        errores.append(
            f"deducciones.dependientes = {dep}. El art. 336 par. ET permite "
            f"máximo 4. Corrígelo o el cálculo quedará mal."
        )

    if perfil.ingresos_brutos == 0 and perfil.patrimonio_bruto == 0:
        errores.append(
            "No hay ni ingresos ni patrimonio. Carga los datos antes de calcular."
        )

    return errores


def revisar_faltantes(perfil: Perfil) -> list[str]:
    """Campos en cero que probablemente deberían tener valor."""
    avisos = []
    for ruta, mensaje in CRITICOS:
        if not perfil.get(ruta):
            avisos.append(mensaje)
    if not perfil.patrimonio_bruto:
        avisos.append(
            "Patrimonio bruto en 0. Es obligatorio declararlo y los activos "
            "omitidos que la DIAN detecte se gravan como renta líquida (art. 239-1 ET)."
        )
    return avisos


def cargar(ruta: Path | str) -> Perfil:
    ruta = Path(ruta)
    if ruta.is_dir():
        ruta = ruta / "perfil.toml"
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta}. Corre /renta:setup, o copia "
            f"templates/perfil.ejemplo.toml y llénalo."
        )
    with open(ruta, "rb") as f:
        crudo = tomllib.load(f)

    datos, supuestos = _completar(crudo)
    perfil = Perfil(datos, ruta, supuestos)
    perfil.faltantes = revisar_faltantes(perfil)
    return perfil
