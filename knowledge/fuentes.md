# Fuentes

Toda cifra de `knowledge/*/parametros.toml` lleva su campo `fuente`. Hay un
test que lo verifica: una cifra sin fuente no entra al repositorio.

## Normativa primaria

| Norma | Qué establece |
|---|---|
| [Estatuto Tributario art. 206](https://estatuto.co/206) | Rentas exentas de trabajo. Num. 10: renta exenta del 25%. Par. 5: aplicación a honorarios |
| [ET art. 241](https://estatuto.co/241) | Tarifa del impuesto de renta de personas naturales |
| [ET art. 336](https://estatuto.co/336) | Depuración de la cédula general. Num. 3: tope 40% / 1.340 UVT. Num. 4: opción costos vs. renta exenta. Par.: dependientes 72 UVT |
| [ET art. 387](https://estatuto.co/387) | Deducciones: medicina prepagada, dependientes 10%, definición de dependiente |
| [ET art. 115](https://estatuto.co/115) | Deducción del 50% del GMF |
| [ET art. 119](https://estatuto.co/119) | Deducción de intereses de vivienda |
| [ET art. 126-1](https://estatuto.co/126-1) y [126-4](https://estatuto.co/126-4) | Aportes voluntarios a AFP y cuentas AFC |
| [ET art. 257](https://estatuto.co/257) | Descuento por donaciones a entidades del RTE |
| [ET art. 288](https://estatuto.co/288) | Conversión de moneda extranjera a TRM de la fecha de realización |
| [ET art. 269](https://estatuto.co/269) | Valor patrimonial de activos en moneda extranjera |
| [ET art. 108 par. 2](https://estatuto.co/108) | Verificación de aportes del contratista para deducir el pago |
| [ET art. 368-2](https://estatuto.co/368-2) | Cuándo una persona natural es agente de retención |
| [ET art. 437 par. 3](https://estatuto.co/437) | Requisitos para ser no responsable de IVA |
| [ET art. 481 lit. c](https://estatuto.co/481) | Exportación de servicios exenta de IVA |
| [ET art. 239-1](https://estatuto.co/239-1) | Activos omitidos como renta líquida gravable |
| [ET art. 641](https://estatuto.co/641) | Sanción por extemporaneidad |
| [ET art. 648](https://estatuto.co/648) | Sanción por inexactitud |
| Decreto 1625 de 2016, art. 1.2.1.20.3 y 1.2.1.20.5 | Reglamento de la depuración de rentas de trabajo |
| Decreto 1625 de 2016, art. 1.6.1.4.12 | Requisitos del documento soporte |
| [Ley 2277 de 2022, art. 7](https://normograma.dian.gov.co/dian/compilacion/docs/ley_2277_2022.htm) | Adiciona la deducción de 72 UVT por dependiente |
| Sentencia C-120 de 2018, Corte Constitucional | Derecho a detraer costos y gastos de honorarios |
| [Resolución DIAN 000167 de 2021](https://normograma.dian.gov.co/dian/compilacion/docs/resolucion_dian_0167_2021.htm) | Documento soporte en físico mientras no se exija el electrónico |

## Valores de la UVT

| Año | Valor | Resolución |
|---|---|---|
| 2024 | $47.065 | Res. DIAN 000187 de 2023 |
| 2025 | $49.799 | Res. DIAN 000193 de 2024 |
| 2026 | $52.374 | Res. DIAN 000238 del 15 de diciembre de 2025 |

## Datos

- [Serie TRM histórica — datos.gov.co](https://www.datos.gov.co/Econom-a-y-Finanzas/Tasa-de-Cambio-Representativa-del-Mercado-Historico/32sa-8pi3) · Banco de la República. Es la única fuente externa que consulta el motor.
- [Portal DIAN — Renta Personas Naturales](https://micrositios.dian.gov.co/renta-personas-naturales-ag-2025/)
- [Programa Ayuda Renta — DIAN](https://www.dian.gov.co/impuestos/personas/Renta-Personas-Naturales-AG-2020/Paginas/Programa-Ayuda-Renta.aspx)

## Fuentes secundarias

Útiles para entender, **no** para citar en una declaración. Cuando una de
estas es la única fuente de una cifra, hay que verificarla contra la norma
antes de meterla a `parametros.toml`.

- [Gerencie.com](https://www.gerencie.com/) — rentas exentas y costos en independientes
- [Actualícese](https://actualicese.com/) — UVT y umbrales por año
- [Siempre al Día](https://siemprealdia.co/) — análisis de reformas

## Lo que falta

Aportes con fuente bienvenidos. Ver `CONTRIBUTING.md`.

1. **Decreto oficial de plazos** por últimos dos dígitos, por año gravable.
   Es la razón de que `plazos.tabla_cargada = false`: una fecha adivinada
   cuesta una sanción del 5% mensual.
2. ~~**Doctrina DIAN** sobre generación extemporánea del documento soporte~~
   **RESUELTO y adverso**: Concepto DIAN 006942 del 5-may-2025 — generarlo
   fuera de plazo invalida su efecto fiscal. Falta la jurisprudencia del
   Consejo de Estado, si la hay.
3. **Cómputo de consignaciones** para el umbral de 3.500 UVT: ¿cuentan los
   traslados entre cuentas propias del mismo titular? La respuesta cambia el
   riesgo de mucha gente.
4. **Qué reportan las plataformas** (Deel, Upwork, Payoneer) a la DIAN, en
   qué formato, y qué objeciones se han visto en la práctica.
5. **Cripto**: valoración patrimonial a 31-dic y ganancia ocasional en
   enajenaciones.
