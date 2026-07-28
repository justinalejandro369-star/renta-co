---
name: renta-ingresos
description: Determina y clasifica los ingresos del año gravable, con TRM diaria para moneda extranjera. Úsala cuando haya que definir cuánto ganó el contribuyente, clasificar movimientos del ledger, convertir dólares a pesos, o cuando el usuario pregunte por ingresos, honorarios, USD, TRM o Deel.
---

# Ingresos

Es la cifra de la que cuelga todo lo demás. Un ingreso omitido dispara requerimiento y sanción por inexactitud del 100% de la diferencia (art. 648 ET). Un traslado contado como ingreso hace pagar impuesto sobre plata que nunca fue ingreso.

## Clasificación

| Categoría | Qué es | Dónde va |
|---|---|---|
| `ingreso_trabajo` | Honorarios, compensación por servicios personales, contratos de prestación de servicios | Cédula general, rentas de trabajo |
| `ingreso_capital` | Rendimientos financieros, intereses, arrendamientos | Cédula general, rentas de capital |
| `traslado` | Retiro del wallet a la cuenta propia, transferencia entre cuentas propias, conversión de moneda | **Ni ingreso ni gasto** |
| `costo` | Pago a contratista, comisión de plataforma, insumo | Solo Ruta A |
| `gasto_personal` | Consumo propio | No deducible, pero se registra para no confundirlo con costo |
| `retencion` | Retención que un tercero te practicó | Se resta del impuesto, no de la base |

## El error de los traslados

Un export de Deel o de Wise mezcla, en el mismo archivo:

- El pago que entró del cliente → **ingreso**
- El retiro de ese mismo dinero a tu banco → **traslado**, la misma plata otra vez
- La conversión de USD a COP dentro de la plataforma → **traslado**, la misma plata una tercera vez

Sumar todo lo positivo triplica el ingreso. Es el error más común al importar a mano y por eso los adaptadores clasifican por texto, no por signo.

**Pero ojo con la otra cara**: para el umbral de 3.500 UVT de IVA, los traslados **sí** cuentan como consignación. Son dos preguntas distintas sobre el mismo movimiento.

## TRM — art. 288 ET

Cada operación en moneda extranjera se convierte a la TRM **de su fecha de realización**. No promedio anual, no TRM de cierre.

```bash
python -m engine.cli importar --expediente ./expediente
```

Descarga la serie de `datos.gov.co` (solo se envía un rango de fechas), la cachea, y convierte movimiento por movimiento.

Si el contador usó promedio, reconcilia con `engine.ledger.comparar_trm_diaria_vs_promedio`. En 2025 la TRM osciló 19%: la diferencia sobre ingresos de tres cifras de millones son millones de base gravable.

## Preguntas de la entrevista

Después de leer los documentos, no antes.

1. **¿Este es todo el año?** Si el reporte de la plataforma empieza en julio, faltan seis meses. Pídelos. Si no los consigue, se estima y **se marca como supuesto** en la salida — nunca como si fuera un dato.
2. **¿Todos los clientes están acá?** Un cliente que pagó por transferencia directa no aparece en el reporte de la plataforma.
3. **¿Hubo pagos en efectivo o en cripto?** Son ingreso igual.
4. **¿Alguna de estas entradas es plata de terceros que redistribuiste?** Cambia el análisis de riesgo R-01 aunque no cambie el ingreso.
5. **¿Hay reembolsos de gastos?** Si el cliente te reembolsó un vuelo, entra como ingreso y el gasto se resta por el otro lado — solo si tienes soporte.
6. **¿Vendiste algo con utilidad?** Un activo poseído más de dos años es ganancia ocasional, cédula aparte, tarifa distinta. Este motor no la calcula todavía: márcalo para el contador.

## Qué NO es ingreso

- Traslados entre cuentas propias.
- Préstamos recibidos — son pasivo.
- Devoluciones de dinero propio.
- Reembolsos de saldo a favor de la DIAN.
- Dinero de terceros en tránsito. **Pero cuenta como consignación para el umbral de IVA.**

## Cierre

Cuando cierres los ingresos, escribe en `expediente/02-datos/resumen-ingresos.md`:

- Total por categoría.
- Qué parte está soportada con documento y qué parte es estimada.
- Rango de TRM usado y si fue diaria.
- Cualquier movimiento que quedó clasificado con duda, con el criterio que se usó.

Ese archivo es lo primero que va a mirar el contador.
