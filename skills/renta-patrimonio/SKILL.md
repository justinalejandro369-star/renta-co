---
name: renta-patrimonio
description: Determina el patrimonio bruto y los pasivos a 31 de diciembre del año gravable. Úsala cuando haya que declarar activos, cuentas, cripto, vehículos o inmuebles, o cuando el usuario pregunte por patrimonio, si tiene que declarar sus ahorros, o por la ecuación patrimonial.
---

# Patrimonio

No cambia el impuesto de renta, pero **es la parte que más problemas causa después**. Un activo omitido que la DIAN detecte se grava como renta líquida gravable, sin derecho a costo, más sanción por inexactitud (art. 239-1 ET).

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
| Saldo en plataformas (Deel, Wise, Payoneer, PayPal) | Saldo a 31-dic, **TRM de esa fecha** | Extracto de la plataforma |
| Cripto | Valor de mercado a 31-dic | Reporte del exchange o del wallet |
| Acciones, ETFs, brokers | Valor a 31-dic, TRM de esa fecha | Estado de cuenta anual |
| Vehículos | Avalúo del Ministerio de Transporte | Tarjeta de propiedad + tabla de avalúo |
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

## Moneda extranjera

Art. 269 ET: a la **TRM del 31 de diciembre**. No la del día que se consultó, no la promedio.

## Si falta un certificado

Si no se consigue el certificado de saldo, se usa el último extracto disponible y **se marca como estimado** en la salida. Nunca se pone un cero: un cero declarado es una omisión; un estimado documentado es una posición defendible.

Anótalo en `expediente/05-riesgos/` con el número exacto de lo que falta.

## Cierre

Escribe en `expediente/02-datos/patrimonio.md` la tabla completa, con la fuente de cada cifra y qué está estimado. Es lo que el contador va a querer ver, y lo que te salva si hay requerimiento en dos años.
