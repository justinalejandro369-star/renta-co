# Benchmark

```bash
python -m benchmark.correr
```

Catorce contribuyentes ficticios, tres capas de verificación. Corre en CI en
cada push.

## Por qué tres capas

Un test que compara la salida del motor contra una constante **que salió del
propio motor** no prueba nada: si el motor está mal, la constante también lo
está. Este benchmark evita esa trampa por tres caminos distintos.

### 1. Invariantes

Propiedades que deben cumplirse siempre, sin importar el caso:

- El impuesto del art. 241 es **monótono** — más base nunca produce menos
  impuesto. Se verifica sobre un barrido de ~5.700 bases gravables.
- La tarifa efectiva nunca supera la marginal máxima del 39%.
- Los primeros 1.090 UVT están a tarifa 0%.
- La renta líquida y el impuesto nunca son negativos.
- El impuesto neto nunca supera al bruto.
- El tope conjunto nunca excede el menor entre el 40% de los ingresos netos
  y 1.340 UVT.
- El impuesto nunca supera la base gravable.
- La ruta elegida es siempre la de menor saldo.
- La tabla de sensibilidad viene ordenada y sin ahorros no positivos.

### 2. Diferencial

`benchmark/referencia.py` es una **segunda implementación**, escrita por
separado directamente desde el Estatuto Tributario, con estilo deliberadamente
literal y sin compartir una línea con `engine/`.

Sus constantes están **transcritas a mano** y no se leen de
`knowledge/parametros.toml`. Si se leyeran de ahí, una cifra equivocada en ese
archivo se cancelaría entre las dos implementaciones y el test pasaría.

Se comparan renta líquida, impuesto, impuesto neto, saldo, tope conjunto, vía
de dependientes elegida y mejor ruta, en las dos rutas, para las catorce
personas. Tolerancia de un peso por redondeo.

Para que un error sobreviva a esta capa tendría que aparecer **idéntico en
dos implementaciones escritas por separado**.

### 3. Anclas

Valores calculados a mano con la norma en la mano, con la aritmética escrita
en el propio archivo para que cualquiera la audite. Atrapan el caso que la
capa 2 no ve: que ambas implementaciones se equivoquen igual.

```python
{
    "id": "P01", "ruta": "A", "campo": "impuesto", "esperado": 7_272_360,
    "razon": "Base 90.000.000 = 1.807,265206 UVT. Tramo 1.700–4.100 al 28% "
             "con 116 UVT adicionales: (1.807,265206 − 1.700) × 0,28 + 116 "
             "= 146,034258 UVT × 49.799 = 7.272.360.",
}
```

## Las personas

| ID | Caso | Qué pone a prueba |
|---|---|---|
| P01 | Junior remoto, sin gastos | Caso limpio. Sin costos gana Ruta B |
| P02 | Freelance con equipo | El caso central del proyecto |
| P03 | Alto ingreso | El tope de 1.340 UVT muerde antes que el 40% |
| P04 | Bajo el umbral | Detección de no obligado a declarar |
| P05 | Consignaciones altas | R-01 con ingreso propio muy por debajo |
| P06 | 4 dependientes, tope libre | Gana la vía del 10% (art. 387) |
| P07 | 4 dependientes, tope saturado | Se invierte: gana la de 72 UVT |
| P08 | Costos enormes | Ruta A dominante + R-02 abierto |
| P09 | Donaciones grandes | El descuento se topa al 25% **del impuesto** |
| P10 | Retenciones altas | Saldo a favor: el signo tiene que salir bien |
| P11 | Exactamente 1.090 UVT | Frontera del tramo exento |
| P12 | Deducciones > ingreso | Sin negativos, renta líquida en 0 |
| P13 | Solo patrimonio | Impuesto 0, obligado por patrimonio |
| P14 | 900 M al año | Tramos altos y adicionales del art. 241 |

El par **P06 / P07** es el más interesante: el mismo número de dependientes da
una vía ganadora distinta según si el tope del 40% está libre o saturado. Es
exactamente el tipo de detalle que se pierde cuando la decisión la toma una
costumbre en vez de un cálculo.

## Rendimiento

~0,4 ms por liquidación completa —ambas rutas, tabla de sensibilidad y
verificaciones de riesgo— en un portátil. El costo del motor es irrelevante
frente a la latencia del agente; se mide para detectar regresiones, no para
optimizar.

## Agregar una persona

Añádela a `benchmark/personas.py` con su `espera` en prosa. Si conoces el
resultado correcto por cálculo manual, agrégalo también a `ANCLAS` con la
aritmética escrita. Esos son los tests más valiosos del repositorio.
