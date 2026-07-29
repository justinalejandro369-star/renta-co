---
name: renta-riesgos
description: Levanta el registro de riesgos de la declaración, con fundamento normativo, severidad, probabilidad de objeción y mitigación. Úsala antes de cerrar cualquier declaración, cuando haya una posición discutible, o cuando el usuario pregunte qué tan riesgoso es algo, si lo pueden fiscalizar, o por sanciones, IVA, UGPP o la DIAN.
---

# Registro de riesgos

Toda declaración tiene posiciones que la DIAN podría objetar. El punto no es evitarlas todas: es **tomarlas informado y dejarlo por escrito**.

Escribe el resultado en `expediente/05-riesgos/riesgos.md`. Formato en `templates/riesgos.md`.

## Catálogo base del perfil freelance

Evalúa los **dieciséis**, siempre. Los que no apliquen se marcan como no aplicables, no se omiten — así el contador ve que se miraron.

**R-01, R-02, R-09, R-10 y R-11 los emite el motor** con los datos del perfil (`bin/renta calcular`), así que esos cinco llegan ya evaluados: cópialos de la salida, no los redactes de nuevo. Los otros seis los levantas tú.

> Si `calcular` imprime un `R-xx` que no está en esta lista, **no lo omitas del entregable**: agrégalo con lo que diga el motor y repórtalo como catálogo desactualizado. Un riesgo que el motor detecta y el `riesgos.md` no menciona es el error invisible de este proyecto — queda dicho en la conversación y no queda escrito en el expediente.

### R-01 · Pérdida de la calidad de no responsable de IVA por consignaciones
**Severidad ALTA · La más subestimada de todas.**

El umbral de 3.500 UVT ($174.296.500 en 2025) se mide sobre **consignaciones**, no sobre ingresos propios. Quien recibe plata de clientes y la redistribuye, o mueve dinero entre sus propias cuentas, puede superarlo sin que su ingreso lo haga.

**Consecuencia:** obligación de inscribirse como responsable de IVA, facturar, declarar IVA por período, y sanción por **cada** declaración omitida — la del **art. 643 (no declarar)** si nunca se presentaron, que es más gravosa que la del 641 por extemporaneidad. Puede costar más que el propio impuesto de renta.

**Mitigación:** sumar el total consignado del año con los extractos completos de **todas** las cuentas. Si se supera, evaluar si la actividad califica como exportación de servicios exenta (art. 481 lit. c ET), lo que deja el IVA en 0% aunque obligue a declarar. **Resolverlo antes de presentar renta, no después.**

### R-02 · Rechazo de costos por falta de verificación de aportes del contratista
**Severidad ALTA · Solo Ruta A**

Art. 108 par. 2 ET: el contratante debe verificar la afiliación y el pago de aportes a seguridad social del contratista. Si no cotizó, la DIAN puede rechazar **la totalidad** del costo.

**Mitigación:** planilla PILA de cada persona, de los meses trabajados. Si no cotizaron, la Ruta A pierde su fundamento y la Ruta B pasa a ser la correcta — no por conveniencia, sino porque el costo no es deducible.

### R-03 · Objeción al documento soporte generado extemporáneamente
**Severidad ALTA · Solo Ruta A** — subió de MEDIA con el Concepto DIAN 006942 de 2025.

La Resolución DIAN 000167 de 2021 permite generar el documento soporte **en físico** mientras la DIAN no exija la versión electrónica (par. 3). Sigue vigente: la Res. 000165 de 2023 no la derogó y de hecho remite a ella.

**Pero el art. 2 de esa MISMA resolución fija plazos de generación**, y hay doctrina adversa reciente: la **DIAN, Concepto 006942 del 5 de mayo de 2025**, sostiene que el documento soporte solo puede generarse el mismo día de la operación, o por operaciones acumuladas con un mismo proveedor dentro de la semana siguiente a la primera, y que **generarlo fuera de plazo invalida su efecto fiscal**.

O sea: construir hoy el soporte de pagos de hace meses NO es una posición discutible con la DIAN de un lado y la sustancia del otro. Es una posición que la DIAN ya rechazó por escrito. Se puede sostener —la sustancia está probada con extractos verificables y el concepto no es ley—, pero hay que decirlo así y no como «es discutible».

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

### R-09 · Costos por encima del tope indicativo del 60%
**Severidad ALTA · Solo Ruta A**

El art. 336-1 ET, adicionado por la Ley 2277 de 2022 art. 60, estima los costos y gastos deducibles de rentas de trabajo en el **60% de los ingresos brutos**. Superarlo es legítimo, pero obliga a indicarlo **EXPRESAMENTE** en la declaración marcando la casilla informativa.

