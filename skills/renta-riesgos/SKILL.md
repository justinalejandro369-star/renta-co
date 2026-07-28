---
name: renta-riesgos
description: Levanta el registro de riesgos de la declaración, con fundamento normativo, severidad, probabilidad de objeción y mitigación. Úsala antes de cerrar cualquier declaración, cuando haya una posición discutible, o cuando el usuario pregunte qué tan riesgoso es algo, si lo pueden fiscalizar, o por sanciones, IVA, UGPP o la DIAN.
---

# Registro de riesgos

Toda declaración tiene posiciones que la DIAN podría objetar. El punto no es evitarlas todas: es **tomarlas informado y dejarlo por escrito**.

Escribe el resultado en `expediente/05-riesgos/riesgos.md`. Formato en `templates/riesgos.md`.

## Catálogo base del perfil freelance

Evalúa los ocho, siempre. Los que no apliquen se marcan como no aplicables, no se omiten — así el contador ve que se miraron.

### R-01 · Pérdida de la calidad de no responsable de IVA por consignaciones
**Severidad ALTA · La más subestimada de todas.**

El umbral de 3.500 UVT ($174.296.500 en 2025) se mide sobre **consignaciones**, no sobre ingresos propios. Quien recibe plata de clientes y la redistribuye, o mueve dinero entre sus propias cuentas, puede superarlo sin que su ingreso lo haga.

**Consecuencia:** obligación de inscribirse como responsable de IVA, facturar, declarar IVA por período, y sanción por extemporaneidad de **cada** declaración omitida. Puede costar más que el propio impuesto de renta.

**Mitigación:** sumar el total consignado del año con los extractos completos de **todas** las cuentas. Si se supera, evaluar si la actividad califica como exportación de servicios exenta (art. 481 lit. c ET), lo que deja el IVA en 0% aunque obligue a declarar. **Resolverlo antes de presentar renta, no después.**

### R-02 · Rechazo de costos por falta de verificación de aportes del contratista
**Severidad ALTA · Solo Ruta A**

Art. 108 par. 2 ET: el contratante debe verificar la afiliación y el pago de aportes a seguridad social del contratista. Si no cotizó, la DIAN puede rechazar **la totalidad** del costo.

**Mitigación:** planilla PILA de cada persona, de los meses trabajados. Si no cotizaron, la Ruta A pierde su fundamento y la Ruta B pasa a ser la correcta — no por conveniencia, sino porque el costo no es deducible.

### R-03 · Objeción al documento soporte generado extemporáneamente
**Severidad MEDIA · Solo Ruta A**

La Resolución DIAN 000167 de 2021 permite generar el documento soporte **en físico** mientras la DIAN no exija la versión electrónica. Eso habilita construir hoy el soporte de pagos ya hechos.

La DIAN puede argumentar que debía existir al momento de la operación. Es discutible: la sustancia está probada con extractos verificables.

**Mitigación:** expediente completo — contrato o acuerdo con fechas reales, cuenta de cobro firmada por cada pago, documento soporte con numeración consecutiva, y el extracto de cada transferencia.

**Línea que no se cruza:** fechas y montos van tal como ocurrieron. Documentar tarde una operación real es cumplimiento tardío de un deber formal. Cambiar fechas o inflar montos es falsedad en documento privado.

### R-04 · Ingreso subdeclarado
**Severidad ALTA**

Si parte del ingreso es estimado y no soportado, hay riesgo. Las plataformas reportan a las autoridades y la DIAN cruza información. Sanción por inexactitud: **100% de la diferencia** del impuesto (art. 648 ET).

**Mitigación:** reporte anual completo de cada fuente de ingreso. Es innegociable.

### R-05 · Patrimonio bruto subdeclarado
**Severidad MEDIA-ALTA**

Activos omitidos que la DIAN detecte se gravan como renta líquida gravable sin derecho a costo (art. 239-1 ET), más sanción. Y la ecuación patrimonial dispara la presunción de ingresos omitidos.

**Mitigación:** certificado de saldo a 31-dic de **cada** cuenta, wallet, exchange y broker. Ver `renta-patrimonio`.

### R-06 · Exposición ante la UGPP por aportes propios
**Severidad MEDIA-ALTA · Fuera del alcance de la declaración**

Un independiente debe cotizar a salud y pensión sobre el 40% de sus ingresos. La UGPP fiscaliza con sus propios términos y sanciones, y cruza información con las declaraciones de renta.

**Mitigación:** frente separado, con asesoría específica. **No se oculta en la declaración** — declarar ingresos de independiente sin aportes correlativos es exactamente lo que dispara el cruce. Ocultar el ingreso para evitar el cruce cambia un problema por uno peor.

### R-07 · Deducciones improcedentes que se cuelan
**Severidad BAJA-MEDIA**

Partidas que parecen deducibles y no lo son: intereses de tarjeta de crédito, consumos personales, traslados entre cuentas propias contados como ingreso, donaciones sin certificado del RTE, abono a capital del crédito de vivienda.

**Mitigación:** lista explícita en el memo al contador, para contrastar renglón por renglón.

### R-08 · TRM promedio en vez de TRM diaria
**Severidad BAJA, pero cuantificable**

Art. 288 ET exige TRM de la fecha de cada operación. Un promedio anual mueve la base en millones cuando la TRM osciló 19% en el año.

**Mitigación:** el ledger ya aplica TRM diaria. Si el contador usó promedio, reconciliar y documentar la diferencia.

## Cómo escribir cada riesgo

```markdown
## R-0X · <título>
**Severidad: ALTA|MEDIA|BAJA · Probabilidad: ALTA|MEDIA|BAJA · Estado: <estado>**

<Qué pasa, en dos frases, con la norma citada.>

**Si se materializa:** <consecuencia concreta en pesos cuando se pueda.>

**Mitigación:** <qué hacer, con qué documento, en qué orden.>
```

Cierra con la tabla resumen ordenada por severidad.

## Regla de honestidad

Si una posición es agresiva, **dilo**. No la escondas en la mitigación. La persona tiene derecho a saber que está tomando un riesgo y de qué tamaño, para decidir. Un registro de riesgos que solo tranquiliza no sirve de nada.

Si el usuario pide ocultar un ingreso, antedatar un documento o inventar un gasto: **no**, en una frase, sin sermón. Después ofrece lo que sí funciona: la deducción legal que no había mirado, o la planeación del año en curso.
