"""CLI de renta-co.

    python -m engine.cli calcular   --expediente ./expediente
    python -m engine.cli importar   --expediente ./expediente
    python -m engine.cli verificar  --expediente ./expediente
    python -m engine.cli parametros --anio 2025

Diseñado para que el agente lo invoque y lea la salida, y para que un humano
la entienda sin el agente. La aritmética vive acá, no en el modelo.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import parametros as P
from . import perfil as PF
from .depuracion import RUTAS, comparar

ANCHO = 84


def cop(x: float) -> str:
    return f"${x:,.0f}".replace(",", ".")


def linea(c: str = "─") -> None:
    print(c * ANCHO)


def titulo(texto: str) -> None:
    print()
    linea("═")
    print(texto)
    linea("═")


# ---------------------------------------------------------------------

def cmd_calcular(args) -> int:
    p = PF.cargar(args.expediente)
    errores = PF.validar(p, P.anios_disponibles())
    if errores:
        print("No se puede calcular todavía:\n")
        for e in errores:
            print(f"  ✗ {e}")
        return 1

    anio = args.anio or p.anio_gravable
    par = P.cargar(anio)
    r = comparar(p, par)

    titulo(f"DECLARACIÓN DE RENTA — AÑO GRAVABLE {anio}    UVT {cop(par.uvt)}")

    for aviso in r["advertencias_parametros"]:
        print(f"  ⚠ {aviso}")
    if r["advertencias_parametros"]:
        print()

    a, b = r["rutas"]["A"], r["rutas"]["B"]
    print(f"{'CONCEPTO':<52}{'RUTA A':>15}{'RUTA B':>15}")
    print(f"{'':<52}{'costos':>15}{'25% exento':>15}")
    linea()
    # Las dos rutas emiten los mismos renglones en el mismo orden, así que
    # se imprimen por posición. La única fila cuya ETIQUETA puede diferir es
    # la última: una ruta puede dar saldo a pagar y la otra saldo a favor.
    # Usar la etiqueta de A para las dos invertía el signo del resultado en
    # pantalla, justo en el caso más frecuente —retenciones altas—.
    for i, ren in enumerate(a.renglones):
        rb = b.renglones[i]
        if i == len(a.renglones) - 1:
            etiqueta = "= SALDO  (+ a pagar · − a favor)"
            va, vb = round(a.saldo), round(b.saldo)
        else:
            etiqueta, va, vb = ren.concepto, ren.valor, rb.valor
        print(f"{_recortar(etiqueta, 52):<52}{cop(va):>15}{cop(vb):>15}")
    linea()

    mejor = r["mejor_ruta"]
    print()
    print(f"  Ruta más favorable      : RUTA {mejor} — {RUTAS[mejor]}")
    print(f"  Diferencia entre rutas  : {cop(r['diferencia_entre_rutas'])}")
    print(f"  Tarifa marginal         : {r['tarifa_marginal']:.0%}")
    # La vía de dependientes puede diferir entre rutas. Reportar siempre la
    # de A contradecía la tabla de arriba cuando ganaba B, y es la línea que
    # alguien copia al formulario.
    ganadora = r["rutas"][mejor]
    if ganadora.dependientes_via != "sin dependientes":
        print(f"  Vía de dependientes     : {ganadora.dependientes_via}")
        otra = r["rutas"]["B" if mejor == "A" else "A"]
        if otra.dependientes_via != ganadora.dependientes_via:
            print(f"    (la otra ruta usaría: {otra.dependientes_via})")

    print()
    print(f"  Patrimonio bruto        : {cop(r['patrimonio_bruto'])}")
    print(f"  Pasivos                 : {cop(r['pasivos'])}")
    print(f"  Patrimonio líquido      : {cop(r['patrimonio_liquido'])}")

    # --- sensibilidad ------------------------------------------------
    titulo("CUÁNTO VALE CADA PALANCA — impuesto ahorrado, en pesos")
    if not r["sensibilidad"]:
        print("  No hay palancas pendientes: todo lo modelable ya está cargado.")
    else:
        from .depuracion import DESEMBOLSO

        gratis = [x for x in r["sensibilidad"] if x.tipo != DESEMBOLSO]
        cuestan = [x for x in r["sensibilidad"] if x.tipo == DESEMBOLSO]

        def bloque(titulo_bloque, items, subtitulo):
            if not items:
                return
            print(f"  {titulo_bloque}")
            print(f"  {subtitulo}")
            print()
            print(f"{'PALANCA':<52}{'RUTA A':>15}{'RUTA B':>15}")
            linea()
            for pal in items:
                marca = f" [solo {pal.solo_ruta}]" if pal.solo_ruta else ""
                print(f"{_recortar(pal.etiqueta + marca, 52):<52}"
                      f"{cop(pal.ahorro_a):>15}{cop(pal.ahorro_b):>15}")
                if pal.tipo == DESEMBOLSO:
                    signo = "queda a favor" if pal.neto > 0 else "PIERDES"
                    print(f"      Desembolso {cop(pal.costo)} → {signo} "
                          f"{cop(abs(pal.neto))} en neto")
                for tramo in _envolver(pal.nota, ANCHO - 6):
                    print(f"      {tramo}")
                print()

        bloque("SIN SACAR PLATA DEL BOLSILLO",
               gratis,
               "Conseguir un papel, o acreditar algo que ya es cierto.")
        bloque("EXIGEN DESEMBOLSAR",
               cuestan,
               "El ahorro NO es ganancia: compáralo contra lo que hay que poner.")

    # --- verificaciones ----------------------------------------------
    titulo("VERIFICACIONES DE OBLIGACIÓN Y RIESGO")
    for v in r["verificaciones"]:
        icono = {"alta": "🔴", "media": "🟠", "info": "🔵"}.get(v["severidad"], "•")
        print(f"{icono} {v['id']} · {v['titulo']}")
        print(f"   Estado: {v['estado']}")
        for tramo in _envolver(v["detalle"], ANCHO - 3):
            print(f"   {tramo}")
        if v.get("fuente"):
            print(f"   Fuente: {v['fuente']}")
        print()

    # --- supuestos que deciden si este motor aplica --------------------
    # Un perfil sin bloque [contribuyente] producía una liquidación completa
    # de residente fiscal sin una sola advertencia: el supuesto se registraba
    # y solo lo imprimía `verificar`, que casi nadie corre.
    criticos = [x for x in r["supuestos"] if "DECIDE SI ESTE MOTOR APLICA" in x]
    if criticos:
        titulo("⚠ SUPUESTOS QUE DECIDEN SI ESTE CÁLCULO APLICA")
        for x in criticos:
            print(f"  · {x}")
        print()
        print("  No venían en el perfil y se asumieron. Si alguno está mal, el")
        print("  resultado completo lo está: confírmalos antes de seguir.")
        print()

    # --- lo que falta -------------------------------------------------
    if r["faltantes"]:
        titulo("LO QUE FALTA — ordenado por impacto potencial")
        for f in r["faltantes"]:
            for i, tramo in enumerate(_envolver(f, ANCHO - 4)):
                print(f"  {'•' if i == 0 else ' '} {tramo}")
        print()

    print()
    print("  Este resultado es un BORRADOR. No es asesoría tributaria y no se ha")
    print("  presentado ante la DIAN. Revísalo con un contador público antes de")
    print("  declarar. Ver DISCLAIMER.md.")
    print()

    if args.csv:
        destino = Path(args.expediente) / "03-analisis" / "escenarios.csv"
        _escribir_csv(destino, a, b)
        print(f"  CSV → {destino}")

    return 0


def _escribir_csv(destino: Path, a, b) -> None:
    import csv as _csv

    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["concepto", "ruta_A_costos", "ruta_B_exenta_25", "fuente"])
        for i, ren in enumerate(a.renglones):
            rb = b.renglones[i]
            if i == len(a.renglones) - 1:
                # El último renglón es SIEMPRE el saldo, con signo explícito
                # y la misma etiqueta pase lo que pase. Una versión anterior
                # solo usaba el signo cuando las dos rutas divergían, así que
                # la misma columna significaba una cosa u otra según el
                # perfil: quien lo leyera con un script sumaba un saldo a
                # favor como si fuera a pagar.
                w.writerow(["= SALDO (positivo a pagar, negativo a favor)",
                            round(a.saldo), round(b.saldo), ren.fuente])
            else:
                w.writerow([ren.concepto, ren.valor, rb.valor, ren.fuente])


def _recortar(texto: str, ancho: int) -> str:
    return texto if len(texto) <= ancho else texto[: ancho - 1] + "…"


def _envolver(texto: str, ancho: int) -> list[str]:
    palabras, lineas, actual = texto.split(), [], ""
    for pal in palabras:
        if len(actual) + len(pal) + 1 > ancho:
            lineas.append(actual)
            actual = pal
        else:
            actual = f"{actual} {pal}".strip()
    if actual:
        lineas.append(actual)
    return lineas


# ---------------------------------------------------------------------

def cmd_importar(args) -> int:
    from . import adapters
    from .ledger import Ledger, escribir_sugerencia_perfil
    from .trm import TRM, SinTRM

    exp = Path(args.expediente)
    crudo = exp / "00-crudo"
    if not crudo.exists():
        print(f"No existe {crudo}. Corre /renta-co:setup primero.")
        return 1

    ledger = Ledger()
    archivos = sorted(crudo.rglob("*.csv"))
    if not archivos:
        print(f"No hay archivos CSV en {crudo}.")
        print("Exporta tus movimientos de la plataforma o del banco y ponlos ahí.")
        return 1

    print(f"Archivos encontrados: {len(archivos)}\n")
    for archivo in archivos:
        try:
            movs, nombre = adapters.importar(archivo)
            for m in movs:
                ledger.agregar(m)
            print(f"  ✓ {archivo.name:<44} {nombre:<14} {len(movs):>4} movimientos")
        except ValueError as e:
            print(f"  ✗ {archivo.name}\n      {e}")

    if not ledger.movimientos:
        print("\nNo se importó ningún movimiento.")
        return 1

    # El propósito de `importar` es CONSTRUIR los datos que llenan el perfil,
    # así que no puede exigir que el perfil ya exista ni que parsee. Si está
    # y sirve, se usa su año; si no, se sigue sin filtrar y se avisa.
    anio = args.anio
    if anio is None and (exp / "perfil.toml").exists():
        try:
            anio = PF.cargar(exp).anio_gravable
        except (ValueError, OSError) as e:
            print(f"\n⚠ No se pudo leer perfil.toml para saber el año gravable "
                  f"({e.__class__.__name__}). Se importa todo sin filtrar; pasa "
                  f"--anio si quieres acotarlo.")
    if anio:
        antes = len(ledger.movimientos)
        ledger = ledger.filtrar_anio(anio)
        print(f"\nFiltrado al año gravable {anio}: {len(ledger.movimientos)} de {antes}")

    # TRM solo si hay moneda extranjera
    extranjeras = [m for m in ledger.movimientos if m.moneda.upper() != "COP"]
    trm = None
    if extranjeras:
        fechas = [m.fecha for m in extranjeras]
        cache = exp / "02-datos" / "trm-cache.csv"
        try:
            trm = TRM.para(min(fechas), max(fechas), cache=cache,
                           permitir_red=not args.sin_red)
            lo, hi = trm.rango()
            origen = "caché local" if trm.desde_cache else "datos.gov.co"
            print(f"\nTRM cargada desde {origen}: {len(trm.serie)} días, "
                  f"rango {cop(lo)} – {cop(hi)} ({(hi - lo) / lo:.1%} de oscilación)")
        except SinTRM as e:
            print(f"\n✗ {e}")
            return 1

    ledger.convertir(trm)
    destino = exp / "02-datos" / "ledger.csv"
    ledger.escribir_csv(destino)

    print(f"\nLedger → {destino}\n")
    print("Resumen por categoría:")
    for categoria, total in sorted(ledger.resumen().items(), key=lambda x: -abs(x[1])):
        print(f"  {categoria:<20} {cop(total):>18}")

    pendientes = ledger.sin_clasificar()
    if pendientes:
        print(f"\n⚠ {len(pendientes)} movimiento(s) SIN CLASIFICAR. El agente los "
              f"revisa contigo uno por uno; no se calcula nada hasta cerrarlos.")

    for aviso in ledger.validar(trm):
        for tramo in _envolver(aviso, ANCHO - 4):
            print(f"  ⚠ {tramo}" if tramo == _envolver(aviso, ANCHO - 4)[0] else f"    {tramo}")

    # --- puente al perfil ---------------------------------------------
    sugerido = escribir_sugerencia_perfil(ledger, exp / "02-datos" / "sugerido-perfil.toml")
    print(f"\nSugerencia de perfil → {sugerido}")
    print("  Revisa cada cifra y cópiala a perfil.toml. NO se sobrescribe tu")
    print("  perfil: ese paso es tuyo, y es donde se atrapan las clasificaciones")
    print("  equivocadas antes de que lleguen al impuesto.")

    # --- consignaciones -------------------------------------------------
    cons = ledger.consignaciones()
    print(f"\nEntradas brutas de todas las fuentes: {cop(cons['entradas_brutas'])}")
    for fuente, valor in cons["por_fuente"].items():
        print(f"    · {fuente:<40} {cop(valor):>18}")
    print()
    print("  ⚠ Esto NO es la cifra del umbral de 3.500 UVT de IVA. Léelo antes")
    print("    de usarlo:")
    for aviso in cons["avisos"]:
        for i, tramo in enumerate(_envolver(aviso, ANCHO - 8)):
            print(f"      {'·' if i == 0 else ' '} {tramo}")
    return 0


def cmd_verificar(args) -> int:
    p = PF.cargar(args.expediente)
    errores = PF.validar(p, P.anios_disponibles())
    faltantes = PF.revisar_faltantes(p)

    titulo("VERIFICACIÓN DEL PERFIL")
    if errores:
        print("Errores que impiden calcular:")
        for e in errores:
            print(f"  ✗ {e}")
    else:
        print("  ✓ El perfil es válido y se puede calcular.")

    if faltantes:
        print("\nCampos en cero que probablemente deberían tener valor:")
        for f in faltantes:
            for i, tramo in enumerate(_envolver(f, ANCHO - 4)):
                print(f"  {'•' if i == 0 else ' '} {tramo}")

    if p.supuestos:
        print(f"\n{len(p.supuestos)} campo(s) tomaron su valor por defecto:")
        for s in p.supuestos:
            print(f"  · {s}")

    return 1 if errores else 0


def cmd_parametros(args) -> int:
    anios = P.anios_disponibles()
    if args.anio is None:
        print("Años gravables disponibles:", ", ".join(str(a) for a in anios))
        return 0
    par = P.cargar(args.anio)
    titulo(f"PARÁMETROS — AÑO GRAVABLE {args.anio}")
    print(f"  UVT                    {cop(par.uvt)}   ({par.get('uvt.fuente')})")
    print()
    for clave, etiqueta in [
        ("topes.conjunto_deducciones_exentas.tope_uvt", "Tope conjunto"),
        ("topes.dependientes_72uvt.uvt_por_dependiente", "Por dependiente"),
        ("umbrales.obligado_a_declarar.ingresos_brutos_uvt", "Obligado a declarar (ingresos)"),
        ("umbrales.obligado_a_declarar.patrimonio_bruto_uvt", "Obligado a declarar (patrimonio)"),
        ("umbrales.no_responsable_iva.consignaciones_uvt", "No responsable IVA (consignaciones)"),
    ]:
        uvt = par.get(clave)
        if uvt:
            print(f"  {etiqueta:<38}{uvt:>8} UVT = {cop(par.cop(uvt)):>18}")
    print()
    print("  Tarifa art. 241:")
    for r in par.exigir("tarifa.rangos"):
        hasta = "en adelante" if r["hasta_uvt"] == 0 else f"{r['hasta_uvt']:>7,} UVT"
        print(f"    {r['desde_uvt']:>7,} – {hasta:<16} {r['tarifa']:>5.0%}  "
              f"+ {r['adicional_uvt']:>6,} UVT")
    for aviso in par.advertencias():
        print(f"\n  ⚠ {aviso}")
    return 0


# ---------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="renta-co",
        description="Motor de cálculo de la declaración de renta — persona natural, Colombia.",
        epilog="No es asesoría tributaria. Ver DISCLAIMER.md.",
    )
    sub = ap.add_subparsers(dest="comando", required=True)

    def comun(sp):
        sp.add_argument("--expediente", default="./expediente",
                        help="Ruta al expediente (default: ./expediente)")
        sp.add_argument("--anio", type=int, default=None,
                        help="Año gravable. Por defecto el del perfil.")
        return sp

    c = comun(sub.add_parser("calcular", help="Compara las dos rutas y da la sensibilidad"))
    c.add_argument("--csv", action="store_true", help="Escribe 03-analisis/escenarios.csv")
    c.set_defaults(func=cmd_calcular)

    i = comun(sub.add_parser("importar", help="Movimientos crudos → ledger con TRM diaria"))
    i.add_argument("--sin-red", action="store_true",
                   help="No descargar TRM; exige caché local completo")
    i.set_defaults(func=cmd_importar)

    v = comun(sub.add_parser("verificar", help="Valida el perfil y reporta qué falta"))
    v.set_defaults(func=cmd_verificar)

    pa = sub.add_parser("parametros", help="Muestra los parámetros de un año gravable")
    pa.add_argument("--anio", type=int, default=None)
    pa.set_defaults(func=cmd_parametros)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError, P.ParametrosNoEncontrados) as e:
        print(f"✗ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