**Si se materializa:** no marcar la casilla acarrea la sanción del art. 651 num. 1 lit. d). Y hay un segundo requisito que suele mirarse por separado: esos costos deben estar soportados con **factura electrónica** de venta, nómina electrónica o documento equivalente ELECTRÓNICO — lo que choca de frente con la estrategia de documento soporte en físico del R-03. Quien piense superar el 60% tiene que mirar los dos juntos.

**Mitigación:** el motor lo emite solo cuando `total_costos > 60% de los ingresos brutos`. Si sale, decidir con el contador ANTES de escoger la Ruta A: puede ser que la Ruta B salga mejor no por aritmética sino porque los soportes electrónicos no existen.

### R-10 · Costos por encima del techo de su tipo de renta
**Severidad ALTA · Solo Ruta A**

El Decreto 1625 art. 1.2.1.20.5 inciso final (sustituido por el Decreto 2231 de 2023) no topa los costos contra la cédula: los topa contra los ingresos menos los INCRNGO de **cada tipo de renta**. El exceso de un tipo NO genera pérdida que se pueda restar de otro.

Importa cuando hubo un mal año en la actividad y a la vez rentas de capital: no se puede cruzar lo uno contra lo otro.

**Si se materializa:** la DIAN rechaza el exceso, sube la renta líquida y con ella el impuesto, más sanción por inexactitud del art. 648.

**Mitigación:** el motor lo emite con el detalle por tipo. Si crees que esos costos pertenecen a otro tipo de renta, decláralo en `[costos.atribucion]` del `perfil.toml` en vez de dejarlo al criterio por defecto — y guarda con qué actividad se relaciona cada factura.

### R-11 · Costos sin tipo de renta: el techo no se pudo aplicar
**Severidad MEDIA · Solo Ruta A**

Sale cuando el contribuyente tiene ingresos de **más de un tipo** y el `perfil.toml` no dice a cuál pertenece cada costo. El motor NO los reparte a ojo —atribuirlos al tipo equivocado sube el impuesto de alguien que no lo debe— así que los deja **sin topar**, y esa es una posición favorable al contribuyente: el borrador puede estar restando de más.

**Si se materializa:** el borrador subdeclara, que es el error que la DIAN cobra con sanción por inexactitud del art. 648.

**Mitigación, y es acción tuya, no del motor:** si sale R-11, **no entregues el borrador sin resolverlo**. Escribe el bloque `[costos.atribucion]` en `perfil.toml` —una línea por campo de `[costos]`, con `rentas_trabajo_honorarios`, `rentas_capital` u `otras_rentas_no_laborales`— y vuelve a calcular. La cifra puede cambiar la ruta ganadora, no solo el saldo.

Si un mismo campo de `[costos]` mezcla gastos de dos actividades, sepáralos primero: usa los campos que ya existen (`comisiones_plataforma`, `equipo_tecnologico`, `arriendo_oficina`) en vez de amontonarlo todo en `otros`. La atribución es por CAMPO, no por peso.

### R-12 · Dependientes sin acreditación verificable
**Severidad ALTA**

La DIAN lo denunció por escrito. **Comunicado de Prensa No. 058 del 2 de septiembre de 2024**: de 2,25 millones de declaraciones de personas naturales encontró inconsistencia en al menos 90.000, y lo primero que nombró fue que «se están incluyendo como dependientes a personas con identificaciones inusuales, tales como "cero" o con números secuenciales "1234...", "2222", "5678", entre otros».

Míralo de frente, porque es incómodo: **la palanca que esta herramienta promociona con más energía es exactamente la inconsistencia número uno que la administración está persiguiendo.** La deducción es legal y vale mucho — pero empujarla sin su riesgo, en el mismo expediente que se enorgullece de registrar riesgos, es un punto ciego. Este riesgo va SIEMPRE que haya dependientes declarados, aunque estén bien soportados.

**Mitigación:** documento de identidad real de cada uno, más el soporte de su causal. La que más se olvida es la **certificación de contador público** para padres, hermanos o cónyuge con ingresos anuales inferiores a 260 UVT (art. 387 par. 2 nums. 4 y 5), que además es la causal más usada.

### R-13 · Deducción del 1% por factura electrónica improcedente
**Severidad MEDIA-ALTA**

La segunda inconsistencia del mismo Comunicado 058: «la inclusión improcedente del beneficio de deducción del 1% sobre las compras soportadas con factura electrónica».

**Mitigación:** son DOS condiciones concurrentes y casi nadie verifica la segunda — factura electrónica de venta con el NIT o cédula del contribuyente como ADQUIRIENTE, **y** pago por medio electrónico. Guarda el soporte del medio de pago junto con la factura.

