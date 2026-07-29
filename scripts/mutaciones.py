#!/usr/bin/env python3
"""Inyector de mutaciones — mide si la suite sirve para algo.

    python3 scripts/mutaciones.py          # las 100
    python3 scripts/mutaciones.py M11      # una sola

Un test que pasa no dice nada; lo que dice algo es un test que FALLA cuando
el código que dice cubrir se rompe. La ronda 5 midió 28 de 49 (57%) y por
eso dio veredicto de NO LISTO: el núcleo tributario detectaba casi todo y
la capa de datos no detectaba nada.

Regla de uso: después de agregar tests, agrega también la mutación que
dicen atrapar, y comprueba que la atrapan. Si escapa, el test no sirve.

Y ojo con la otra forma de que una mutación escape: que el test sí exista
pero no pruebe la CLASE. M87 —cambiar el filtro de `ded_fijas` por `if True`
sin tocar el de `fuera_fijas`— escapó teniendo un test dedicado, porque el
test comprobaba «voltear el flag cambia el impuesto» y eso seguía siendo
cierto con el 1% de factura electrónica contado a los dos lados del tope. Lo
que faltaba era la invariante: los dos lados tienen que SUMAR el total.

Ojo con las mutaciones FALSAS —las que no cambian el comportamiento—. Una
de ellas (leer `ingresos_brutos_uvt` en vez de `consignaciones_uvt`, que en
AG2025 valen los dos 3.500) se contó como escapada durante un rato: no
escapó, es que no mutaba nada. Si una mutación "escapa", primero comprueba
que de verdad cambie el resultado.

Cada mutación es un cambio plausible: lo que escribiría alguien apurado, no
un `raise` aleatorio. Se aplica, se corre `make test`, se restaura.

IMPORTANTE: se hace `touch` de todos los .py después de restaurar. Sin eso,
un __pycache__ con la misma mtime deja corriendo el bytecode mutado y la
medición miente en la dirección peligrosa (parece que la mutación escapó
cuando en realidad el arreglo nunca se cargó).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# (id, archivo, texto original, texto mutado)
MUTACIONES = [
    # ---- capa de datos: montos y separadores -----------------------
    ("M01-monto-banda-moneda", "engine/adapters/generico.py",
     '    if (moneda or "").strip().upper() in SIN_FRACCION_SIGNIFICATIVA:\n        return []',
     "    if False:\n        return []"),
    ("M02-monto-convencion-muerta", "engine/adapters/generico.py",
     "    sep = next(iter(decimales)) if decimales else None",
     "    sep = None"),
    ("M03-monto-relleno-es-decimal", "engine/adapters/generico.py",
     "    if _relleno_de_ceros(entero):\n        return []",
     "    if False:\n        return []"),
    ("M03b-cero-solo-no-es-decimal", "engine/adapters/generico.py",
     '    if entero == "0":\n        return [0]',
     "    if False:\n        return [0]"),
    ("M04-monto-sin-validacion-token", "engine/adapters/generico.py",
     "    if forma is None:\n        raise malo",
     "    if False:\n        raise malo"),
    ("M05-convencion-vota-malformados", "engine/adapters/generico.py",
     "        if len(idx) > 1 or (idx and idx[0] != len(seps) - 1):\n            continue",
     "        if False:\n            continue"),

    # ---- capa de datos: signo y clasificación ----------------------
    ("M06-deel-sin-veto-de-signo", "engine/adapters/deel.py",
     "            if categoria in ENTRANTES and monto < 0:",
     "            if False:"),
    ("M07-wise-sin-veto-de-signo", "engine/adapters/wise.py",
     "            if categoria in ENTRANTES and monto < 0:",
     "            if False:"),
    ("M08-bancolombia-sin-veto-de-signo", "engine/adapters/bancolombia.py",
     "            if categoria in ENTRANTES and monto < 0:",
     "            if False:"),
    ("M09-avisos-de-signo-solo-costos", "engine/ledger.py",
     "        for categoria, (signo, etiqueta, ejemplo) in self.SIGNO_ESPERADO.items():",
     "        for categoria, (signo, etiqueta, ejemplo) in list(self.SIGNO_ESPERADO.items())[2:]:"),
    ("M10-filas-malas-en-silencio", "engine/adapters/generico.py",
     "    if malas:\n        avisos.append(aviso_de_filas_saltadas",
     "    if False:\n        avisos.append(aviso_de_filas_saltadas"),

    # ---- TRM -------------------------------------------------------
    ("M11-trm-rellena-40-dias", "engine/trm.py",
     "        for atras in range(1, 8):",
     "        for atras in range(1, 41):"),
    ("M12-trm-devuelve-el-promedio", "engine/trm.py",
     "        if fecha in self.serie:\n            return self.serie[fecha]",
     "        if fecha in self.serie:\n            return self.promedio()"),
    ("M13-trm-no-verifica-huecos", "engine/trm.py",
     "                if cubiertos < len(quedan):",
     "                if False:"),
    ("M14-trm-banda-de-plausibilidad", "engine/trm.py",
     "            if not (TRM_MINIMA <= valor <= TRM_MAXIMA):",
     "            if False:"),

    # ---- ledger ----------------------------------------------------
    ("M15-conversion-ignora-la-trm", "engine/ledger.py",
     "            self.monto_cop = round(self.monto_origen * self.trm)",
     "            self.monto_cop = round(self.monto_origen)"),
    ("M16-filtrar-anio-deja-pasar", "engine/ledger.py",
     "            [m for m in self.movimientos if m.fecha.year == anio], list(self.avisos)",
     "            list(self.movimientos), list(self.avisos)"),
    ("M17-entradas-incluye-salidas", "engine/ledger.py",
     "            if m.monto_cop > 0:\n                por_fuente[m.fuente] = por_fuente.get(m.fuente, 0) + m.monto_cop",
     "            if True:\n                por_fuente[m.fuente] = por_fuente.get(m.fuente, 0) + abs(m.monto_cop)"),
    ("M18-reclasificacion-sin-ordinal", "engine/ledger.py",
     "        anterior = pendientes.pop(base + (ordinal,), None)",
     "        anterior = pendientes.pop(base + (0,), None)"),
    ("M19-reclasificacion-traga-ilegibles", "engine/ledger.py",
     "                    ilegibles.append(f\"línea {n}: {e}\")",
     "                    pass"),
    ("M20-aviso-de-mezcla-de-anios", "engine/ledger.py",
     "            if len(anios) > 1:",
     "            if False:"),

    # ---- perfil: las guardas de alcance ----------------------------
    ("M21-pension-no-detiene", "engine/perfil.py",
     '    if perfil.get("ingresos.rentas_pension"):',
     "    if False:"),
    ("M22-ganancia-ocasional-no-detiene", "engine/perfil.py",
     '    if perfil.get("ingresos.ganancia_ocasional"):',
     "    if False:"),
    ("M23-salario-no-detiene", "engine/perfil.py",
     '    if perfil.get("ingresos.rentas_laborales_salario"):',
     "    if False:"),
    ("M24-no-residente-no-detiene", "engine/perfil.py",
     '    if not perfil.get("contribuyente.residente_fiscal", True):',
     "    if False:"),
    ("M25-negativos-pasan", "engine/perfil.py",
     "    if valor < 0:\n        return [f\"{ruta} no puede ser negativo ({valor})\"]",
     "    if False:\n        return [f\"{ruta} no puede ser negativo ({valor})\"]"),
    ("M25b-negativos-en-patrimonio", "engine/perfil.py",
     "            errores += _errores_de_monto(\n                f\"patrimonio.{grupo}[{i}].valor",
     "            errores += [] and _errores_de_monto(\n                f\"patrimonio.{grupo}[{i}].valor"),
    ("M25c-punto-de-miles-pasa", "engine/perfil.py",
     "    if isinstance(valor, float):\n        # Entero pero escrito como float",
     "    if False:\n        # Entero pero escrito como float"),
    ("M26-tipos-no-se-validan", "engine/perfil.py",
     "    if not isinstance(valor, (int, float)) or isinstance(valor, bool):\n        return [f\"{ruta} debe ser un n\u00famero",
     "    if False:\n        return [f\"{ruta} debe ser un n\u00famero"),
    ("M27-dependientes-sin-tope", "engine/perfil.py",
     "    elif dep > 5:",
     "    elif dep > 50:"),

    # ---- parámetros ------------------------------------------------
    ("M28-cop-no-multiplica", "engine/parametros.py",
     "        return uvt * self.uvt",
     "        return uvt"),
    ("M29-tarifa-sin-contiguidad", "engine/parametros.py",
     "        if anterior.get(\"hasta_uvt\") != siguiente.get(\"desde_uvt\"):",
     "        if False:"),
    ("M30-tarifa-un-solo-rango", "engine/parametros.py",
     "    if len(rangos) < 2:",
     "    if False:"),
    ("M31-tarifa-porcentaje", "engine/parametros.py",
     "        if not 0 <= t <= 1:",
     "        if False:"),
    ("M32-tarifa-decreciente", "engine/parametros.py",
     "    if tarifas != sorted(tarifas):",
     "    if False:"),
    ("M33-tarifa-ultimo-cerrado", "engine/parametros.py",
     '    if rangos[-1].get("hasta_uvt") not in (0, None):',
     "    if False:"),
    ("M34-herencia-no-se-marca", "engine/parametros.py",
     "        if self.heredados:",
     "        if False:"),
    ("M35-incompleto-no-se-avisa", "engine/parametros.py",
     "        if not self.completo:",
     "        if False:"),

    # ---- verificaciones de obligación ------------------------------
    ("M36-obl01-patrimonio-por-diez", "engine/depuracion.py",
     'u.get("patrimonio_bruto_uvt", 4500) * uvt',
     'u.get("patrimonio_bruto_uvt", 4500) * uvt * 10'),
    ("M37-obl01-patrimonio-umbral-de-ingresos", "engine/depuracion.py",
     'if p.patrimonio_bruto >= u.get("patrimonio_bruto_uvt", 4500) * uvt:',
     'if p.patrimonio_bruto >= u.get("ingresos_brutos_uvt", 1400) * uvt:'),
    ("M38-obl01-mayor-estricto", "engine/depuracion.py",
     'if p.ingresos_brutos >= u.get("ingresos_brutos_uvt", 1400) * uvt:',
     'if p.ingresos_brutos > u.get("ingresos_brutos_uvt", 1400) * uvt * 1.0001:'),
    ("M39-obl01-afirma-que-no", "engine/depuracion.py",
     "    elif faltan_insumos:",
     "    elif False:"),
    ("M40-r01-umbral-equivocado", "engine/depuracion.py",
     'tope_iva = iva.get("consignaciones_uvt", 3500) * uvt',
     'tope_iva = iva.get("ingresos_brutos_uvt", 3500) * uvt'),
    ("M40b-r01-umbral-del-estado", "engine/depuracion.py",
     'tope_iva = iva.get("consignaciones_uvt", 3500) * uvt',
     'tope_iva = iva.get("consignaciones_uvt_contratistas_del_estado", 4000) * uvt'),
    ("M41-r01-sin-cuantificar-es-info", "engine/depuracion.py",
     '        estado, sev = "SIN CUANTIFICAR", "media"',
     '        estado, sev = "DENTRO DEL UMBRAL", "info"'),
    ("M42-r09-invertido", "engine/depuracion.py",
     "    if p.total_costos > p.ingresos_brutos * tope_ind and p.ingresos_brutos:",
     "    if p.total_costos < p.ingresos_brutos * tope_ind and p.ingresos_brutos:"),
    ("M43-r02-no-se-emite", "engine/depuracion.py",
     '    if pagos_contratistas > 0 and not p.get("verificaciones.contratistas_con_pila_verificada"):',
     "    if False:"),

    # ---- privacidad ------------------------------------------------
    ("M44-enmascarar-devuelve-todo", "scripts/escanear_privacidad.py",
     "                    salida.append(c if visible else \"X\")",
     "                    salida.append(c)"),
    ("M44b-enmascarar-no-tapa-nombres", "scripts/escanear_privacidad.py",
     "            salida.append(_tapar_palabra(trozo))",
     "            salida.append(trozo)"),
    ("M56-staged-sin-nul", "scripts/escanear_privacidad.py",
     '["git", "diff", "--cached", "-z", "--name-only", "--diff-filter=ACMR"],',
     '["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],'),
    ("M57-opacas-no-bloquean", "scripts/escanear_privacidad.py",
     "    if args.staged and opacas:",
     "    if False:"),
    ("M58-nombre-de-archivo-no-se-mira", "scripts/escanear_privacidad.py",
     "        h += hallazgos_del_nombre(ruta)",
     "        h += []"),
    ("M59-moneda-vacia-cae-al-defecto", "engine/adapters/generico.py",
     "    crudo = (fila.get(columna) or \"\").strip().upper()",
     "    crudo = (fila.get(columna) or defecto).strip().upper()"),
    ("M60-bancolombia-ignora-moneda", "engine/adapters/bancolombia.py",
     'c_moneda = col("moneda", "currency", "divisa", "ccy")',
     "c_moneda = None"),
    ("M61-fecha-sin-convencion", "engine/adapters/generico.py",
     '    if convencion == "mdy":',
     "    if False:"),
    ("M62-tipo-no-manda-sobre-descripcion", "engine/adapters/deel.py",
     "    impuesta = _por_tipo(tipo)",
     "    impuesta = None"),
    ("M63-retencion-como-subcadena", "engine/adapters/bancolombia.py",
     '(("retencion en la fuente", "retenci\u00f3n en la fuente", "rte fte",',
     '(("retencion", "retenci\u00f3n", "rte fte",'),
    ("M45-indice-lee-el-disco", "scripts/escanear_privacidad.py",
     '                ["git", "show", f":{ruta}"],',
     '                ["cat", ruta],'),
    ("M46-indice-ilegible-sale-cero", "scripts/escanear_privacidad.py",
     "        except SinIndice as e:\n            print(f\"✗ {e}\")\n            return 1",
     "        except SinIndice as e:\n            print(f\"✗ {e}\")\n            return 0"),
    ("M47-luhn-acepta-todo", "scripts/escanear_privacidad.py",
     "    return total % 10 == 0",
     "    return True"),
    ("M48-ignore-sin-limite", "scripts/escanear_privacidad.py",
     "        if omitidos > limite:",
     "        if False:"),

    # ---- CLI -------------------------------------------------------
    ("M49-cli-columna-b-repite-a", "engine/cli.py",
     "            etiqueta, va, vb = ren.concepto, ren.valor, rb.valor",
     "            etiqueta, va, vb = ren.concepto, ren.valor, ren.valor"),
    ("M50-cli-importar-sale-cero", "engine/cli.py",
     "        print()\n        return 1\n    return 0",
     "        print()\n        return 0\n    return 0"),
    # ---- menores de la ronda 5 -------------------------------------
    ("M51-sin-red-exige-fines-de-semana", "engine/trm.py",
     "                       for i in range(cls.DIAS_DE_RESPALDO + 1))",
     "                       for i in range(1))"),
    ("M52-contraparte-fuera-de-contexto", "scripts/escanear_privacidad.py",
     "    r\"contraparte|beneficiario|payee)\\b\",",
     "    r\"zzz_no_existe)\\b\","),
    ("M53-mojibake-no-se-detecta", "engine/adapters/generico.py",
     "        roto = MOJIBAKE.search(texto)",
     "        roto = None"),
    ("M54-columnas-sin-comillas", "scripts/escanear_privacidad.py",
     "        if c == '\"':\n            entre_comillas = not entre_comillas",
     "        if False:\n            entre_comillas = not entre_comillas"),
    ("M55-citas-hardcodeadas", "engine/depuracion.py",
     "    citada = par.fuente(ruta_valor)",
     "    citada = \"sin fuente citada\""),
    # ---- ronda 6, segunda tanda ------------------------------------
    ("M64-contratistas-fundidos-en-otros", "engine/ledger.py",
     'if m.categoria == "costo_contratista")',
     'if m.categoria == "zzz")'),
    ("M65-validar-no-alimenta-el-exit", "engine/cli.py",
     "    incidencias += ledger.bloqueantes(trm)",
     "    incidencias += []"),
    ("M66-sin-clasificar-no-bloquea", "engine/ledger.py",
     "        bloqueos = []\n        pendientes = self.sin_clasificar()\n        if pendientes:",
     "        bloqueos = []\n        pendientes = self.sin_clasificar()\n        if False:"),
    ("M67-no-se-compara-con-el-ledger", "engine/cli.py",
     "    desfase = _desfase_con_el_ledger(Path(args.expediente), p)",
     "    desfase = []"),
    ("M68-dep72-sin-rentas-de-trabajo", "engine/depuracion.py",
     "    if trabajo > 0:\n        dep_72 = min(n_dep, max_dep) * uvt_por_dep * uvt",
     "    if True:\n        dep_72 = min(n_dep, max_dep) * uvt_por_dep * uvt"),
    ("M69-sensibilidad-sobreestima", "engine/depuracion.py",
     "        return min(self.base_a, self.base_b) - min(self.saldo_a, self.saldo_b)",
     "        return max(self.ahorro_a, self.ahorro_b)"),
    ("M70-obl02-afirma-sin-insumos", "engine/depuracion.py",
     '    comerciante = p.get("contribuyente.es_comerciante", None)',
     "    comerciante = False"),
    ("M71-clasificacion-previa-utf8-duro", "engine/ledger.py",
     "        with abrir_csv(ruta) as f:",
     '        with open(ruta, newline="", encoding="utf-8") as f:'),
    ("M72-cedula-corta-no-se-ve", "scripts/escanear_privacidad.py",
     '("cédula corta o extranjería", re.compile(r"(?<!\\d)\\d{6,7}(?!\\d)"), "ambigua"),',
     ""),
    ("M73-iban-no-se-ve", "scripts/escanear_privacidad.py",
     '("IBAN", re.compile(r"\\b[A-Z]{2}\\d{2}[A-Z0-9]{10,30}\\b"), "alta"),',
     ""),
    # ---- ronda 6, tercera tanda ------------------------------------
    # No hay M75. `.privacidadignore` dejó de aplicarse en `--staged`
    # BORRANDO el filtrado, y este arnés muta código que existe: "alguien lo
    # vuelve a agregar" no se expresa como un cambio de una línea. La
    # conducta la cubre
    # `test_privacidadignore_no_puede_apagar_el_hook`, que monta un repo con
    # un glob estrecho y plausible y exige que el hook siga bloqueando.
    ("M76-llave-sin-descripcion", "engine/ledger.py",
     '    desc = " ".join(str(descripcion or "").split()).lower()',
     '    desc = ""'),
    ("M77-cache-rechaza-el-export-oficial", "engine/trm.py",
     '                   or campos.get("vigenciadesde"))',
     "                   or None)"),
    ("M78-duplicado-gana-el-ultimo", "engine/trm.py",
     "            if fecha in serie and serie[fecha] != valor:",
     "            if False:"),
    ("M79-preambulo-rompe-la-importacion", "engine/adapters/generico.py",
     "        if linea.strip() and linea.count(\",\") + linea.count(\";\") >= 1:",
     "        if True:"),

    # ---- ronda 7: el tope de costos por tipo de renta, la
    #      exclusividad por dependiente, los flags del knowledge,
    #      el art. 577, la discontinuidad del 241 y los patrones
    #      nuevos del escáner ------------------------------------
    ('M80-costos-sin-tope-por-tipo', 'engine/depuracion.py',
     '        pasa = min(pedido, techo)',
     '        pasa = pedido'),
    ('M81-techo-ignora-los-incrngo-del-tipo', 'engine/depuracion.py',
     '        techo = max(p.get(f"ingresos.{tipo}") - incrngo_tipo.get(tipo, 0.0), 0.0)',
     '        techo = max(p.get(f"ingresos.{tipo}"), 0.0)'),
    ('M82-la-renta-de-capital-reclama-los-costos', 'engine/perfil.py',
     '        actividad = [t for t in TIPOS_DE_ACTIVIDAD if self.get(f"ingresos.{t}") > 0]',
     '        actividad = [t for t in TIPOS_DE_RENTA if self.get(f"ingresos.{t}") > 0]'),
    ('M83-atribucion-declarada-se-ignora', 'engine/perfil.py',
     '            tipo = declarada.get(campo) or unico',
     '            tipo = unico'),
    ('M84-atribucion-con-typo-pasa-callada', 'engine/perfil.py',
     '            if campo not in ESQUEMA["costos"]:',
     '            if False:'),
    ('M85-dependientes-sin-escenario-mixto', 'engine/depuracion.py',
     '    if trabajo > 0 and n_dep > 1:\n        dep_72_resto = min(n_dep - 1, max_dep) * uvt_por_dep * uvt',
     '    if False:\n        dep_72_resto = min(n_dep - 1, max_dep) * uvt_por_dep * uvt'),
    ('M86-el-mixto-gasta-todos-los-dependientes', 'engine/depuracion.py',
     '        dep_72_resto = min(n_dep - 1, max_dep) * uvt_por_dep * uvt',
     '        dep_72_resto = min(n_dep, max_dep) * uvt_por_dep * uvt'),
    ('M87-flags-del-tope-no-se-leen', 'engine/depuracion.py',
     '        if par.get(f"{bloque}.dentro_del_tope_conjunto", True)',
     '        if True'),
    ('M88-marginal-devuelve-el-tramo-anterior', 'engine/depuracion.py',
     '        if hasta == 0 or base_uvt < hasta:\n            return rango["tarifa"]',
     '        if hasta == 0 or base_uvt <= hasta:\n            return rango["tarifa"]'),
    ('M89-577-no-aproxima', 'engine/depuracion.py',
     '    return int(round(valor / 1000) * 1000)',
     '    return int(valor)'),
    ('M90-no-avisa-la-discontinuidad-del-241', 'engine/depuracion.py',
     '        if desde <= base_cop <= hasta:',
     '        if False:'),
    ('M91-monto-sin-la-senal-del-tipo', 'engine/adapters/generico.py',
     '    if (not decimales and len(seps) > 1\n            and seps[-1] != seps[0] and len(set(seps[:-1])) == 1):',
     '    if (False and len(seps) > 1\n            and seps[-1] != seps[0] and len(set(seps[:-1])) == 1):'),
    ('M92-perfil-cosecha-cualquier-seccion', 'scripts/escanear_privacidad.py',
     '        if normalizar(seccion) in SECCIONES_DE_PERSONAS:',
     '        if True:'),
    ('M93-perfil-cosecha-cualquier-clave', 'scripts/escanear_privacidad.py',
     '        elif isinstance(nodo, str) and CLAVES_DE_PERSONA.fullmatch(clave):',
     '        elif isinstance(nodo, str):'),
    ('M94-el-inventario-no-mira-lo-excluido', 'scripts/escanear_privacidad.py',
     '        if esta_ignorado(a, globs, raiz) and a.name != ARCHIVO_INVENTARIO',
     '        if False'),
    ('M95-nada-cruza-lineas', 'scripts/escanear_privacidad.py',
     '    hallazgos += hallazgos_partidos(texto)',
     '    hallazgos += []'),
    ('M96-lo-partido-nunca-es-alta', 'scripts/escanear_privacidad.py',
     '                    enmascarar(bruto), "alta" if contexto else "baja",',
     '                    enmascarar(bruto), "baja",'),
    ('M97-subtotal-de-deducciones-incompleto', 'engine/depuracion.py',
     '    L._r("  = Subtotal deducciones dentro del tope", ded_fijas + e["dep_dentro"], 0,',
     '    L._r("  = Subtotal deducciones dentro del tope", ded_fijas, 0,'),
]


def tocar():
    ahora = time.time()
    for py in RAIZ.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        os.utime(py, (ahora, ahora))


def correr_suite() -> bool:
    """True si la suite DETECTA algo (falla)."""
    r = subprocess.run(
        ["python3", "-m", "unittest", "discover", "-s", "engine/tests", "-t", "."],
        cwd=RAIZ, capture_output=True, text=True,
    )
    return r.returncode != 0


def main():
    solo = sys.argv[1] if len(sys.argv) > 1 else None
    escapadas, detectadas, no_aplicadas = [], [], []

    for ident, relativo, viejo, nuevo in MUTACIONES:
        if solo and solo not in ident:
            continue
        archivo = RAIZ / relativo
        original = archivo.read_text(encoding="utf-8")
        if viejo not in original:
            no_aplicadas.append(ident)
            continue
        if original.count(viejo) > 1:
            no_aplicadas.append(f"{ident} (ambiguo: {original.count(viejo)})")
            continue
        try:
            archivo.write_text(original.replace(viejo, nuevo), encoding="utf-8")
            tocar()
            if correr_suite():
                detectadas.append(ident)
                print(f"  ✓ detectada   {ident}")
            else:
                escapadas.append(ident)
                print(f"  ✗ ESCAPÓ      {ident}")
        finally:
            archivo.write_text(original, encoding="utf-8")
            tocar()

    total = len(detectadas) + len(escapadas)
    print()
    print(f"Detectadas: {len(detectadas)}/{total} "
          f"({len(detectadas) / total:.0%})" if total else "sin mutaciones")
    if escapadas:
        print("\nESCAPARON:")
        for e in escapadas:
            print(f"  · {e}")
    if no_aplicadas:
        print("\nNo se pudieron aplicar (el texto cambió):")
        for n in no_aplicadas:
            print(f"  · {n}")
    return 1 if escapadas else 0


if __name__ == "__main__":
    sys.exit(main())
