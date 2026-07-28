"""Construcción del ledger: movimientos crudos → pesos con TRM diaria.

Un ledger es la lista de todos los movimientos del año gravable, cada uno
convertido a COP con la TRM de SU fecha, y clasificado en una categoría
tributaria. Es el insumo de la depuración y la prueba de dónde salió cada
cifra si la DIAN pregunta.

Categorías:
    ingreso_trabajo     honorarios, compensación por servicios
    ingreso_capital     rendimientos, dividendos, intereses
    costo               pago a contratista, comisión, insumo deducible
    gasto_personal      no deducible; se registra para no confundirlo con costo
    traslado            movimiento entre cuentas propias: NI ingreso NI gasto
    retencion           retención practicada por un tercero
    desconocido         requiere clasificación manual
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .trm import TRM

CATEGORIAS = {
    "ingreso_trabajo": "Renta de trabajo (honorarios / servicios)",
    "ingreso_capital": "Renta de capital",
    "costo": "Costo o gasto deducible (solo Ruta A)",
    "gasto_personal": "Gasto personal — NO deducible",
    "traslado": "Traslado entre cuentas propias — ni ingreso ni gasto",
    "retencion": "Retención en la fuente practicada",
    "desconocido": "Sin clasificar",
}

# El error más caro y más común del perfil freelance.
ADVERTENCIA_TRASLADO = (
    "Los traslados entre cuentas propias NO son ingreso. Contarlos infla la "
    "base gravable. Pero SÍ cuentan como consignación para el umbral de "
    "3.500 UVT de IVA — revisa ambas cosas."
)


@dataclass
class Movimiento:
    fecha: date
    descripcion: str
    monto_origen: float
    moneda: str = "COP"
    categoria: str = "desconocido"
    contraparte: str = ""
    fuente: str = ""          # de qué archivo salió
    trm: float | None = None
    monto_cop: float = 0.0

    def convertir(self, trm: TRM | None) -> "Movimiento":
        if self.moneda.upper() == "COP":
            self.trm = 1.0
            self.monto_cop = round(self.monto_origen)
        else:
            if trm is None:
                raise ValueError(
                    f"Movimiento en {self.moneda} el {self.fecha} sin serie TRM cargada."
                )
            self.trm = trm.de(self.fecha)
            self.monto_cop = round(self.monto_origen * self.trm)
        return self


@dataclass
class Ledger:
    movimientos: list[Movimiento] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def agregar(self, m: Movimiento) -> None:
        self.movimientos.append(m)

    def convertir(self, trm: TRM | None) -> "Ledger":
        for m in self.movimientos:
            m.convertir(trm)
        return self

    def total(self, categoria: str) -> float:
        return sum(m.monto_cop for m in self.movimientos if m.categoria == categoria)

    def resumen(self) -> dict[str, float]:
        return {c: self.total(c) for c in CATEGORIAS if self.total(c)}

    def sin_clasificar(self) -> list[Movimiento]:
        return [m for m in self.movimientos if m.categoria == "desconocido"]

    def consignaciones(self) -> float:
        """Todo lo que ENTRÓ a las cuentas, incluidos traslados.

        Es la base del umbral de 3.500 UVT del art. 437 par. 3 ET, y NO es lo
        mismo que el ingreso propio.
        """
        return sum(m.monto_cop for m in self.movimientos if m.monto_cop > 0)

    def validar(self) -> list[str]:
        avisos = list(self.avisos)
        pendientes = self.sin_clasificar()
        if pendientes:
            avisos.append(
                f"{len(pendientes)} movimiento(s) sin clasificar por "
                f"{sum(abs(m.monto_cop) for m in pendientes):,.0f} COP. "
                f"Clasifícalos antes de calcular: un ingreso mal clasificado "
                f"cambia el impuesto."
            )
        if self.total("traslado"):
            avisos.append(ADVERTENCIA_TRASLADO)
        fechas = [m.fecha for m in self.movimientos]
        if fechas:
            anios = {f.year for f in fechas}
            if len(anios) > 1:
                avisos.append(
                    f"El ledger mezcla los años {sorted(anios)}. Filtra al año "
                    f"gravable antes de calcular."
                )
        return avisos

    def filtrar_anio(self, anio: int) -> "Ledger":
        return Ledger(
            [m for m in self.movimientos if m.fecha.year == anio], list(self.avisos)
        )

    def escribir_csv(self, ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "fecha", "descripcion", "contraparte", "moneda",
                "monto_origen", "trm", "monto_cop", "categoria", "fuente",
            ])
            for m in sorted(self.movimientos, key=lambda x: x.fecha):
                w.writerow([
                    m.fecha.isoformat(), m.descripcion, m.contraparte, m.moneda,
                    f"{m.monto_origen:.2f}", f"{m.trm:.2f}" if m.trm else "",
                    m.monto_cop, m.categoria, m.fuente,
                ])

    def a_perfil(self) -> dict:
        """Mapea el ledger a las secciones del perfil.toml."""
        return {
            "ingresos": {
                "rentas_trabajo_honorarios": round(self.total("ingreso_trabajo")),
                "rentas_capital": round(self.total("ingreso_capital")),
            },
            "costos": {
                "otros": round(abs(self.total("costo"))),
            },
            "anticipos": {
                "retenciones_practicadas": round(abs(self.total("retencion"))),
            },
            "verificaciones": {
                "consignaciones_totales_anio": round(self.consignaciones()),
            },
        }


def comparar_trm_diaria_vs_promedio(ledger: Ledger, trm: TRM) -> dict:
    """Cuánta base gravable mueve usar promedio en vez de TRM diaria.

    Sirve para reconciliar cuando el contador usó promedio.
    """
    prom = trm.promedio()
    diaria = sum(
        m.monto_cop for m in ledger.movimientos
        if m.categoria.startswith("ingreso") and m.moneda.upper() != "COP"
    )
    promedio = sum(
        m.monto_origen * prom for m in ledger.movimientos
        if m.categoria.startswith("ingreso") and m.moneda.upper() != "COP"
    )
    minimo, maximo = trm.rango()
    return {
        "con_trm_diaria": round(diaria),
        "con_trm_promedio": round(promedio),
        "diferencia": round(diaria - promedio),
        "trm_promedio": round(prom, 2),
        "trm_minima": minimo,
        "trm_maxima": maximo,
        "oscilacion_pct": round((maximo - minimo) / minimo * 100, 1) if minimo else 0,
        "correcto": "TRM diaria — art. 288 ET",
    }