### R-15 · Renta por comparación patrimonial (arts. 236 y 237)
**Severidad ALTA · El motor lo emite**

Es la primera cuenta que la DIAN hace de forma automática. Si el patrimonio líquido creció más de lo que explican las rentas, la diferencia **se grava como renta líquida** (art. 236).

Lo que se compara NO es la renta líquida a secas. El art. 237 fija la fórmula: `renta gravable + ganancia ocasional neta + rentas exentas − impuestos de renta y complementarios pagados durante el año`.

**Mitigación:** el chequeo necesita `anio_anterior.patrimonio_liquido` en el perfil; sin él el motor dice que no puede concluir, y ese «no puede concluir» no es un aprobado. Si queda diferencia, hay que encontrar la causa justificativa y escribirla: valorizaciones nominales de inmuebles, herencias y donaciones (van a ganancia ocasional), préstamos recibidos —suben activo y pasivo a la vez—, INCRNGO. Si no hay ninguna, es ingreso no declarado.

**Ojo:** como «impuestos pagados» el motor solo ve las retenciones. Si el contribuyente pagó el saldo de la declaración anterior, ese pago también resta y la diferencia sin justificar es MAYOR que la que imprime el motor.

### R-16 · Beneficio de auditoría (art. 689-3)
**Severidad INFO · Es una OPORTUNIDAD, no un riesgo · El motor lo emite**

Subir el impuesto neto ≥35% frente al año anterior deja la declaración en firme a los **6 meses** en vez de a los 36; ≥25%, a los 12. Para un independiente con ingresos creciendo suele estar al alcance sin hacer nada distinto, y cambia por completo el perfil de riesgo de la declaración.

Vigente para los años gravables 2024, 2025 y 2026 por la **Ley 2294 de 2023 art. 69**. El texto del art. 689-3 dice «2022 y 2023»: quien lo lea solo en el Estatuto concluye que ya no aplica.

**Las tres condiciones que se pierden al resumir, y las tres muerden en este perfil:**
1. Presentación oportuna y **PAGO TOTAL** dentro del plazo. Un día tarde o pagar en cuotas y el beneficio se cae entero.
2. Si la declaración arroja **pérdida fiscal**, la DIAN conserva la facultad de fiscalizarla aunque corra el término. Es relevante acá: con un solo tipo de renta, los costos que exceden los ingresos producen pérdida fiscal declarable.
3. No procede si se demuestra que las **retenciones declaradas son inexistentes** — otra razón para conciliar la exógena.

**No lo presentes como una recomendación automática.** Renunciar a una deducción para alcanzar el umbral es una decisión de planeación legítima, pero es un cambio de posición: se propone, no se aplica.

### R-17 · Conciliación contra la información exógena
**Severidad ALTA · El motor lo emite · Va ANTES de calcular**

La exógena es lo que la DIAN **ya sabe** antes de que el contribuyente declare: terceros —clientes, bancos, plataformas— reportaron lo que le pagaron y lo que le retuvieron, y de ahí sale la declaración sugerida del Muisca.

Un ingreso que un tercero reportó y el contribuyente no declaró es una diferencia que la DIAN ve **sin fiscalizar a nadie**. Una retención declarada que nadie reportó es la causal expresa del art. 689-3 para perder el beneficio de auditoría.

**Mitigación:** descargarla del portal (Consulta de información exógena reportada por terceros), conciliarla contra el ledger con `templates/conciliacion-exogena.md`, explicar cada diferencia, y solo entonces marcar `verificaciones.exogena_descargada_y_conciliada = true`.

### Firmeza y conservación

No es un riesgo numerado, pero cierra el expediente y faltaba por completo:

- **Firmeza general:** 3 años desde el vencimiento del plazo para declarar (art. 714). Con beneficio de auditoría, 6 o 12 meses.
- **Conservación:** el art. 632 obliga a guardar los soportes por el término de firmeza. En la práctica **5 años**, por las correcciones del art. 588 y la firmeza especial de las declaraciones con pérdidas o compensaciones (art. 147).
- **El expediente no se borra al presentar. Se archiva.** Es el papel de trabajo.
- **Firma de contador:** NO es obligatoria para este perfil. El art. 596 la exige a quienes estén obligados a llevar contabilidad **Y** superen 100.000 UVT de patrimonio bruto o ingresos brutos. Decirlo genera confianza — y trae su corolario incómodo: sin firma no hay ningún filtro profesional entre esta salida y el Muisca, así que toda la carga de control queda en los chequeos del motor y en quien los lea.

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
