# Registro de riesgos — AG {{año}}

Cada riesgo con su fundamento normativo, la probabilidad de que la DIAN o la
UGPP lo objete, y la consecuencia si se pierde.

---

## R-01 · Pérdida de la calidad de no responsable de IVA por consignaciones
**Severidad: ALTA · Probabilidad: {{}} · Estado: {{}}**

El umbral de 3.500 UVT ({{$174.296.500}}) se mide sobre **consignaciones**, no
sobre ingresos propios.

Total consignado en el año: **{{$X}}**. {{Dentro del umbral, con margen de $X /
SUPERADO por $X}}.

**Si se materializa:** obligación de inscribirse como responsable de IVA,
facturar, declarar IVA por período, y sanción por extemporaneidad de cada
declaración omitida. Puede costar más que el propio impuesto de renta.

**Mitigación:** {{}}. Si se superó, evaluar exportación de servicios exenta
(art. 481 lit. c ET), que deja el IVA en 0% aunque obligue a declarar.

---

## R-02 · Rechazo de costos por falta de verificación de aportes del contratista
**Severidad: ALTA · Probabilidad: {{}} · Solo Ruta A**

Art. 108 par. 2 ET. Costos en juego: **{{$X}}**. Impacto si se rechazan:
**+{{$X}} de impuesto**.

**Mitigación:** planilla PILA de cada contratista, de los meses trabajados.

---

## R-03 · Objeción al documento soporte generado extemporáneamente
**Severidad: MEDIA · Probabilidad: {{}} · Solo Ruta A**

{{Descripción del caso concreto.}}

**Línea que no se cruza:** fechas y montos van tal como ocurrieron.

---

## R-04 · Ingreso subdeclarado
**Severidad: ALTA · Probabilidad: {{}}**

Soportado: **{{$X}}**. Estimado sin soporte: **{{$X}}**.
Sanción por inexactitud: 100% de la diferencia (art. 648 ET).

---

## R-05 · Patrimonio bruto subdeclarado
**Severidad: MEDIA-ALTA · Probabilidad: {{}}**

Faltan: {{lista}}. Art. 239-1 ET + ecuación patrimonial.

---

## R-06 · Exposición ante la UGPP por aportes propios
**Severidad: MEDIA-ALTA · Fuera del alcance de la declaración**

{{Estado de cotización.}} Frente separado, con sus propios términos y
sanciones. **No se oculta en la declaración.**

---

## R-07 · Deducciones improcedentes
**Severidad: BAJA-MEDIA**

Partidas que hay que asegurarse de NO incluir: {{lista con montos}}.

---

## R-08 · TRM promedio en vez de TRM diaria
**Severidad: BAJA · Estado: {{mitigado}}**

El ledger aplica TRM diaria (art. 288 ET). Diferencia frente a promedio:
**{{$X}}**. {{Reconciliar con el contador si usó promedio.}}

---

## R-09 · Costos por encima del tope indicativo del 60%
**Severidad: ALTA · Solo Ruta A · Lo emite el motor**

Art. 336-1 ET. Costos {{$X}} = {{X}}% de los ingresos brutos. Superar el 60%
es legítimo pero obliga a marcar la casilla informativa; no marcarla acarrea
la sanción del art. 651 num. 1 lit. d). Y exige soporte con factura
electrónica, nómina electrónica o documento equivalente ELECTRÓNICO, lo que
choca con la estrategia de documento soporte físico del R-03.

**Mitigación:** {{}}

---

## R-10 · Costos por encima del techo de su tipo de renta
**Severidad: ALTA · Solo Ruta A · Lo emite el motor**

Decreto 1625 art. 1.2.1.20.5. {{$X}} rechazados: {{detalle por tipo}}.

**Mitigación:** declarar `[costos.atribucion]` en el `perfil.toml` en vez de
dejarlo al criterio por defecto, y guardar con qué actividad se relaciona
cada factura.

---

