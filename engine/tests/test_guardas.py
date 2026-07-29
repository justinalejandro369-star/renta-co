"""Las guardas: lo que impide un número creíble y equivocado.

Por qué existe este archivo
───────────────────────────
La medición de la ronda 5 encontró que el núcleo tributario detectaba 19 de
20 mutaciones, y que las GUARDAS alrededor no detectaban casi ninguna:

  · `perfil.validar()`: 0%. Escapaban las seis — no residente, pensión,
    ganancia ocasional, salario, montos negativos, `str` donde va número.
  · Los veredictos de `verificar_obligaciones`: el benchmark solo comprobaba
    que existieran los `id` y que la severidad fuera válida. Escapaban el
    umbral de patrimonio ×10, R-01 comparando contra el umbral equivocado y
    R-09 invertido. El titular más peligroso de la herramienta —«¿estás
    obligado a declarar?»— no tenía una sola aserción de contenido.
  · `_validar_tarifa`: 4 de sus 5 chequeos eran verificación muerta, porque
    el único test pasaba por la rama `tarifas[-1] <= 0` sin importar cuál de
    las otras estuviera viva. Acá va uno por chequeo.

La regla es la misma en todo el archivo: se afirma el CONTENIDO del
veredicto, no que el veredicto exista.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from engine import parametros as P
from engine import perfil as PF
from engine.depuracion import verificar_obligaciones
from engine.ledger import Ledger, Movimiento
from engine.parametros import ParametrosNoEncontrados
from engine.trm import TRM, SinTRM

RAIZ = Path(__file__).resolve().parent.parent.parent


def perfil_con(**secciones) -> PF.Perfil:
    datos, supuestos = PF._completar(secciones)
    return PF.Perfil(datos, None, supuestos)


# ---------------------------------------------------------------------
# perfil.validar() — las seis que escapaban
# ---------------------------------------------------------------------

class TestAlcanceDelMotor(unittest.TestCase):
    """Cada una de estas liquidaría de más o de menos por decenas de
    millones si el motor siguiera adelante. Y el resultado se ve bien."""

    BASE = {"contribuyente": {"anio_gravable": 2025, "residente_fiscal": True},
            "ingresos": {"rentas_trabajo_honorarios": 180_000_000}}

    def _errores(self, **cambios):
        datos = {k: dict(v) for k, v in self.BASE.items()}
        for seccion, campos in cambios.items():
            datos.setdefault(seccion, {}).update(campos)
        return PF.validar(perfil_con(**datos), P.anios_disponibles())

    def _perfil(self, **cambios):
        datos = {k: dict(v) for k, v in self.BASE.items()}
        for seccion, campos in cambios.items():
            datos.setdefault(seccion, {}).update(campos)
        return perfil_con(**datos)

    def test_el_perfil_base_si_se_puede_calcular(self):
        """El control: sin esto, cualquier guarda pasaría por rechazarlo todo."""
        self.assertEqual(self._errores(), [])

    def test_un_no_residente_se_detiene(self):
        errores = self._errores(contribuyente={"residente_fiscal": False})
        self.assertTrue(any("FUERA DE ALCANCE" in e and "residente" in e
                            for e in errores), errores)

    def test_la_pension_se_detiene(self):
        errores = self._errores(ingresos={"rentas_pension": 30_000_000})
        self.assertTrue(any("FUERA DE ALCANCE" in e and "pensión" in e.lower()
                            for e in errores), errores)
        self.assertTrue(any("206" in e for e in errores),
                        "el mensaje no cita el art. 206 num. 5")

    def test_la_ganancia_ocasional_se_detiene(self):
        errores = self._errores(ingresos={"ganancia_ocasional": 50_000_000})
        self.assertTrue(any("FUERA DE ALCANCE" in e and "ocasional" in e
                            for e in errores), errores)
        self.assertTrue(any("314" in e for e in errores))

    def test_el_salario_se_detiene(self):
        errores = self._errores(ingresos={"rentas_laborales_salario": 60_000_000})
        self.assertTrue(any("FUERA DE ALCANCE" in e and "336" in e
                            for e in errores), errores)

    def test_un_monto_negativo_se_detiene(self):
        errores = self._errores(costos={"otros": -1_000_000})
        self.assertTrue(any("negativo" in e for e in errores), errores)

    def test_un_punto_de_miles_en_un_campo_de_pesos_se_detiene(self):
        """`180.000` es TOML VÁLIDO: el float 180.0. Pasaba la validación con
        un ✓, el motor liquidaba sobre ciento ochenta pesos y devolvía
        "saldo $0" — la respuesta más cara que puede dar esta herramienta,
        con el sello de validada puesto. La señal es limpia: un monto en
        pesos es un entero."""
        errores = self._errores(ingresos={"rentas_trabajo_honorarios": 180.000})
        self.assertTrue(errores, "180.000 pasó la validación")
        self.assertTrue(any("180_000_000" in e for e in errores), errores)

    def test_un_monto_con_centavos_tambien_se_detiene(self):
        errores = self._errores(costos={"otros": 1_500_000.75})
        self.assertTrue(any("decimales" in e for e in errores), errores)

    def test_un_entero_de_verdad_no_molesta(self):
        """El control: la guarda no puede rechazar lo que sí es correcto."""
        self.assertEqual(self._errores(costos={"otros": 1_500_000}), [])

    def test_el_patrimonio_tambien_se_valida(self):
        """Era la única sección con montos fuera de ESQUEMA, así que no se
        validaba nada: un `valor = "350.000.000"` reventaba con un TypeError
        crudo antes de que nadie pudiera decir qué estaba mal."""
        errores = self._errores(patrimonio={"activos": [{"valor": "350.000.000"}]})
        self.assertTrue(any("debe ser un número" in e for e in errores), errores)
        self.assertTrue(any("patrimonio" in e for e in errores), errores)

    def test_un_activo_negativo_se_detiene(self):
        """Es la casilla que el art. 648 num. 1 sanciona al 200% por activos
        omitidos, y pasaba en silencio. Un pasivo negativo, además, AUMENTA
        el patrimonio líquido: el signo se invierte."""
        for grupo in ("activos", "pasivos"):
            errores = self._errores(patrimonio={grupo: [{"valor": -350_000_000}]})
            self.assertTrue(any("no puede ser negativo" in e for e in errores),
                            f"{grupo} negativo pasó: {errores}")

    def test_un_patrimonio_con_punto_de_miles_no_revienta_al_cargar(self):
        """`cargar()` llama a `revisar_faltantes()`, que suma el patrimonio,
        ANTES de que nadie valide. Tiene que salir el mensaje, no un
        traceback."""
        import tempfile

        exp = Path(tempfile.mkdtemp())
        (exp / "perfil.toml").write_text(
            "[contribuyente]\nanio_gravable = 2025\nresidente_fiscal = true\n"
            "[ingresos]\nrentas_trabajo_honorarios = 240_000_000\n"
            '[[patrimonio.activos]]\nnombre = "Apto"\nvalor = "350.000.000"\n',
            encoding="utf-8",
        )
        p = PF.cargar(exp)                       # no debe lanzar
        self.assertEqual(p.patrimonio_bruto, 0)
        self.assertTrue(PF.validar(p, P.anios_disponibles()))

    def test_un_texto_donde_va_un_numero_se_detiene(self):
        """En TOML los miles se escriben con guion bajo. Quien los escribe
        como en Colombia —180.000.000— produce un float de 180 o un str."""
        errores = self._errores(ingresos={"rentas_trabajo_honorarios": "180.000.000"})
        self.assertTrue(any("debe ser un número" in e for e in errores), errores)

    def test_el_error_de_tipo_corta_antes_de_hacer_aritmetica(self):
        """Va PRIMERO y devuelve solo: el resto de las validaciones hace
        cuentas y reventaría con un traceback."""
        errores = self._errores(ingresos={"rentas_trabajo_honorarios": "mucho"},
                                deducciones={"dependientes": 99})
        self.assertTrue(all("debe ser un número" in e for e in errores), errores)

    def test_mas_de_cinco_dependientes_se_detiene(self):
        """Cinco, no cuatro: el art. 336 num. 3 inciso 2 topa en 4 la
        deducción de 72 UVT, y el 10% del art. 387 consume un dependiente
        DISTINTO (Decreto 1625 art. 1.2.1.20.3). El quinto todavía vale."""
        self.assertEqual(self._errores(deducciones={"dependientes": 5}), [])
        errores = self._errores(deducciones={"dependientes": 6})
        self.assertTrue(any("máximo 5" in e for e in errores), errores)

    def test_un_anio_sin_parametros_se_detiene(self):
        errores = self._errores(contribuyente={"anio_gravable": 1999})
        self.assertTrue(any("1999" in e for e in errores), errores)

    def test_todas_las_guardas_de_alcance_estan_probadas(self):
        """Cierra la clase: si alguien agrega un cuarto campo fuera de
        alcance a ESQUEMA['ingresos'] y no lo prueba, esto falla."""
        fuera_de_alcance = {"rentas_laborales_salario", "rentas_pension",
                            "ganancia_ocasional"}
        for campo in fuera_de_alcance:
            self.assertIn(campo, PF.ESQUEMA["ingresos"])
            errores = self._errores(ingresos={campo: 1_000_000})
            self.assertTrue(any("FUERA DE ALCANCE" in e for e in errores),
                            f"{campo} no detiene el cálculo")
        # Y los que SÍ liquida no pueden haberse colado en la lista.
        for campo in PF.Perfil.INGRESOS_CEDULA_GENERAL:
            self.assertNotIn(campo, fuera_de_alcance)


# ---------------------------------------------------------------------
# verificar_obligaciones — el contenido, no la forma
# ---------------------------------------------------------------------

class TestVeredictosDeObligacion(unittest.TestCase):
    def setUp(self):
        self.par = P.cargar(2025)
        self.uvt = self.par.uvt

    def _check(self, id_, **secciones):
        datos = {"contribuyente": {"anio_gravable": 2025, "residente_fiscal": True}}
        for seccion, campos in secciones.items():
            datos.setdefault(seccion, {}).update(campos)
        checks = verificar_obligaciones(perfil_con(**datos), self.par)
        encontrado = next((c for c in checks if c["id"] == id_), None)
        self.assertIsNotNone(encontrado, f"no se emitió {id_}: {[c['id'] for c in checks]}")
        return encontrado

    # ---- OBL-01: el titular más peligroso de la herramienta -----------

    def test_obl01_dispara_justo_en_el_umbral_de_ingresos(self):
        """1.400 UVT exactas ya obligan: el art. 594-3 dice «igual o superior».
        Un ×10 en el umbral, o un > donde va >=, cambia el veredicto."""
        tope = 1400 * self.uvt
        justo = self._check("OBL-01", ingresos={"rentas_trabajo_honorarios": tope})
        self.assertEqual(justo["estado"], "SÍ")
        self.assertIn("ingresos brutos", justo["detalle"])

        debajo = self._check(
            "OBL-01",
            ingresos={"rentas_trabajo_honorarios": tope - 1},
            patrimonio={},
        )
        self.assertNotEqual(debajo["estado"], "SÍ")

    def test_obl01_usa_4500_uvt_para_patrimonio_y_no_el_de_ingresos(self):
        """El umbral de patrimonio es 4.500 UVT, no 1.400. Confundirlos hace
        que alguien con 1.500 UVT de patrimonio y sin ingresos crea que
        tiene que declarar, o al revés."""
        entre_los_dos = 2_000 * self.uvt
        c = self._check("OBL-01",
                        patrimonio={"activos": [{"valor": entre_los_dos}]})
        self.assertNotEqual(
            c["estado"], "SÍ",
            "2.000 UVT de patrimonio no superan el umbral de 4.500")

        arriba = self._check("OBL-01",
                             patrimonio={"activos": [{"valor": 4_500 * self.uvt}]})
        self.assertEqual(arriba["estado"], "SÍ")
        self.assertIn("patrimonio bruto", arriba["detalle"])

    def test_obl01_no_afirma_que_no_cuando_el_perfil_esta_a_medias(self):
        """«NO estás obligado» con el perfil vacío es la afirmación que
        termina en sanción por extemporaneidad."""
        c = self._check("OBL-01")
        self.assertIn("NO SE PUEDE AFIRMAR", c["estado"])
        self.assertEqual(c["severidad"], "media")

    def test_obl01_solo_dice_que_no_con_los_tres_insumos_cargados(self):
        c = self._check(
            "OBL-01",
            ingresos={"rentas_trabajo_honorarios": 10_000_000},
            patrimonio={"activos": [{"valor": 5_000_000}]},
            verificaciones={"consignaciones_totales_anio": 5_000_000},
        )
        self.assertEqual(c["estado"], "NO por los datos cargados")
        self.assertIn("tarjeta de", c["detalle"],
                      "no advierte de los dos umbrales que no modela")

    # ---- R-01: el umbral de IVA --------------------------------------

    def test_r01_compara_contra_3500_uvt_y_no_contra_otro_umbral(self):
        tope = 3_500 * self.uvt
        dentro = self._check("R-01",
                             verificaciones={"consignaciones_totales_anio": tope})
        self.assertEqual(dentro["estado"], "DENTRO DEL UMBRAL",
                         "3.500 UVT exactas todavía NO superan el umbral")

        fuera = self._check("R-01",
                            verificaciones={"consignaciones_totales_anio": tope + 1})
        self.assertEqual(fuera["estado"], "UMBRAL SUPERADO")
        self.assertEqual(fuera["severidad"], "alta")

    def test_r01_lee_la_clave_de_consignaciones_y_no_una_vecina(self):
        """En AG2025 `ingresos_brutos_uvt` y `consignaciones_uvt` valen los
        dos 3.500, así que confundirlos no cambia ni un peso y ninguna
        aserción sobre el resultado lo notaría. Se prueba con parámetros
        donde los umbrales vecinos son DISTINTOS, que es lo único que
        distingue «lee la clave correcta» de «da el número correcto por
        casualidad».
        """
        par = P.Parametros(
            {
                "uvt": {"valor": 100},
                "umbrales": {
                    "obligado_a_declarar": {"ingresos_brutos_uvt": 1_400},
                    "no_responsable_iva": {
                        "ingresos_brutos_uvt": 9_000,
                        "consignaciones_uvt": 3_500,
                        "consignaciones_uvt_contratistas_del_estado": 4_000,
                    },
                },
                "tarifa": {"rangos": [{"desde_uvt": 0, "hasta_uvt": 0,
                                       "tarifa": 0.39, "adicional_uvt": 0}]},
            },
            set(), 2025,
        )
        perfil = perfil_con(
            contribuyente={"anio_gravable": 2025, "residente_fiscal": True},
            verificaciones={"consignaciones_totales_anio": 3_500 * 100 + 1},
        )
        r01 = next(c for c in verificar_obligaciones(perfil, par) if c["id"] == "R-01")
        self.assertEqual(r01["estado"], "UMBRAL SUPERADO")

        justo_debajo = perfil_con(
            contribuyente={"anio_gravable": 2025, "residente_fiscal": True},
            verificaciones={"consignaciones_totales_anio": 3_500 * 100},
        )
        r01 = next(c for c in verificar_obligaciones(justo_debajo, par)
                   if c["id"] == "R-01")
        self.assertEqual(r01["estado"], "DENTRO DEL UMBRAL")

    def test_r01_sin_cuantificar_no_se_lee_como_estar_dentro(self):
        c = self._check("R-01")
        self.assertEqual(c["estado"], "SIN CUANTIFICAR")
        self.assertEqual(c["severidad"], "media")

    def test_r01_siempre_repite_el_calificador_de_actividad_gravada(self):
        """El art. 437 par. 3 num. 6 mide consignaciones PROVENIENTES DE
        ACTIVIDADES GRAVADAS. Omitirlo convierte la advertencia en una
        alarma falsa que empuja a inscribirse como responsable de IVA."""
        for consig in (0, 1_000_000, 4_000 * self.uvt):
            c = self._check("R-01",
                            verificaciones={"consignaciones_totales_anio": consig})
            self.assertIn("gravadas con IVA", c["detalle"])

    # ---- R-09: el tope indicativo del 60% ----------------------------

    def test_r09_se_emite_por_encima_del_60_y_no_por_debajo(self):
        """Invertir la comparación es la mutación obvia, y produce el aviso
        exactamente en los perfiles a los que no aplica."""
        ingresos = 100_000_000
        arriba = verificar_obligaciones(
            perfil_con(contribuyente={"anio_gravable": 2025, "residente_fiscal": True},
                       ingresos={"rentas_trabajo_honorarios": ingresos},
                       costos={"otros": 61_000_000}),
            self.par,
        )
        self.assertIn("R-09", [c["id"] for c in arriba])

        abajo = verificar_obligaciones(
            perfil_con(contribuyente={"anio_gravable": 2025, "residente_fiscal": True},
                       ingresos={"rentas_trabajo_honorarios": ingresos},
                       costos={"otros": 59_000_000}),
            self.par,
        )
        self.assertNotIn("R-09", [c["id"] for c in abajo])

    def test_r09_cita_el_articulo_que_lo_sustenta(self):
        c = self._check("R-09",
                        ingresos={"rentas_trabajo_honorarios": 100_000_000},
                        costos={"otros": 70_000_000})
        self.assertIn("336-1", c["fuente"])
        self.assertEqual(c["severidad"], "alta")

    # ---- R-02 ---------------------------------------------------------

    def test_obl02_no_concluye_sin_saber_si_eres_comerciante(self):
        """Devolvía «NO (perfil de servicios profesionales)» HARDCODEADO, sin
        leer un campo, sobre un hecho que el motor nunca vio. Quien vende
        bienes y supera 30.000 UVT leía «NO» y omitía una obligación real. Y
        era incoherente con OBL-01, que se niega a decir «NO» sin insumos."""
        c = self._check("OBL-02")
        self.assertIn("NO SE PUEDE AFIRMAR", c["estado"])
        self.assertEqual(c["severidad"], "media")

    def test_obl02_concluye_cuando_el_perfil_lo_dice(self):
        no = self._check("OBL-02", contribuyente={"es_comerciante": False})
        self.assertTrue(no["estado"].startswith("NO"))
        self.assertEqual(no["severidad"], "info")

    def test_obl02_avisa_al_comerciante_que_supera_el_tope(self):
        """Las DOS condiciones del art. 368-2 a la vez."""
        arriba = self._check(
            "OBL-02", contribuyente={"es_comerciante": True},
            ingresos={"rentas_trabajo_honorarios": 30_000 * self.uvt})
        self.assertTrue(arriba["estado"].startswith("SÍ"))
        self.assertEqual(arriba["severidad"], "alta")

        debajo = self._check(
            "OBL-02", contribuyente={"es_comerciante": True},
            ingresos={"rentas_trabajo_honorarios": 1_000_000})
        self.assertTrue(debajo["estado"].startswith("NO"))

    def test_r02_se_emite_solo_si_hay_pagos_sin_pila_verificada(self):
        con = self._check("R-02", costos={"pagos_a_contratistas": 48_000_000})
        self.assertEqual(con["severidad"], "alta")
        self.assertIn("108", con["fuente"])

        sin = verificar_obligaciones(
            perfil_con(contribuyente={"anio_gravable": 2025, "residente_fiscal": True},
                       costos={"pagos_a_contratistas": 48_000_000},
                       verificaciones={"contratistas_con_pila_verificada": True}),
            self.par,
        )
        self.assertNotIn("R-02", [c["id"] for c in sin])


# ---------------------------------------------------------------------
# _validar_tarifa — un test por chequeo
# ---------------------------------------------------------------------

TARIFA_2025 = [
    (0, 1090, 0.00, 0), (1090, 1700, 0.19, 0), (1700, 4100, 0.28, 116),
    (4100, 8670, 0.33, 788), (8670, 18970, 0.35, 2296),
    (18970, 31000, 0.37, 5901), (31000, 0, 0.39, 10352),
]


class TestValidarTarifa(unittest.TestCase):
    """`_fusionar` reemplaza las listas enteras: un hijo que declare un solo
    `[[tarifa.rangos]]` borra los otros seis y el motor liquida cero para
    cualquier base. Los cinco chequeos existen por eso, y cuatro estaban
    muertos porque el único test pasaba siempre por el quinto."""

    def _knowledge(self, rangos) -> Path:
        base = Path(tempfile.mkdtemp())
        carpeta = base / "ag2025"
        carpeta.mkdir()
        lineas = ["[meta]", "anio_gravable = 2025", "completo = true", "",
                  "[uvt]", "valor = 49799", 'fuente = "prueba"', "",
                  "[tarifa]", 'fuente = "ET art. 241"', ""]
        for desde, hasta, tarifa, adicional in rangos:
            lineas += ["[[tarifa.rangos]]", f"desde_uvt = {desde}",
                       f"hasta_uvt = {hasta}", f"tarifa = {tarifa}",
                       f"adicional_uvt = {adicional}", ""]
        (carpeta / "parametros.toml").write_text("\n".join(lineas), encoding="utf-8")
        return base

    def _rechaza(self, rangos, fragmento):
        with self.assertRaises(ParametrosNoEncontrados) as ctx:
            P.cargar(2025, knowledge=self._knowledge(rangos))
        self.assertIn(fragmento, str(ctx.exception))

    def test_la_tarifa_buena_si_carga(self):
        """El control. Sin esto, un `raise` incondicional pasaría los seis."""
        par = P.cargar(2025, knowledge=self._knowledge(TARIFA_2025))
        self.assertEqual(len(par.exigir("tarifa.rangos")), 7)

    def test_rechaza_la_tabla_de_un_solo_rango(self):
        """Es exactamente lo que deja una fusión que reemplazó la lista."""
        self._rechaza([(0, 0, 0.39, 0)], "rango(s)")

    def test_rechaza_una_tarifa_escrita_como_porcentaje(self):
        rangos = [(0, 1090, 0.0, 0), (1090, 0, 39, 0)]
        self._rechaza(rangos, "fuera de rango")

    def test_rechaza_tarifas_que_no_crecen(self):
        rangos = [(0, 1090, 0.39, 0), (1090, 0, 0.19, 0)]
        self._rechaza(rangos, "de menor a mayor")

    def test_rechaza_la_ultima_tarifa_en_cero(self):
        """Con esto el impuesto sería cero para cualquier base."""
        rangos = [(0, 1090, 0.0, 0), (1090, 0, 0.0, 0)]
        self._rechaza(rangos, "cero para cualquier base")

    def test_rechaza_un_hueco_entre_rangos(self):
        rangos = [(0, 1090, 0.0, 0), (1700, 0, 0.19, 0)]
        self._rechaza(rangos, "hueco")

    def test_rechaza_una_tabla_que_no_empieza_en_cero(self):
        rangos = [(100, 1090, 0.0, 0), (1090, 0, 0.19, 0)]
        self._rechaza(rangos, "empezar en 0 UVT")

    def test_rechaza_un_ultimo_rango_cerrado(self):
        """Sin rango abierto, una base por encima del último tope no tiene
        tarifa: el motor liquidaría cero justo para el que más debe."""
        rangos = [(0, 1090, 0.0, 0), (1090, 31000, 0.19, 0)]
        self._rechaza(rangos, "abierto")

    def test_rechaza_un_adicional_negativo(self):
        rangos = [(0, 1090, 0.0, 0), (1090, 0, 0.19, -500)]
        self._rechaza(rangos, "adicional_uvt negativo")

    def test_rechaza_la_ausencia_de_tarifa(self):
        base = Path(tempfile.mkdtemp())
        carpeta = base / "ag2025"
        carpeta.mkdir()
        (carpeta / "parametros.toml").write_text(
            "[meta]\nanio_gravable = 2025\n[uvt]\nvalor = 49799\n", encoding="utf-8")
        with self.assertRaises(ParametrosNoEncontrados) as ctx:
            P.cargar(2025, knowledge=base)
        self.assertIn("tarifa.rangos", str(ctx.exception))


# ---------------------------------------------------------------------
# Parametros: conversión, fuente y marca de herencia
# ---------------------------------------------------------------------

class TestParametros(unittest.TestCase):
    def test_cop_multiplica_por_la_uvt(self):
        """Devolver el número de UVT sin multiplicar deja todos los topes
        cuatro órdenes de magnitud por debajo, y el motor recorta
        deducciones que sí procedían."""
        par = P.cargar(2025)
        self.assertEqual(par.cop(1_340), 1_340 * par.uvt)
        self.assertNotEqual(par.cop(1_340), 1_340)
        self.assertEqual(par.cop(0), 0)

    def test_fuente_cita_el_bloque_que_declara_el_valor(self):
        par = P.cargar(2025)
        self.assertIn("241", par.fuente("tarifa.rangos"))
        self.assertEqual(par.fuente("no.existe.nada"), "sin fuente citada")

    def test_un_anio_heredado_avisa_de_lo_que_no_esta_verificado(self):
        """La advertencia de AG2026 es lo único que distingue «parámetro
        verificado» de «copiado del año pasado». Si desaparece, el usuario
        planea 2026 con las cifras de 2025 sin saberlo."""
        par = P.cargar(2026)
        avisos = par.advertencias()
        self.assertTrue(par.heredados, "AG2026 dejó de marcar lo heredado")
        self.assertTrue(any("heredados" in a for a in avisos), avisos)
        self.assertTrue(any("INCOMPLETOS" in a for a in avisos), avisos)
        self.assertFalse(par.completo)

    def test_los_plazos_no_se_heredan(self):
        """Las fechas de ag2025 son para declarar el año gravable 2025.
        Mostrarlas en 2026 no es incompleto, es falso."""
        par = P.cargar(2026)
        self.assertFalse(par.get("plazos.tabla_cargada", False))
        self.assertTrue(any("plazos" in a for a in par.advertencias()))

    def test_un_ciclo_de_herencia_no_cuelga_el_motor(self):
        base = Path(tempfile.mkdtemp())
        for anio, padre in ((2030, "ag2031"), (2031, "ag2030")):
            carpeta = base / f"ag{anio}"
            carpeta.mkdir()
            (carpeta / "parametros.toml").write_text(
                f'[meta]\nanio_gravable = {anio}\nhereda_de = "{padre}"\n'
                f"[uvt]\nvalor = 1\n", encoding="utf-8")
        with self.assertRaises(ParametrosNoEncontrados) as ctx:
            P.cargar(2030, knowledge=base)
        self.assertIn("Ciclo", str(ctx.exception))


# ---------------------------------------------------------------------
# TRM y ledger: las guardas de la capa de datos
# ---------------------------------------------------------------------

class TestSensibilidadDiceLaVerdad(unittest.TestCase):
    """La tabla se titula «cuánto vale cada palanca» y es el número con el
    que la gente decide si desembolsa. El ahorro reportado era
    `max(ahorro_a, ahorro_b)`, y el contribuyente no paga el mejor de los dos
    ahorros: paga el mejor de los dos SALDOS."""

    def setUp(self):
        from engine.depuracion import comparar

        self.par = P.cargar(2025)
        self.r = comparar(perfil_con(
            contribuyente={"anio_gravable": 2025, "residente_fiscal": True},
            ingresos={"rentas_trabajo_honorarios": 900_000_000},
            incrngo={"aportes_obligatorios_salud_pension": 18_000_000},
            deducciones={"dependientes": 2},
        ), self.par)

    def test_el_ahorro_reportado_es_el_que_de_verdad_se_ahorra(self):
        """Se recalcula desde cero: aplicar la palanca y volver a liquidar
        las dos rutas tiene que dar el saldo que la tabla promete."""
        from engine.depuracion import comparar

        self.assertTrue(self.r["sensibilidad"], "el perfil no produjo palancas")
        base = min(self.r["rutas"]["A"].saldo, self.r["rutas"]["B"].saldo)
        for pal in self.r["sensibilidad"]:
            despues = min(pal.saldo_a, pal.saldo_b)
            self.assertAlmostEqual(
                pal.ahorro_max, base - despues, places=0,
                msg=f"{pal.etiqueta}: promete {pal.ahorro_max} y ahorra {base - despues}",
            )
        del comparar

    def test_una_palanca_de_la_ruta_perdedora_no_promete_el_ahorro_de_esa_ruta(self):
        """El caso que producía la sobreestimación: gana B, y la palanca de
        costos solo opera en A. Reportaba los $94.500.000 de A cuando el
        ahorro real es la diferencia contra el saldo de B."""
        self.assertEqual(self.r["mejor_ruta"], "B",
                         "este perfil dejó de ejercitar el caso")
        costos = next(x for x in self.r["sensibilidad"] if "Costos" in x.etiqueta)
        self.assertGreater(costos.ahorro_a, costos.ahorro_max)
        self.assertLess(
            costos.ahorro_max, costos.ahorro_a,
            "la palanca sigue prometiendo el ahorro de la ruta que pierde")

    def test_ninguna_palanca_promete_mas_de_lo_que_hay_por_ahorrar(self):
        """Cota dura: nadie puede ahorrar más que el saldo que se debe."""
        base = min(self.r["rutas"]["A"].saldo, self.r["rutas"]["B"].saldo)
        for pal in self.r["sensibilidad"]:
            self.assertLessEqual(round(pal.ahorro_max), round(max(base, 0)) + 1,
                                 f"{pal.etiqueta} promete más que el saldo entero")


class TestDependientesSoloSobreRentasDeTrabajo(unittest.TestCase):
    """Art. 336 num. 3 inciso 2: «el TRABAJADOR podrá deducir». Y el Decreto
    1625 art. 1.2.1.20.3: «aplican únicamente a los ingresos provenientes de
    rentas de trabajo»."""

    def setUp(self):
        self.par = P.cargar(2025)

    def _renglon(self, perfil, concepto):
        from engine.depuracion import liquidar

        return next(r.valor for r in liquidar(perfil, self.par, "A").renglones
                    if concepto in r.concepto)

    def test_sin_honorarios_no_hay_deduccion_de_dependientes(self):
        p = perfil_con(
            contribuyente={"anio_gravable": 2025, "residente_fiscal": True},
            ingresos={"otras_rentas_no_laborales": 300_000_000},
            deducciones={"dependientes": 4},
        )
        self.assertEqual(self._renglon(p, "Dependientes (72 UVT"), 0)
        self.assertEqual(self._renglon(p, "Dependientes (10%"), 0)

    def test_con_honorarios_si_la_hay(self):
        """El control: la guarda no puede tragarse el caso normal."""
        p = perfil_con(
            contribuyente={"anio_gravable": 2025, "residente_fiscal": True},
            ingresos={"rentas_trabajo_honorarios": 300_000_000},
            deducciones={"dependientes": 4},
        )
        self.assertGreater(
            self._renglon(p, "Dependientes (72 UVT")
            + self._renglon(p, "Dependientes (10%"), 0)


class TestCitasNormativas(unittest.TestCase):
    """La cita que ve el contador es la del MOTOR, no la de knowledge/.

    Las dos podían divergir porque la cifra salía de
    `knowledge/<año>/parametros.toml` y la cita de un literal en Python. La
    ronda 5 encontró tres divergencias sobre el mismo número —prepagada,
    dependientes de 72 UVT y el 1% de factura electrónica—, y en las tres la
    del motor apuntaba a una norma distinta de la verificada.
    """

    def _citas_de_knowledge(self, anio: int) -> set[str]:
        import tomllib

        ruta = RAIZ / "knowledge" / f"ag{anio}" / "parametros.toml"
        with open(ruta, "rb") as f:
            datos = tomllib.load(f)
        citas: set[str] = set()

        def recorrer(nodo):
            if isinstance(nodo, dict):
                if isinstance(nodo.get("fuente"), str):
                    citas.add(nodo["fuente"])
                for v in nodo.values():
                    recorrer(v)
            elif isinstance(nodo, list):
                for v in nodo:
                    recorrer(v)

        recorrer(datos)
        return citas

    # Renglones cuya norma no tiene bloque propio en parametros.toml porque
    # no llevan una cifra parametrizable: son la estructura de la cédula.
    SIN_BLOQUE = {
        "ET art. 335 y art. 103", "ET art. 338", "ET art. 340",
        "ET arts. 55 y 56", "ET art. 336 num. 4",
        "ET art. 206 num. 10, mod. Ley 2277 de 2022 art. 2",
        "ET art. 373", "ET art. 815",
    }

    def test_ningun_renglon_cita_una_norma_que_knowledge_no_declare(self):
        from engine.depuracion import liquidar

        citas = self._citas_de_knowledge(2025)
        par = P.cargar(2025)
        p = PF.cargar(RAIZ / "expediente.ejemplo")
        divergentes = []
        for ruta in ("A", "B"):
            for renglon in liquidar(p, par, ruta).renglones:
                if not renglon.fuente:
                    continue
                if renglon.fuente in citas or renglon.fuente in self.SIN_BLOQUE:
                    continue
                divergentes.append((renglon.concepto, renglon.fuente))
        self.assertEqual(
            divergentes, [],
            "estos renglones citan una norma que knowledge/ no declara; si la "
            "cifra sale de parametros.toml, la cita también tiene que salir de "
            "ahí (ver _fuente en depuracion.py)",
        )

    def test_los_tres_renglones_que_divergian_citan_lo_mismo_que_knowledge(self):
        from engine.depuracion import liquidar

        par = P.cargar(2025)
        p = PF.cargar(RAIZ / "expediente.ejemplo")
        por_concepto = {r.concepto: r.fuente
                        for r in liquidar(p, par, "A").renglones}
        for concepto, bloque in (
            ("− Medicina prepagada", "topes.medicina_prepagada"),
            ("− Dependientes (72 UVT c/u — FUERA del tope)",
             "topes.dependientes_72uvt"),
            ("− Deducción 1% compras con factura electrónica",
             "topes.deduccion_1pct_factura_electronica"),
        ):
            self.assertEqual(por_concepto[concepto], par.get(f"{bloque}.fuente"),
                             f"{concepto} cita algo distinto de {bloque}")

    def test_un_ano_sin_fuente_declarada_cae_al_respaldo_y_no_a_vacio(self):
        """Un renglón sin cita es peor que uno con cita imperfecta: el
        contador no tiene por dónde empezar a verificar."""
        from engine.depuracion import _fuente

        par = P.Parametros({"uvt": {"valor": 100}}, set(), 2025)
        self.assertEqual(_fuente(par, "topes.gmf.porcentaje_deducible",
                                 "ET art. 115"), "ET art. 115")


class TestGuardasDeTRM(unittest.TestCase):
    def setUp(self):
        self.dia = date(2025, 3, 14)
        self.trm = TRM({self.dia: 4_000.0})

    def test_retrocede_hasta_una_semana_y_ni_un_dia_mas(self):
        """El art. 288 exige la TRM de la fecha de realización. Retroceder al
        último día hábil es correcto; rellenar un hueco de cuarenta días es
        inventar el dato. El límite tiene que estar probado en su borde."""
        self.assertEqual(self.trm.de(self.dia + timedelta(days=7)), 4_000.0)
        with self.assertRaises(SinTRM):
            self.trm.de(self.dia + timedelta(days=8))

    def test_cada_dia_suplido_queda_registrado(self):
        self.trm.de(self.dia + timedelta(days=2))
        self.assertIn(self.dia + timedelta(days=2), self.trm.suplidas)

    def test_un_hueco_largo_se_reporta_y_uno_de_fin_de_semana_no(self):
        self.trm.de(self.dia + timedelta(days=1))       # sábado
        self.assertEqual(self.trm.huecos_grandes(dias=3), [])
        self.trm.de(self.dia + timedelta(days=6))
        self.assertTrue(self.trm.huecos_grandes(dias=3))

    def test_para_no_construye_la_serie_si_la_descarga_dejo_huecos(self):
        """La fuente puede devolver un rango parcial. Sin este chequeo el
        objeto se construía igual y `de()` rellenaba hacia atrás sin avisar."""
        import engine.trm as T

        original = T.descargar
        T.descargar = lambda desde, hasta, timeout=30: {desde: 4_000.0}
        try:
            with self.assertRaises(SinTRM):
                T.TRM.para(date(2025, 1, 1), date(2025, 12, 31), cache=None)
        finally:
            T.descargar = original

    def test_sin_red_y_sin_cache_es_error_explicito(self):
        with self.assertRaises(SinTRM) as ctx:
            TRM.para(date(2025, 1, 1), date(2025, 1, 5), cache=None,
                     permitir_red=False)
        self.assertIn("red está desactivada", str(ctx.exception))

    def test_sin_red_acepta_un_cache_de_solo_dias_habiles(self):
        """La fuente oficial no publica fines de semana, así que un caché
        COMPLETO tiene huecos por definición. Exigir todos los días
        calendario hacía que `--sin-red` fuera inutilizable sin haber estado
        en línea: bastaba que el rango tocara un sábado."""
        import tempfile

        from engine.trm import escribir_cache

        habiles = {date(2025, 3, d): 4_000.0 for d in (13, 14, 17, 18)}
        cache = Path(tempfile.mkdtemp()) / "trm-cache.csv"
        escribir_cache(cache, habiles)

        trm = TRM.para(date(2025, 3, 14), date(2025, 3, 17), cache=cache,
                       permitir_red=False)
        self.assertEqual(trm.de(date(2025, 3, 15)), 4_000.0)   # sábado
        self.assertTrue(trm.desde_cache)

    def test_sin_red_sigue_fallando_con_un_hueco_de_verdad(self):
        """El arreglo no puede volverse una puerta: un mes sin datos sigue
        siendo un caché que no sirve."""
        import tempfile

        from engine.trm import escribir_cache

        cache = Path(tempfile.mkdtemp()) / "trm-cache.csv"
        escribir_cache(cache, {date(2025, 3, 14): 4_000.0})
        with self.assertRaises(SinTRM) as ctx:
            TRM.para(date(2025, 3, 14), date(2025, 4, 30), cache=cache,
                     permitir_red=False)
        self.assertIn("no cubre", str(ctx.exception))


class TestCacheDeTRM(unittest.TestCase):
    def _escribir(self, contenido: str) -> Path:
        import tempfile

        ruta = Path(tempfile.mkdtemp()) / "trm-cache.csv"
        ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def test_se_acepta_el_export_crudo_de_datos_gov_co(self):
        """Los mensajes de SinTRM mandan a descargar la serie de esa fuente
        y guardarla como CSV. El archivo que el usuario obtiene tiene
        columnas `valor,vigenciadesde` y se rechazaba: el remedio que la
        herramienta ofrece no funcionaba."""
        from engine.trm import leer_cache

        serie, avisos = leer_cache(self._escribir(
            "valor,vigenciadesde,vigenciahasta\n4409.15,2025-01-02,2025-01-02\n"))
        self.assertEqual(serie[date(2025, 1, 2)], 4409.15)
        self.assertEqual(avisos, [])

    def test_una_fecha_duplicada_con_valores_distintos_avisa(self):
        """Ganaba la última, en silencio, y las dos son plausibles: nada
        delata cuál es la buena. Una TRM equivocada multiplica el ingreso de
        ese día."""
        from engine.trm import leer_cache

        serie, avisos = leer_cache(self._escribir(
            "fecha,trm\n2025-01-02,4409.15\n2025-01-02,3000.00\n"))
        self.assertEqual(serie[date(2025, 1, 2)], 4409.15)
        self.assertTrue(any("dos veces" in a for a in avisos), avisos)


class TestEntradasPorFuente(unittest.TestCase):
    """Alimenta la cifra de consignaciones del umbral de IVA. Si cuenta las
    SALIDAS, el numerador del art. 437 par. 3 num. 6 se infla con dinero que
    salió, y alguien se inscribe como responsable de IVA sin deberlo."""

    def _ledger(self):
        return Ledger([
            Movimiento(date(2025, 3, 1), "giro", 50_000_000, "COP",
                       "ingreso_trabajo", fuente="deel.csv"),
            Movimiento(date(2025, 3, 2), "retiro", -30_000_000, "COP",
                       "traslado", fuente="deel.csv"),
            Movimiento(date(2025, 3, 3), "abono", 30_000_000, "COP",
                       "traslado", fuente="banco.csv"),
        ]).convertir(None)

    def test_solo_suma_las_entradas(self):
        por_fuente = self._ledger().entradas_por_fuente()
        self.assertEqual(por_fuente["deel.csv"], 50_000_000)
        self.assertEqual(por_fuente["banco.csv"], 30_000_000)

    def test_el_total_no_incluye_el_valor_absoluto_de_las_salidas(self):
        cons = self._ledger().consignaciones()
        self.assertEqual(cons["entradas_brutas"], 80_000_000)
        self.assertNotEqual(cons["entradas_brutas"], 110_000_000)

    def test_nunca_se_declara_listo_para_el_umbral(self):
        cons = self._ledger().consignaciones()
        self.assertFalse(cons["listo_para_el_umbral"])
        self.assertTrue(any("gravada" in a for a in cons["avisos"]))


class TestAvisoDeMezclaDeAnios(unittest.TestCase):
    def test_un_ledger_con_dos_anios_avisa(self):
        ledger = Ledger([
            Movimiento(date(2024, 12, 31), "a", 100, "COP", "ingreso_trabajo"),
            Movimiento(date(2025, 1, 1), "b", 200, "COP", "ingreso_trabajo"),
        ]).convertir(None)
        self.assertTrue(any("mezcla los años" in a for a in ledger.validar()))

    def test_un_ledger_de_un_solo_anio_no_avisa(self):
        ledger = Ledger([
            Movimiento(date(2025, 1, 1), "b", 200, "COP", "ingreso_trabajo"),
        ]).convertir(None)
        self.assertFalse(any("mezcla los años" in a for a in ledger.validar()))


if __name__ == "__main__":
    unittest.main()


class TestPlantillasContraElMotor(unittest.TestCase):
    """Las plantillas no pueden pedir aritmética que el motor no emite.

    `AGENTS.md` regla 1: «la aritmética la hace el motor, no tú». Tres
    plantillas la rompían por omisión: pedían UNA casilla de «Deducciones» y
    el motor emitía cinco renglones sueltos sin su suma, así que quien
    llenaba la plantilla tenía que sumarlos a mano — sobre las cifras que van
    al formulario.

    Este test cierra la CLASE: cada fila de la tabla del comparativo tiene
    que corresponder a un renglón que el motor emite de verdad.
    """

    TEMPLATES = RAIZ / "templates"

    def _renglones(self) -> list[str]:
        from engine.depuracion import liquidar

        par = P.cargar(2025)
        p = PF.cargar(RAIZ / "expediente.ejemplo")
        return [r.concepto for r in liquidar(p, par, "A").renglones]

    # Filas del comparativo que NO son un renglón: son metadatos de la tabla
    # o cifras que el motor publica por otra vía, con su nombre.
    FILAS_QUE_NO_SON_RENGLON = {
        "Concepto": "encabezado de la tabla",
        "Impuesto (art. 241)": "IMPUESTO SOBRE LA RENTA",
        "− Descuentos": "− Descuento por donaciones",
        "− Retenciones": "− Retenciones practicadas en el año",
        "= **Saldo a {{pagar/favor}}**": "= SALDO A PAGAR / A FAVOR",
        "− INCRNGO": "− Ingresos no constitutivos de renta (INCRNGO)",
        "Ingresos brutos cédula general": "= Total ingresos brutos cédula general",
        "= Ingresos netos": "= Ingresos netos (base del límite del 40%)",
        "− Costos y gastos": "− Costos y gastos procedentes",
        "− Renta exenta 25%": "− Renta exenta 25%",
        "− Deducciones dentro del tope": "  = Subtotal deducciones dentro del tope",
        "− Deducciones fuera del tope": "  = Subtotal deducciones fuera del tope",
        "[tope 40% / 1.340 UVT]": "  [tope conjunto 40% / 1.340 UVT]",
        "[rechazado por el tope]": "  [rechazado por el tope]",
        "[costos rechazados por el tope por tipo de renta]":
            "  [costos rechazados por el tope por tipo de renta]",
        "= **Renta líquida gravable**": "= RENTA LÍQUIDA GRAVABLE",
    }

    def _filas_del_comparativo(self) -> list[str]:
        texto = (self.TEMPLATES / "comparativo.md").read_text(encoding="utf-8")
        filas = []
        for linea in texto.splitlines():
            if not linea.startswith("| ") or set(linea) <= set("|- "):
                continue
            primera = linea.split("|")[1].strip()
            if primera:
                filas.append(primera)
            # Solo la primera tabla: las de palancas y supuestos no son
            # renglones de la depuración.
            if primera.startswith("= **Saldo"):
                break
        return filas

    def test_cada_fila_del_comparativo_existe_como_renglon(self):
        renglones = self._renglones()
        huerfanas = []
        for fila in self._filas_del_comparativo():
            equivalente = self.FILAS_QUE_NO_SON_RENGLON.get(fila)
            if equivalente is None:
                huerfanas.append(f"{fila!r} no está en el mapa de equivalencias")
            elif (equivalente not in renglones
                  and not equivalente.startswith("encabezado")
                  and not equivalente.startswith("= SALDO")):
                huerfanas.append(f"{fila!r} → {equivalente!r} no lo emite el motor")
        self.assertEqual(
            huerfanas, [],
            "el comparativo pide cifras que el motor no emite; o el motor "
            "emite el subtotal, o la plantilla deja de pedirlo",
        )

    def test_el_subtotal_de_deducciones_cuadra_con_sus_renglones(self):
        """El subtotal tiene que ser la suma de los renglones que dice
        sumar, no una cifra parecida."""
        from engine.depuracion import liquidar

        par = P.cargar(2025)
        p = PF.cargar(RAIZ / "expediente.ejemplo")
        for ruta in ("A", "B"):
            por_concepto = {r.concepto: r.valor
                            for r in liquidar(p, par, ruta).renglones}
            partes = sum(por_concepto[c] for c in (
                "− GMF deducible (50% del 4x1000 pagado)",
                "− Intereses de vivienda",
                "− Medicina prepagada",
                "− Aportes voluntarios AFP / AFC",
                "− Dependientes (10% renta de trabajo)",
            ))
            self.assertEqual(
                por_concepto["  = Subtotal deducciones dentro del tope"], partes,
                f"ruta {ruta}: el subtotal no es la suma de sus renglones",
            )
            fuera = sum(por_concepto[c] for c in (
                "− Dependientes (72 UVT c/u — FUERA del tope)",
                "− Deducción 1% compras con factura electrónica",
            ))
            self.assertEqual(
                por_concepto["  = Subtotal deducciones fuera del tope"], fuera,
                f"ruta {ruta}: el subtotal de fuera no cuadra",
            )

    def test_ninguna_plantilla_pide_una_cifra_sin_decir_de_donde_sale(self):
        """`checklist-documentos.md` pedía un `{{$X}}` de «PILA de cada
        contratista habilita X en Ruta A» que no existía en ninguna salida.
        Cada `{{$X}}` de esa plantilla tiene que venir con su origen."""
        texto = (self.TEMPLATES / "checklist-documentos.md").read_text(
            encoding="utf-8")
        self.assertIn("R-02", texto,
                      "la cifra de contratistas no dice de dónde sale")
        self.assertIn("costos.pagos_a_contratistas", texto)
