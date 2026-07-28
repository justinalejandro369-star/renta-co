---
name: renta-patrimonio
description: Determina el patrimonio bruto y los pasivos a 31 de diciembre del año gravable. Úsala cuando haya que declarar activos, cuentas, cripto, vehículos o inmuebles, o cuando el usuario pregunte por patrimonio, si tiene que declarar sus ahorros, o por la ecuación patrimonial.
---

# Patrimonio

No cambia el impuesto de renta, pero **es la parte que más problemas causa después**. Un activo omitido que la DIAN detecte se grava como renta líquida gravable, sin derecho a costo (art. 239-1 ET), **más sanción por inexactitud del 200%** — no del 100%: el art. 648 num. 1 la duplica justamente cuando se omiten activos o se incluyen pasivos inexistentes.

## La ecuación patrimonial

La DIAN corre este chequeo automático:

```
patrimonio inicial + renta líquida − gastos de vida ≈ patrimonio final
```

Si no cuadra, **presume ingresos omitidos**. Por eso un patrimonio subdeclarado no solo es un riesgo por sí mismo: hace sospechosa toda la declaración.

Y por eso hace falta la declaración del año anterior — de ahí sale el patrimonio inicial.

## Qué se declara

A **31 de diciembre del año gravable**, todo, esté donde esté:

| Activo | Cómo se valora | Qué pedir |
|---|---|---|
| Cuentas de ahorro y corrientes | Saldo a 31-dic | Certificado de saldo de **cada** banco |
| Billeteras digitales (Nequi, Daviplata, A la Mano) | Saldo a 31-dic | Certificado o extracto de diciembre |
| Saldo en plataformas (Deel, Wise, Payoneer, PayPal) | Saldo a 31-dic, **TRM del reconocimiento inicial de cada partida** (art. 269) | Extracto de la plataforma |
| Cripto | **Costo fiscal** (art. 267), no valor de mercado — DIAN, Concepto 100202208-1621 de 2023 (Unificado de Criptoactivos) | Reporte del exchange o del wallet, y el soporte de lo que pagaste |
| Acciones, ETFs, brokers | **Costo fiscal** (art. 272: «deben ser declarados por su costo fiscal»), con TRM del reconocimiento inicial. El valor de mercado solo aplica a obligados a sistemas especiales de valoración | Estado de cuenta anual |
| Vehículos | **Costo fiscal** (art. 267). El avalúo del Ministerio de Transporte es para el impuesto de vehículos y NO se usa en renta | Factura de compra o soporte del costo |
| Inmuebles | El mayor entre costo fiscal y avalúo catastral | Certificado de tradición, predial |
| Cuentas por cobrar | Valor nominal | Contrato o soporte |
| Aportes en sociedades | Costo fiscal | Certificado de la sociedad |

## Preguntas

Pregunta por **todo**, no solo por lo que apareció en los documentos. Los saldos pequeños se olvidan y son los que rompen la ecuación patrimonial.

1. ¿En qué bancos tienes cuenta? ¿**Todos**, incluidas las que casi no usas?
2. ¿Nequi, Daviplata, A la Mano, Lulo, Nu?
3. ¿Cuánto tenías en la plataforma de pago el 31 de diciembre?
4. ¿Cripto? ¿En qué exchange o wallet? ¿Cuánto valía el 31 de diciembre?
5. ¿Acciones o ETFs? ¿En Colombia o afuera?
6. ¿Carro, moto?
7. ¿Apartamento, casa, lote? ¿Propio, en herencia, en sucesión?
8. ¿Te deben plata con soporte escrito?
9. ¿Tienes parte de una empresa?

Y de pasivos:

10. ¿Créditos, hipoteca, tarjetas de crédito, deudas con personas?

## Pasivos

Solo los que se puedan probar. Los pasivos con personas naturales exigen documento de fecha cierta.

Se declaran por el saldo a 31-dic. **El saldo de la tarjeta de crédito a 31-dic es pasivo** y mucha gente lo olvida.

## Moneda extranjera — ojo, no es la TRM de cierre

Es un error muy extendido, incluido en material que circula entre contadores.

**Art. 269 ET**, modificado por la Ley 1819 de 2016 art. 116:

> «El valor de los activos en moneda extranjera se estiman en moneda nacional **al momento de su reconocimiento inicial a la tasa representativa del mercado**, menos los abonos o pagos medidos a la misma tasa representativa del mercado del reconocimiento inicial.»

O sea: **a la TRM del día en que entró cada partida**, no a la del 31 de diciembre. La regla del cierre es el texto original del Decreto 624 de 1989, derogado en 2016.

Concuerda con el art. 288 inciso 2: «Las fluctuaciones de las partidas del estado de situación financiera… **no tendrán efectos fiscales sino hasta el momento de la enajenación o abono**». La diferencia en cambio no realizada no se reconoce.

Reexpresar a TRM de cierre infla o desinfla el patrimonio y mueve la renta por comparación patrimonial (art. 236 ET) — justo el riesgo R-05.

## Si falta un certificado

Si no se consigue el certificado de saldo, se usa el último extracto disponible y **se marca como estimado** en la salida. Nunca se pone un cero: un cero declarado es una omisión; un estimado documentado es una posición defendible.

Anótalo en `expediente/05-riesgos/` con el número exacto de lo que falta.

## Cierre

Escribe en `expediente/02-datos/patrimonio.md` la tabla completa, con la fuente de cada cifra y qué está estimado. Es lo que el contador va a querer ver, y lo que te salva si hay requerimiento en dos años.