## R-11 · Costos sin tipo de renta: el techo no se pudo aplicar
**Severidad: MEDIA · Solo Ruta A · Lo emite el motor**

Hay ingresos de más de un tipo y el perfil no dice a cuál pertenece cada
costo, así que el motor NO les aplicó el techo. **El borrador puede estar
restando de más**, que es el error que la DIAN cobra con sanción por
inexactitud.

**Mitigación:** no entregues el borrador sin resolverlo. Escribe
`[costos.atribucion]` y vuelve a calcular: puede cambiar la ruta ganadora,
no solo el saldo.

---

## R-12 · Dependientes sin acreditación verificable
**Severidad: ALTA**

La DIAN denunció esto públicamente. **Comunicado de Prensa No. 058 del 2 de
septiembre de 2024**: de 2,25 millones de declaraciones de personas
naturales encontró inconsistencia en al menos 90.000, y nombró de primera
que «se están incluyendo como dependientes a personas con identificaciones
inusuales, tales como "cero" o con números secuenciales "1234...", "2222",
"5678", entre otros».

Es el riesgo que acompaña a la palanca más grande de esta herramienta. No
está acá para desanimarla: la deducción es legal y vale. Está para que se
tome con el soporte que exige.

Dependientes declarados: {{N}}. Deducción tomada: **{{$X}}**.

**Mitigación:** documento de identidad REAL de cada dependiente, y el soporte
que corresponde a su causal — registro civil, certificado de estudio de la
institución, certificación del Ministerio de Salud para dependencia física o
psicológica, o **certificación de contador público** para padres, hermanos o
cónyuge con ingresos anuales inferiores a 260 UVT (art. 387 par. 2 nums. 4 y
5 ET). Esta última es la que más se olvida y es la que sostiene la causal más
usada.

---

## R-13 · Deducción del 1% por factura electrónica improcedente
**Severidad: MEDIA-ALTA**

La segunda inconsistencia que nombra el mismo Comunicado 058 de 2024: «la
inclusión improcedente del beneficio de deducción del 1% sobre las compras
soportadas con factura electrónica».

Deducción tomada: **{{$X}}**.

**Mitigación:** exige las DOS condiciones a la vez, y casi nadie verifica la
segunda — factura electrónica de venta con el NIT o cédula del contribuyente
como ADQUIRIENTE, **y** pago por medio electrónico. Una factura a nombre de
otro, o una compra en efectivo, no cuentan. Guarda el soporte del medio de
pago junto con la factura.

---

## R-15 · Renta por comparación patrimonial (arts. 236 y 237 ET)

**Qué es:** la primera cuenta que la DIAN hace de forma automática. Si tu
patrimonio líquido creció más de lo que explican tus rentas, la diferencia se
**grava como renta líquida**.

**Lo que se compara** (fórmula del art. 237, no la renta líquida a secas):

    renta gravable + ganancia ocasional neta + rentas exentas
      − impuestos de renta y complementarios pagados durante el año

**Patrimonio líquido {{año-1}}:** {{$X}} · **{{año}}:** {{$X}} · **Δ:** {{$X}}
**Suma del art. 237:** {{$X}} · **Sin justificar:** {{$X}}

**Causas justificativas que aplican en este caso:** {{}}

> Suelen serlo: valorizaciones nominales de inmuebles, herencias y donaciones
> (van a ganancia ocasional), préstamos recibidos —suben el activo y el pasivo
> a la vez— y los INCRNGO. **No** lo es el ingreso no declarado.
>
> El motor solo ve las retenciones como «impuestos pagados». Si pagaste el
> saldo de la declaración anterior, ese pago también resta.

---

## R-16 · Beneficio de auditoría (art. 689-3 ET)

**Qué es:** subir el impuesto neto ≥35% frente al año anterior deja la
declaración **en firme a los 6 meses** en vez de a los 36. Con ≥25%, a los 12.

**Impuesto neto {{año-1}}:** {{$X}} · **{{año}}:** {{$X}} · **Incremento:** {{%}}
**Veredicto del motor:** {{}}

