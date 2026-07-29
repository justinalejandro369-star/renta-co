# Formulario 210 — AG {{año}}

> **BORRADOR. No presentado ante la DIAN.**
> Generado por renta-co el {{fecha}}. Revisar con contador público antes de radicar.
> Ver [DISCLAIMER.md](../../DISCLAIMER.md).

---

## ⚠ Antes de transcribir un solo número

**Los números de casilla NO están precargados en esta plantilla, a propósito.**

La DIAN cambia la numeración de renglones entre años gravables. Una casilla
equivocada es un error de transcripción que puede costar una corrección o una
sanción, y no hay forma de verificarla desde acá.

Procedimiento:

1. Abre el Formulario 210 **oficial del año gravable {{año}}** en el portal de
   la DIAN o en el Programa Ayuda Renta.
2. Escribe el número de casilla en la columna vacía de cada fila.
3. Solo entonces transcribe los valores.

Si no puedes verificar la numeración, deja la columna en blanco y entrega el
borrador con los conceptos. Un contador la completa en minutos; una casilla
inventada le cuesta media hora encontrarla.

---

## Sección de patrimonio

| Casilla | Concepto | Valor | De dónde sale |
|---|---|---|---|
| ___ | Total patrimonio bruto | {{$X}} | `02-datos/patrimonio.md` |
| ___ | Deudas | {{$X}} | `02-datos/patrimonio.md` |
| ___ | **Total patrimonio líquido** | **{{$X}}** | bruto − deudas |

---

## Cédula general — rentas de trabajo

| Casilla | Concepto | Valor | De dónde sale |
|---|---|---|---|
| ___ | Ingresos brutos por rentas de trabajo | {{$X}} | `02-datos/ledger.csv` |
| ___ | Ingresos no constitutivos de renta | {{$X}} | planillas PILA + certificado del banco |
| ___ | Costos y gastos procedentes | {{$X}} | solo si se eligió **Ruta A** |
| ___ | Renta exenta del 25% (art. 206 num. 10) | {{$X}} | solo si se eligió **Ruta B** |
| ___ | Deducciones (GMF, vivienda, prepagada, AFP/AFC, dependientes 10%) | {{$X}} | renglón `= Subtotal deducciones dentro del tope` |
| ___ | Deducción por dependientes | {{$X}} | soporte de la condición |
| ___ | Deducción 1% compras con factura electrónica | {{$X}} | facturas electrónicas |
| ___ | **Renta líquida de la cédula general** | **{{$X}}** | motor |

> **Ruta elegida: {{A / B}}.** Son excluyentes (art. 336 num. 4 ET). Si se marcó
> una, la otra va en cero. Que quede escrito acá evita que alguien "complete"
> el renglón vacío.

---

## Cédula general — rentas de capital y no laborales

| Casilla | Concepto | Valor | De dónde sale |
|---|---|---|---|
| ___ | Ingresos brutos rentas de capital | {{$X}} | certificado de rendimientos |
| ___ | Ingresos brutos rentas no laborales | {{$X}} | {{}} |

---

## Liquidación

| Casilla | Concepto | Valor |
|---|---|---|
| ___ | Renta líquida gravable | {{$X}} |
| ___ | Impuesto sobre la renta líquida gravable (art. 241) | {{$X}} |
| ___ | Descuentos tributarios (donaciones, art. 257) | {{$X}} |
| ___ | **Impuesto neto de renta** | **{{$X}}** |
| ___ | Total retenciones año gravable {{año}} | {{$X}} |
| ___ | Saldo a favor del año anterior | {{$X}} |
| ___ | Anticipo de renta para el año siguiente | {{$X}} ← **verificar con el contador** |
| ___ | **Total saldo a pagar** | **{{$X}}** |
| ___ | **o Total saldo a favor** | **{{$X}}** |

> **Copia estas seis cifras del bloque «Al formulario 210» de `renta calcular`,
> tal como salen. No las recalcules ni las redondees.**
>
> El motor ya las aproximó al múltiplo de mil del art. 577 **encadenadas**:
> el impuesto sale de aplicar el art. 241 a la base YA APROXIMADA, que es lo
> que hace el formulario y lo que comprueba el validador del Muisca. Si
> tomas la cifra al peso de la depuración y la redondeas tú, en algunos
> casos te da mil pesos de diferencia y la declaración queda descuadrada
> consigo misma.
>
> Comprueba las tres ecuaciones antes de presentar:
>
> - impuesto = art. 241 aplicado a la **renta líquida gravable de esta tabla**
> - impuesto neto = impuesto − descuentos
> - saldo = impuesto neto − (retenciones + saldo a favor del año anterior)

---

## Casillas informativas que se olvidan

| Casilla | Cuándo aplica | Estado |
|---|---|---|
| ___ | **Costos y gastos superiores al 60% de los ingresos brutos** (art. 336-1). Marcarla es obligatorio si se supera el umbral; omitirla acarrea la sanción del art. 651 num. 1 lit. d) | {{aplica / no aplica}} |
| ___ | Renta presuntiva | {{}} |
| ___ | Ganancias ocasionales | {{este motor no las calcula — ver contador}} |

---

## Lo que este borrador NO cubre

- **Anticipo de renta** del año siguiente. No lo calcula el motor.
- **Ganancia ocasional** (art. 314 ET, cédula aparte al 15%).
- **Renta presuntiva.**
- **Rentas de pensiones** (art. 206 num. 5).
- Cualquier renglón específico de tu caso que no aparezca arriba.

Todo eso va al contador, señalado explícitamente en `memo-contador.md`.

---

## Verificación final antes de radicar

- [ ] Cada número de casilla verificado contra el formulario oficial de {{año}}
- [ ] La ruta elegida es coherente: si hay costos, no hay renta exenta del 25%
- [ ] El patrimonio incluye **todas** las cuentas, wallets, cripto y vehículos
- [ ] Las retenciones cuadran con la suma de los certificados
- [ ] Se corrió `/renta-co:privacidad` antes de enviarlo a alguien
- [ ] Un contador público lo revisó
