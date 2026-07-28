---
name: renta-rutas
description: Decide entre restar costos y gastos o la renta exenta del 25%, que son excluyentes según el art. 336 num. 4 ET. Úsala cuando haya que elegir la ruta de depuración, comparar escenarios, o cuando el usuario pregunte si le conviene deducir gastos o tomar el 25% exento.
---

# Ruta A vs Ruta B

La decisión que define la declaración de un independiente. **Son excluyentes: se elige una.**

## La norma

**Art. 336 num. 4 ET**, inciso segundo:

> «Los contribuyentes a los que les resulte aplicable el parágrafo 5 del artículo 206 del Estatuto Tributario **deberán optar entre restar los costos y gastos procedentes o la renta exenta** prevista en el numeral 10 del mismo artículo.»

Reglamentado por el art. 1.2.1.20.5 del Decreto 1625 de 2016, que recoge la sentencia **C-120 de 2018** de la Corte Constitucional.

## La asimetría

| | **Ruta A** — costos y gastos | **Ruta B** — renta exenta 25% |
|---|---|---|
| Tope | **Ninguno** | 25%, tope 240 UVT/mes, **y además** dentro del tope conjunto 40% / 1.340 UVT |
| Soporte | Factura o documento soporte por cada peso | Ninguno |
| Aportes del contratista | Hay que verificarlos (art. 108 par. 2) | No aplica |
| Riesgo de fiscalización | Alto si el soporte es débil | Bajo |
| Esfuerzo | Alto | Cero |

## Cómo se decide

**No por opinión. Se corre el motor.**

```bash
python -m engine.cli calcular --expediente ./expediente
```

Sale el comparativo renglón por renglón y la diferencia en pesos.

### Lo que hay que entender antes de decidir

El tope conjunto de 1.340 UVT es lo que estrangula la Ruta B. Pero la Ruta A tiene su propio estrangulamiento, que no es un tope sino un requisito: **solo cuentan los costos que estén soportados con documento válido y, si son pagos a personas, con sus aportes verificados.**

Entonces la comparación real no es «mis gastos» contra «el 25%». Es:

> **costos con soporte válido** contra **lo que la Ruta B logra restar después del tope**

Mucha gente asume que gana la Ruta A «porque tengo muchos gastos», y al filtrar por soporte real la mitad desaparece.

## El mito del "2+ trabajadores por 90 días"

Existe una regla que excluye del beneficio del 25% a quien vincula dos o más trabajadores, **pero está en el art. 383 ET y opera únicamente para la retención en la fuente mensual**, no para la depuración anual.

En la declaración manda el art. 336 num. 4: **la opción es libre**. Tener contratistas no te saca de la Ruta B; solo te da costos que hacen la Ruta A potencialmente mejor.

Si el contador dice lo contrario, esta es la cita.

## Cómo presentar la decisión

Tres cosas, en este orden:

1. **Cuánto se paga por cada ruta**, en pesos.
2. **Cuánto vale la diferencia.** Con frecuencia es menos de lo que la gente cree, y menos que una sola deducción olvidada. Si es así, dilo: evita que se obsesione con la decisión equivocada.
3. **Qué habría que conseguir para que la Ruta A gane**, si hoy pierde. Cuántos pesos de costo soportado harían falta, y si eso es realista.

## Cuándo la Ruta A no es viable aunque gane en el papel

Detente y dilo si:

- **Los contratistas no cotizaron.** Art. 108 par. 2 ET: la DIAN puede rechazar la totalidad del costo. Sin PILA, la Ruta A no tiene piso.
- **No hay documento soporte y el año ya cerró.** Se puede construir en físico (Resolución DIAN 000167 de 2021), pero es una posición discutible que va al registro de riesgos con su nivel. La decisión es del usuario, informada.
- **Los costos son gastos personales disfrazados.** El almuerzo no es costo. Si te presionan, di que no.

En esos casos, la Ruta B no es "la que queda": **es la correcta**, porque el costo no es deducible. Es una distinción importante y hay que decirla así.

## El escenario que hay que modelar siempre

Antes de cerrar la ruta, corre el escenario de dependientes. Con frecuencia:

- Elegir entre A y B vale unos cientos de miles.
- Acreditar dependientes vale varios millones, **sirve en ambas rutas**, y no exige un solo papel de gasto.

Si es el caso, dilo de frente: *la decisión que creías importante vale $X; la que no habías mirado vale $Y*. Ese contraste es lo que hace que la persona entienda dónde está el dinero de verdad.
