---
name: renta-clasificar
description: Lee una carpeta de documentos tributarios desordenados y los identifica, renombra y archiva por entidad y concepto. Úsala cuando el usuario diga "ya cargué todo", "ya subí los archivos", o cuando haya archivos sin clasificar en expediente/00-crudo/. Reporta qué encontró, qué no pudo leer y qué falta.
---

# Clasificar documentos

Este es el momento que hace que valga la pena la herramienta. El usuario soltó archivos con nombres como `Documento_202512_XXXXXXX.zip`, `Extracto_YYYYMM_Cuentas_de ahorro_XXXX.xlsx` y `certificado (2).pdf`. **Él no ordena nada. Tú sí.**

## Procedimiento

### 1. Inventario

Lista todo lo que hay en `expediente/00-crudo/`, incluidos subdirectorios. Descomprime los ZIP en su lugar. No borres nada del original: `00-crudo/` queda intacto como evidencia de qué entregó el usuario y cuándo.

### 2. Identificar uno por uno

Abre cada archivo y determina **entidad** y **concepto**. Los nombres no sirven de nada; el contenido sí.

| Señales en el contenido | Es |
|---|---|
| "Certificado de retención en la fuente", tabla con conceptos y valores retenidos | Certificado de retención |
| "Gravamen a los Movimientos Financieros", "4x1000", base gravable y valor | Certificado de GMF ← **el 50% es deducible** |
| "Rendimientos financieros", "componente inflacionario" | Certificado de rendimientos ← trae INCRNGO |
| Listado de movimientos con fecha, descripción y saldo | Extracto bancario |
| "Payment", "Invoice", "Contract", montos en USD | Reporte de plataforma |
| "Planilla", "PILA", "aportes", "IBC" | Planilla de seguridad social ← INCRNGO |
| "Medicina prepagada", "plan complementario", póliza de salud | Certificado de prepagada |
| "Intereses", "crédito hipotecario", "abono a capital" | Certificado de vivienda |
| "Registro Único Tributario", códigos de responsabilidad | RUT |
| "Formulario 210", renglones numerados | Declaración de un año anterior |
| "Certificado de donación", entidad del RTE, firma de contador | Certificado de donación |
| "W-8BEN", "Certificate of Foreign Status" | Formulario del cliente del exterior |

### 3. Archivar

Mueve **una copia** a `expediente/01-soportes/<entidad>/` con nombre normalizado:

```
<entidad>-<concepto>-<año>.<ext>

bancolombia-certificado-retencion-2025.pdf
bancolombia-certificado-gmf-2025.pdf
deel-movimientos-2025.csv
davivienda-extracto-2025.xlsx
eps-medicina-prepagada-2025.pdf
```

Entidad en minúscula sin tildes, una sola palabra cuando se pueda.

### 4. Extraer las cifras que ya sirven

De cada documento saca los números que van directo al perfil y **anota de qué archivo salió cada uno**. Trazabilidad completa: si la DIAN pregunta, hay que poder decir de dónde salió cada peso.

| Documento | Va a |
|---|---|
| Certificado de GMF | `deducciones.gmf_pagado` (total pagado; el motor toma el 50%) |
| Certificado de retención | `anticipos.retenciones_practicadas` |
| Certificado de rendimientos | `ingresos.rentas_capital` y `incrngo.componente_inflacionario` |
| Planillas PILA | `incrngo.aportes_obligatorios_salud_pension` |
| Certificado de prepagada | `deducciones.medicina_prepagada` |
| Certificado de vivienda | `deducciones.intereses_vivienda` (solo intereses, **no** abono a capital) |
| Extractos y reportes | van al ledger, no al perfil directo |

### 5. Reportar

Tres listas, siempre:

**Identificado** — tabla de archivo → entidad → concepto → cifras extraídas.

**No identificado** — archivo y por qué. Pregunta qué es. No adivines.

**Falta** — lo que no apareció y debería estar. Ordénalo por impacto:

- Certificado de GMF de **cada** banco donde tuvo cuenta. Casi nadie lo pide y siempre suma.
- Extracto **completo del año** de **todas** las cuentas — sin esto no se puede cuantificar el riesgo R-01.
- Planillas PILA de los 12 meses.
- Certificados de saldo a 31 de diciembre de todas las cuentas, wallets y exchanges — para el patrimonio.
- Reporte anual completo de la plataforma de pago. Un reporte parcial deja ingreso sin declarar, y la plataforma sí reporta a la DIAN.
- Declaración del año anterior.

## Errores que hay que atrapar acá

**Extractos parciales.** Si hay extractos de marzo y de junio pero no de los otros meses, dilo. Un extracto parcial no sirve para cuantificar consignaciones ni para el patrimonio.

**Documentos de otro año.** Un extracto de 2026 no sirve para declarar 2025 — salvo para el patrimonio a 31-dic si es el corte de enero.

**Cuentas que aparecen mencionadas pero de las que no hay soporte.** Si un extracto muestra una transferencia a "Nequi" y no hay certificado de Nequi, esa cuenta existe y falta su saldo. Anótalo.

**Intereses de tarjeta de crédito.** Aparecen en certificados al lado de datos que sí sirven. **No son deducibles.** Si los ves, márcalos explícitamente como no deducibles para que nadie los meta después.

## Privacidad

Los documentos se quedan en `expediente/`. No copies cédulas, números de cuenta ni nombres a ningún archivo fuera de ahí, ni a tu resumen de la conversación. Cuando cites un documento en un entregable, cítalo por nombre de archivo, no por su contenido identificatorio.
