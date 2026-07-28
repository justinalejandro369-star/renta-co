# Expediente de ejemplo

Contribuyente **ficticio**. Cifras inventadas y redondas. No hay ni un dato
real de nadie.

Perfil: desarrolladora independiente, cliente único en EE.UU. que le paga en
USD por plataforma, subcontrata a dos personas, mantiene a su madre.

## Correrlo

```bash
python3 -m engine.cli calcular --expediente expediente.ejemplo
```

## Qué mirar

**1. La Ruta A gana, y acá sí por un margen que importa.**
La diferencia entre rutas supera a cualquier palanca individual — no siempre
es así, y por eso el motor las calcula todas en vez de asumir. Fíjate en que
la tabla separa lo que solo exige un papel de lo que exige desembolsar: las
dos palancas más grandes de este caso cuestan más de lo que ahorran.

**2. La vía de dependientes que escoge el motor.**
Con un dependiente y el tope del 40% sin saturar, gana la deducción del 10%
(art. 387) por encima de las 72 UVT. El motor calcula ambas y toma la mejor.
Si el tope estuviera saturado, la respuesta se invierte — hay un test que
verifica exactamente eso.

**3. R-01 en rojo.**
Consignaciones de $198.000.000 contra un umbral de $174.296.500. El ingreso
propio está muy por debajo, pero por la cuenta pasó plata de clientes que se
redistribuyó. **Ese es el caso que la herramienta existe para atrapar**, y el
que casi ninguna declaración mira.

**4. R-02 también en rojo.**
Hay $66.620.000 de costos y ningún contratista con PILA verificada. Si no
cotizaron, la Ruta A pierde su fundamento entero y la respuesta correcta
cambia. Por eso el riesgo se levanta antes de celebrar el resultado.

**5. Los aportes voluntarios en cero.**
La sensibilidad muestra lo que habrían valido. La ventana se cerró el 31 de
diciembre — ese número ya no es una oportunidad, es el argumento para el año
en curso.

## El ledger

```bash
python3 -m engine.cli importar --expediente expediente.ejemplo
```

Importa `00-crudo/movimientos-plataforma.csv` con el adaptador de Deel y
descarga la TRM diaria. Fíjate en la clasificación: de 26 movimientos, 12 son
ingreso, 5 son **traslados** (retiros a la cuenta propia y una conversión de
moneda) y el resto son costos y comisiones.

Sumar todo lo positivo daría un ingreso muchísimo mayor al real. Ese es el
error más común al importar a mano, y la razón de que los traslados sean una
categoría de primera clase.

> Este paso necesita red la primera vez, para bajar la serie TRM de
> `datos.gov.co`. Después queda cacheada.