**Las tres condiciones que se pierden al resumir:**

- [ ] Presentación **oportuna** y **PAGO TOTAL** dentro del plazo. Un día tarde
      o pagar en cuotas y el beneficio se cae entero.
- [ ] Si la declaración arroja **pérdida fiscal**, la DIAN conserva la facultad
      de fiscalizarla aunque haya corrido el término.
- [ ] No procede si se demuestra que las **retenciones declaradas son
      inexistentes** — otra razón para conciliar la exógena (R-17).

> Vigente para los años gravables 2024, 2025 y 2026 por la Ley 2294 de 2023
> art. 69. El texto del art. 689-3 dice «2022 y 2023»: quien lo lea solo en el
> Estatuto concluye que ya no aplica.

---

## R-17 · Conciliación contra la información exógena

**Qué es:** lo que la DIAN **ya sabe** de ti antes de que declares. Tus
clientes, bancos y plataformas reportaron lo que te pagaron y lo que te
retuvieron, y de ahí sale la declaración sugerida del Muisca.

- [ ] Exógena descargada del portal (Consulta de información exógena reportada
      por terceros)
- [ ] Conciliada contra el ledger con `templates/conciliacion-exogena.md`
- [ ] `verificaciones.exogena_descargada_y_conciliada = true` en el perfil

**Diferencias encontradas y su explicación:** {{}}

> Va **antes** de calcular, no después. Un ingreso que un tercero reportó y tú
> no declaraste es una diferencia que la DIAN ve sin fiscalizar a nadie.

---

## Firmeza y conservación

**La declaración de {{año}} queda en firme el:** {{fecha}}
({{36 meses / 12 meses / 6 meses según R-16}})

**Conservar el expediente hasta:** {{fecha}}

> Art. 714: tres años desde el vencimiento del plazo para declarar. Art. 632:
> conservar los soportes por el término de firmeza — en la práctica **cinco
> años**, por las correcciones del art. 588 y la firmeza especial de las
> declaraciones con pérdidas o compensaciones (art. 147).
>
> **El expediente no se borra al presentar. Se archiva.** Es el papel de
> trabajo: si la DIAN pregunta, lo que respalda cada renglón son esos archivos.

---

## Resumen

| ID | Riesgo | Severidad | Se resuelve con |
|---|---|---|---|
| R-01 | Umbral de consignaciones / IVA | ALTA | {{}} |
| R-02 | Costos sin PILA del contratista | ALTA | {{}} |
| R-04 | Ingreso subdeclarado | ALTA | {{}} |
| R-05 | Patrimonio subdeclarado | MEDIA-ALTA | {{}} |
| R-06 | UGPP | MEDIA-ALTA | {{}} |
| R-03 | Documento soporte extemporáneo | MEDIA | {{}} |
| R-09 | Costos > 60% indicativo | ALTA | {{}} |
| R-10 | Costos > techo de su tipo de renta | ALTA | {{}} |
| R-12 | Dependientes sin acreditación | ALTA | {{}} |
| R-13 | Deducción 1% factura electrónica | MEDIA-ALTA | {{}} |
| R-11 | Costos sin tipo de renta | MEDIA | {{}} |
| R-07 | Deducciones improcedentes | BAJA-MEDIA | {{}} |
| R-08 | TRM promedio | BAJA | {{}} |
| R-15 | Comparación patrimonial | ALTA | {{}} |
| R-16 | Beneficio de auditoría | INFO | {{}} |
| R-17 | Exógena sin conciliar | ALTA | {{}} |

> Los que el motor emite —R-01, R-02, R-09, R-10, R-11, R-15, R-16, R-17— se
> copian de la salida de `bin/renta calcular`, no se redactan de nuevo. Si el motor imprime
> un `R-xx` que no está en esta plantilla, agrégalo igual: un riesgo detectado
> que no llega al expediente es el error invisible de este proyecto.
