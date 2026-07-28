---
name: renta-deducciones
description: Encuentra todas las deducciones, descuentos e ingresos no constitutivos de renta que le aplican al contribuyente. Úsala cuando haya que bajar la base gravable, revisar qué se puede restar, o cuando el usuario pregunte por deducciones, dependientes, GMF, prepagada, aportes voluntarios o cómo pagar menos.
---

# Deducciones

Acá está el dinero. La mayoría de las declaraciones de independientes dejan plata sobre la mesa, no por la ruta que eligen sino por deducciones que nadie preguntó.

## El orden en que hay que preguntar

Está ordenado por pesos ahorrados por minuto de conversación.

### 1. Dependientes — **empieza siempre por acá**

72 UVT por dependiente, hasta 4. **Fuera del tope del 40%.** No exige factura ni desembolso: se acredita la **condición**, no un gasto.

En AG2025 son **$3.585.528 por dependiente** de **base eliminada**, hasta $14.342.112.

> No confundas base con impuesto. $3.585.528 de base a una tarifa marginal del 28% son ~$1.004.000 de impuesto ahorrado. Cuando le digas una cifra al usuario, di cuál de las dos es — y para "cuánto vale", usa siempre la de la tabla de sensibilidad, que ya viene en impuesto.

Pregunta exactamente esto, no una versión resumida:

> ¿Tienes hijos menores de 18? ¿Hijos entre 18 y 23 estudiando? ¿**Tus papás o tus hermanos** tuvieron ingresos por debajo de $12.947.740 en el año y dependen económicamente de ti? ¿Cónyuge o pareja permanente sin ingresos o con ingresos por debajo de ese monto?

**La pregunta de padres y hermanos es la que más gente pierde.** Mucha gente mantiene a su mamá y no sabe que eso vale $3,5 M de deducción. Insiste. Si la respuesta es "más o menos le ayudo", indaga: ¿con cuánto?, ¿ella tiene ingresos propios?, ¿de cuánto?

Soporte según el caso:

| Situación | Qué documento |
|---|---|
| Hijo hasta 18 | Registro civil |
| Hijo de 18 a 25 estudiando | Certificado de la institución de educación superior (certificada por el ICFES) o del programa técnico acreditado |
| Hijo mayor de 18 con dependencia física o psicológica | Certificado del **Ministerio de Salud y Protección Social** — la Ley 2411 de 2024 cambió la entidad, antes era Medicina Legal |
| Cónyuge, padres o hermanos con ingresos < 260 UVT | **Certificado de contador público** (art. 387 par. 2 nums. 4 y 5). Es un requisito formal que se olvida y que la DIAN sí exige |
| Dependencia física o psicológica de cónyuge, padres o hermanos | Certificado del Ministerio de Salud y Protección Social |

> Hay una segunda vía por dependientes (10% de la renta de trabajo, tope 384 UVT, art. 387) que es **excluyente** con esta. El motor calcula las dos y toma la mejor. La diferencia clave: la del 10% **sí** consume el tope del 40%, así que solo gana cuando el tope está libre.

### 2. Aportes obligatorios de salud y pensión — INCRNGO, no deducción

Es la mejor posición posible para una partida: resta **antes** del tope del 40% y **no lo consume**.

> ¿Cotizaste a salud y pensión como independiente? Necesito las planillas PILA de los 12 meses.

Si no cotizó: no hay deducción, y además hay exposición ante la UGPP. Ver `renta-riesgos`.

**No lo pongas como deducción.** Ponerlo ahí lo mete dentro del tope del 40% y le quita valor.

### 3. GMF — 50% del 4x1000

Sin tope propio. Tenga o no relación con la actividad. Se pide el certificado a **cada** banco.

> ¿En qué bancos tuviste cuenta ese año? Necesito el certificado de GMF de cada uno.

Es de los papeles más fáciles de conseguir y casi nadie los pide todos.

### 4. Medicina prepagada o seguro de salud

16 UVT/mes, tope 192 UVT anuales ($9.561.408 en 2025). Dentro del tope del 40%.

> ¿Tienes medicina prepagada, plan complementario o póliza de salud? ¿Para ti o para tus dependientes?

⚠ En Ruta B compite contra la renta exenta del 25% dentro del mismo tope. Si el tope ya está saturado, puede no agregar nada. El motor lo resuelve; no lo prometas antes de correrlo.

### 5. Intereses de vivienda

Tope 1.200 UVT. Certificado anual del banco. **Solo los intereses**, no el abono a capital — es el error clásico.

### 6. Aportes voluntarios AFP y AFC

30% del ingreso, tope 3.800 UVT.

⚠ **Solo cuentan los hechos antes del 31 de diciembre del año gravable.** Si el año ya cerró, no hay nada que hacer para esa declaración. Pregúntalo igual, y si la respuesta es no, **muéstrale cuánto habría ahorrado** — ese número es el argumento para que lo haga este año. Pasa la posta a `renta-planeacion`.

### 7. Deducción del 1% por compras con factura electrónica

Tope 240 UVT, **fuera** del tope del 40%. Exige que la factura electrónica salga a su NIT o cédula como adquiriente **y** que el pago haya sido electrónico.

> ¿Pediste factura electrónica a tu nombre cuando compraste cosas grandes — computador, celular, muebles?

Casi siempre la respuesta es no. Sirve para planear el año siguiente.

### 8. Donaciones — descuento, no deducción

25% del valor donado, restado **del impuesto**, tope 25% del impuesto del período.

Exige certificación de una entidad del **Régimen Tributario Especial**, firmada por representante legal y contador o revisor fiscal.

> Sin certificado del RTE, la donación vale **$0**. Una transferencia a una persona, a una colecta, a un GoFundMe o a una fundación no calificada no da descuento. Dilo sin rodeos: mucha gente dona bastante y se lleva la mala noticia. Y aprovecha para que el año que viene done igual, pero pidiendo el certificado.

### 9. Costos y gastos — solo Ruta A

Sin tope, pero cada peso exige factura electrónica o documento soporte, y los pagos a contratistas exigen **verificar sus aportes a seguridad social** (art. 108 par. 2 ET).

Ese requisito, no el documento soporte, es el que más tumba la Ruta A en la práctica. Pide la planilla PILA de cada contratista **antes** de contar con la deducción.

Ver `renta-rutas` para la decisión.

## Lo que hay que rechazar

Aunque el usuario insista:

| No procede | Por qué |
|---|---|
| Intereses de tarjeta de crédito | Consumo personal, no financian la actividad |
| Consumos personales, viajes de placer | No tienen relación de causalidad |
| Gastos sin factura ni documento soporte | Sin soporte no hay deducción |
| Donaciones sin certificado del RTE | Requisito formal insalvable |
| Pagos a contratistas que no cotizaron | Art. 108 par. 2 ET |
| Abono a capital del crédito de vivienda | Solo los intereses son deducibles |

Cuando rechaces algo, di **por qué** y **qué sí se puede hacer** el año siguiente. No es un no seco: es información accionable.

## El tope conjunto

Rentas exentas + deducciones especiales ≤ **40% de los ingresos netos**, máximo **1.340 UVT** ($66.730.660 en 2025).

Quedan **fuera** del tope, y por eso valen más:

- Dependientes 72 UVT
- Deducción del 1% por factura electrónica
- Costos y gastos de la Ruta A
- INCRNGO (aportes obligatorios, componente inflacionario)

Cuando el tope ya esté saturado, **una deducción más dentro del tope vale cero**. Dilo explícitamente en vez de dejar que la persona persiga un certificado que no le va a servir. La tabla de sensibilidad del motor lo muestra en pesos.
