# Conciliación contra la información exógena — AG {{año}}

> **Esto va PRIMERO, antes de calcular nada.** Es la primera parada de
> cualquier contador y la última que se le ocurre a quien declara solo.
>
> La exógena es lo que la DIAN **ya sabe** de ti: tus clientes, bancos y
> plataformas le reportaron lo que te pagaron y lo que te retuvieron. De ahí
> sale la declaración sugerida del Muisca. Un ingreso que un tercero reportó
> y tú no declaraste es una diferencia que la DIAN ve **sin fiscalizar a
> nadie**.
>
> Guarda este archivo en `expediente/01-fuentes/`. Es papel de trabajo:
> conservarlo por el término de firmeza (ver `riesgos.md`).

## 1. Descarga

- [ ] Portal DIAN → **Consulta de información exógena reportada por terceros**
- [ ] Año gravable: {{año}}
- [ ] Archivo guardado en: {{ruta dentro del expediente}}
- [ ] Fecha de descarga: {{fecha}}

> La exógena se sigue reportando y corrigiendo después del plazo. Si la bajas
> muy temprano puede estar incompleta; si la bajas el día antes de presentar,
> no te queda tiempo para pedirle a un tercero que corrija. Anota la fecha:
> es lo que explica una diferencia que aparezca después.

## 2. Ingresos — lo que reportaron contra lo que declaras

| Tercero (NIT) | Concepto | Reportado por el tercero | En tu ledger | Δ | Explicación |
|---|---|---|---|---|---|
| {{}} | {{}} | {{$X}} | {{$X}} | {{$X}} | {{}} |

**Total reportado:** {{$X}} · **Total en el ledger:** {{$X}} · **Δ:** {{$X}}

### Diferencias que SÍ tienen explicación

- **Caja contra causación.** Un cliente que te pagó el 2 de enero de {{año+1}}
  una factura de diciembre reporta en {{año+1}} y tú la declaras según tu
  criterio de imputación. Déjalo escrito con la fecha exacta.
- **Ingreso bruto contra neto recibido.** Las plataformas del exterior suelen
  transferir el neto después de comisión, y el ingreso gravado es el **bruto
  facturado**. Si el cliente del exterior retuvo, la base y el descuento del
  art. 254 están los dos en juego — revísalo con tu contador.
- **Reembolsos y traslados entre tus propias cuentas.** No son ingreso, y son
  la causa número uno de un total inflado.
- **Diferencia de TRM.** El tercero puede haber convertido a una tasa distinta
  de la TRM del día de la operación.

### Diferencias que NO tienen explicación

Un ingreso reportado que no está en tu ledger y no cae en ninguna de las
categorías de arriba es **ingreso no declarado**. Se agrega al perfil y se
vuelve a calcular. No se explica: se declara.

## 3. Retenciones — el lado que casi nadie mira

| Agente retenedor (NIT) | Retención reportada | En tu perfil | Δ |
|---|---|---|---|
| {{}} | {{$X}} | {{$X}} | {{$X}} |

**Total reportado:** {{$X}} · **En `anticipos.retenciones_practicadas`:** {{$X}}

> ⚠ Una retención que **tú declaras y nadie reportó** es la causal expresa del
> art. 689-3 para perder el beneficio de auditoría, además de un rechazo
> probable. Si te falta un certificado, pídelo antes de presentar.
>
> Y al revés: una retención que te practicaron y no incluiste es plata tuya
> que estás regalando.

## 4. Patrimonio y otros reportes

- [ ] Saldos de cuentas bancarias a 31-dic — cuadran con `patrimonio.activos`
- [ ] Inversiones, CDT, fondos
- [ ] Compras y consumos reportados (relevantes para R-15, comparación
      patrimonial: un consumo alto con patrimonio creciente llama la atención)
- [ ] Aportes a seguridad social reportados por la ADRES / operador PILA

## 5. Cierre

- [ ] Toda diferencia de la sección 2 tiene explicación escrita **o** se
      corrigió el perfil
- [ ] Toda diferencia de la sección 3 tiene certificado **o** se corrigió
- [ ] Se volvió a correr `bin/renta calcular` **después** de las correcciones
- [ ] `verificaciones.exogena_descargada_y_conciliada = true` en el perfil

**Conciliado por:** {{}} · **Fecha:** {{}}

---

## Lo que esta conciliación NO cubre

- Lo que **ningún tercero reporta**: clientes del exterior sin obligación de
  reportar en Colombia, pagos en efectivo, cripto. Que no esté en la exógena
  no significa que no sea ingreso.
- La exógena **no es una liquidación**: la declaración sugerida del Muisca la
  arma la DIAN con estos datos y sin conocer tus costos. Cuadrar contra la
  exógena no valida tu declaración, solo descarta una clase de error.
