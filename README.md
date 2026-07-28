<div align="center">

# renta-co

**Tu declaración de renta en Colombia, hecha por tu agente de código.**

Suelta tus extractos en una carpeta. Contesta unas preguntas.
Sale el borrador del Formulario 210, las dos rutas de depuración comparadas en pesos,
la deducción que te estabas perdiendo y el memo para tu contador.

[![verificar](https://github.com/justinalejandro369-star/renta-co/actions/workflows/verificar.yml/badge.svg)](https://github.com/justinalejandro369-star/renta-co/actions/workflows/verificar.yml)
[![licencia MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![sin dependencias](https://img.shields.io/badge/dependencias-0-brightgreen.svg)](#por-qué-cero-dependencias)

[Instalación](#instalación) · [Cómo funciona](#cómo-funciona) · [Por qué existe](#por-qué-existe) · [Privacidad](PRIVACY.md) · [Aviso legal](DISCLAIMER.md)

</div>

---

## Instalación

**Claude Code**

```bash
/plugin marketplace add justinalejandro369-star/renta-co
/plugin install renta-co
```

**Codex CLI**

```bash
codex plugin marketplace add justinalejandro369-star/renta-co
codex plugin add renta-co@renta-co
```

**Cualquier otro agente** (Cursor, Gemini CLI, OpenCode, Cline — todo lo que lea `AGENTS.md`)

```bash
git clone https://github.com/justinalejandro369-star/renta-co
cd renta-co
```

Requiere Python 3.11 o superior. **Cero dependencias externas.**

---

## Uso

```
/renta-co:setup
```

Crea `./expediente/` en tu máquina —ya ignorado por git— y te hace cuatro preguntas.

> Arrastra **todo** a `expediente/00-crudo/`: extractos, certificados, PDFs, ZIPs.
> **No los ordenes ni los renombres.**

```
"listo, ya cargué todo"
```

El agente abre cada archivo, lo identifica, lo renombra, lo archiva por entidad, extrae las cifras que sirven y te dice qué no pudo leer y qué falta. Después te entrevista solo sobre lo que no logró deducir de los documentos.

```
expediente/
├── 00-crudo/          lo que soltaste, intacto
├── 01-soportes/       clasificado por entidad y concepto
├── 02-datos/          ledger con TRM diaria, movimiento por movimiento
├── 03-analisis/       comparativo de rutas + tabla de sensibilidad
├── 04-entregables/    checklist · memo al contador · borrador 210
└── 05-riesgos/        registro de riesgos con severidad y mitigación
```

Antes de compartir cualquier cosa con quien sea:

```
/renta-co:privacidad
```

Escanea las salidas y te dice archivo y línea donde quedó una cédula, un número de cuenta o un nombre. Enmascarado.

---

## Cómo funciona

<table>
<tr><td width="50%" valign="top">

### El agente conduce
Diez skills que saben **qué preguntar, en qué orden y por qué**. No un formulario: una conversación que sabe que la pregunta de dependientes vale millones y la de intereses de tarjeta no vale nada.

</td><td width="50%" valign="top">

### El motor calcula
Python determinista con 64 tests y un benchmark de 14 personas verificado en tres capas. **El modelo de lenguaje nunca hace la aritmética del impuesto.** Puedes leer `engine/depuracion.py` y recalcularlo a mano.

</td></tr>
<tr><td valign="top">

### El conocimiento está citado
Cada UVT, tope, tarifa y umbral vive en `knowledge/<año>/parametros.toml` **con su resolución o artículo**. Un test falla si alguien mete una cifra sin fuente.

</td><td valign="top">

### Los datos no se mueven
El plugin es código. Tu expediente es tuyo y vive en tu proyecto, fuera de git desde el primer segundo. Sin telemetría, sin cuenta, sin backend.

</td></tr>
</table>

---

## Por qué existe

La DIAN te manda una **declaración sugerida** armada con lo que terceros reportaron sobre ti. Es cómoda y es sistemáticamente peor que la que te corresponde: no conoce tus dependientes, no conoce tus costos, y no elige la ruta de depuración que te conviene. Un contador cobra entre $300.000 y $1.000.000, y en el caso de quien cobra en dólares muchos no dominan ni la TRM diaria ni el art. 336 num. 4.

Este proyecto ataca el caso más difícil y peor atendido: **el freelance con ingresos del exterior.**

| El problema | Lo que hace `renta-co` |
|---|---|
| Cobras en USD por Deel, Wise o Payoneer | Convierte cada movimiento a la **TRM de su fecha** (art. 288 ET), no a un promedio. En 2025 la TRM osciló 19%: el atajo mueve la base en millones |
| El export mezcla pagos, retiros y conversiones | Clasifica los **traslados** como lo que son. Sumar todo lo positivo triplica tu ingreso, y es el error más común al importar a mano |
| Tienes que elegir entre costos y el 25% exento | Calcula **las dos rutas** y te dice la diferencia en pesos. Son excluyentes (art. 336 num. 4 ET) |
| Nadie te retuvo nada | Te lo dice antes de que sea sorpresa, y confirma que **no eras agente de retención** (art. 368-2 ET exige ser comerciante *y* superar 30.000 UVT) |
| Le pagas a un equipo | Levanta el requisito que tumba más deducciones: verificar los aportes del contratista (art. 108 par. 2 ET) |
| Por tu cuenta pasa plata de clientes | Trabaja el umbral de **consignaciones** de 3.500 UVT, con su calificador: solo cuenta lo proveniente de actividades gravadas con IVA |

---

## Lo que lo hace distinto

### Te dice cuánto vale cada papel, en pesos

No una lista de deducciones posibles. El peso exacto que ahorra cada una **en tu caso**, ordenada de mayor a menor. Así sabes qué certificado vale la pena perseguir el sábado por la mañana y cuál no sirve para nada porque el tope ya está saturado.

```
CUÁNTO VALE CADA PALANCA — impuesto ahorrado, en pesos
────────────────────────────────────────────────────────────────────
PALANCA                                        RUTA A        RUTA B
────────────────────────────────────────────────────────────────────
Acreditar 4 dependiente(s) — hoy tienes 0   $4.015.791    $4.015.791
      FUERA del tope del 40%. No exige factura ni desembolso: se
      acredita la condición. Padres y hermanos con ingresos anuales
      < 260 UVT cuentan.
```

### Encuentra lo que nadie mira

El umbral de **consignaciones** de 3.500 UVT se mide sobre lo que entró a tus cuentas, no sobre tu ingreso propio: quien recibe plata de clientes y la redistribuye puede pasarse sin que su ingreso se acerque. Si te pasas, pierdes la calidad de no responsable de IVA y aparecen obligación de facturar, declaraciones de IVA y sanción por cada una omitida.

Y trae el calificador que casi nadie cita: el art. 437 par. 3 num. 6 habla de consignaciones **provenientes de actividades gravadas con IVA**. Los traslados entre cuentas propias no cuentan, y si tu actividad es exportación de servicios la cifra relevante puede ser cero. `renta-co` te ayuda a separarlo **antes** de que presentes, en vez de darte una alarma falsa.

### Registra los riesgos en vez de esconderlos

Ocho riesgos del perfil freelance, con fundamento normativo, probabilidad de objeción y mitigación. Cuando una posición es agresiva pero defendible, queda por escrito con su nivel, para que la decisión se tome informada.

### El criterio, explícito

> Se documentan operaciones reales con fechas y montos reales, y se toman **todas** las deducciones y descuentos que la ley permite. No se antedatan documentos, no se inventan gastos, no se ocultan ingresos.

Si le pides lo contrario, no lo hace.

---

## Las diez skills

| Skill | Para qué |
|---|---|
| `renta-onboarding` | Punto de entrada. Crea el expediente y conduce todo el proceso |
| `renta-clasificar` | Identifica, renombra y archiva los documentos que soltaste |
| `renta-ingresos` | Clasifica ingresos y aplica TRM diaria a la moneda extranjera |
| `renta-patrimonio` | Activos y pasivos a 31 de diciembre, y la ecuación patrimonial |
| `renta-deducciones` | Encuentra todo lo que se puede restar, en orden de pesos |
| `renta-rutas` | Decide entre costos y renta exenta del 25%, con números |
| `renta-riesgos` | Registro de riesgos antes de cerrar nada |
| `renta-entregables` | Checklist, comparativo, memo al contador, borrador del 210 |
| `renta-planeacion` | El año en curso, que es donde todavía se puede cambiar algo |
| `renta-privacidad` | Escaneo de datos personales antes de compartir o commitear |

**Comandos:** `/renta-co:setup` · `/renta-co:auditar` · `/renta-co:estado` · `/renta-co:privacidad`

---

## Probarlo ahora mismo, sin exponer nada

```bash
git clone https://github.com/justinalejandro369-star/renta-co
cd renta-co
python3 -m engine.cli calcular --expediente expediente.ejemplo
```

Contribuyente ficticio, flujo completo, cifras redondas. Fíjate en tres cosas: la Ruta A gana pero **la elección de ruta no es lo importante**, el riesgo R-01 sale en rojo, y el motor escoge entre las dos vías de dependientes calculando ambas.

También sirve de test de regresión:

```bash
make verificar          # tests + ejemplo + escaneo de privacidad
```

---

## Privacidad

Los datos y el código viven separados, físicamente. `renta-co` es lo que instalas; `./expediente/` es tuyo y nunca entra al árbol del plugin.

**Lo único que sale a la red** es un rango de fechas a `datos.gov.co` para bajar la serie TRM del Banco de la República, que es pública. Se cachea y después funciona sin red. Sin telemetría, sin analytics, sin cuenta, sin backend.

`PRIVACY.md` dice también lo que casi nadie dice: **el contenido de tus documentos pasa por el modelo de lenguaje que estés usando**, bajo los términos que ya aceptaste con tu proveedor. `renta-co` no controla eso. Si te preocupa, el motor corre entero sin modelo.

Además: `.gitignore` generado en el setup, escáner de PII con enmascaramiento, hook opcional de pre-commit que lee el índice de git, y CI que escanea el árbol y las líneas que cada PR agrega a la historia.

El escáner es una heurística con límites declarados —no lee PDF ni XLSX, y clasifica por confianza para no ahogarte en falsos positivos—. Es una red de seguridad, no una prueba de ausencia. `PRIVACY.md` los enumera.

→ [PRIVACY.md](PRIVACY.md)

---

## Lo que NO hace

- **No presenta nada ante la DIAN.** No se conecta al MUISCA, no tiene tu firma electrónica, no radica declaraciones.
- **No es asesoría tributaria.** El memo al contador es un entregable de primera clase, no un extra. → [DISCLAIMER.md](DISCLAIMER.md)
- No cubre todavía: personas jurídicas, Régimen Simple, rentas de pensiones, ganancia ocasional.
- No trae la tabla de plazos día por día. **A propósito**: exige el decreto oficial y una fecha adivinada cuesta una sanción del 5% mensual. El motor te manda a verificarla.

---

## Por qué cero dependencias

Es una promesa, no una preferencia estética. Esta herramienta calcula cuánto le debes al Estado: cualquiera tiene que poder auditar el cálculo con un Python limpio, sin instalar nada de nadie. `tomllib` es stdlib desde 3.11 y con eso alcanza.

---

## Contribuir

Lo que más falta, en orden:

1. **Adaptadores de bancos y plataformas.** Son ~40 líneas. Faltan Davivienda, BBVA, Nu, Nequi, Daviplata, Payoneer, PayPal, Upwork, Binance.
2. **Años gravables y cambios normativos.** `knowledge/` está versionado por año justamente para eso. Cada cifra necesita su fuente; hay un test que lo verifica.
3. **Casos de prueba.** Perfiles distintos (asalariado, mixto, arrendador) con el resultado calculado a mano contra la norma.

→ [CONTRIBUTING.md](CONTRIBUTING.md)

Si cambió una norma, abre un issue con la resolución.

---

## Hacia dónde va

- `knowledge/ag2026` completo · Régimen Simple modelado · ganancia ocasional
- Perfiles de asalariado y mixto
- `renta-mx` (SAT / RESICO) sobre el mismo motor, y de ahí al resto de Latinoamérica

---

## Licencia

MIT. Ver [LICENSE](LICENSE).

<div align="center">
<sub>Hecho para la gente que factura en dólares y declara en pesos.</sub>
</div>
