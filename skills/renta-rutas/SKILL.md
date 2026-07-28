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
| Tope | Sin tope que recorte la deducción, pero superar el **60% de los ingresos brutos** activa el art. 336-1: casilla informativa obligatoria y soporte **electrónico** | 25%, tope **790 UVT anuales**, **y además** dentro del tope conjunto 40% / 1.340 UVT |
| Soporte | Factura o documento soporte por cada peso | Ninguno |
| Aportes del contratista | Hay que verificarlos (art. 108 par. 2) | No aplica |
| Riesgo de fiscalización | Alto si el soporte es débil | Bajo |
| Esfuerzo | Alto | Cero |

## Cómo se decide

**No por opinión. Se corre el motor.**

```bash
"$RAIZ/bin/renta" calcular --expediente "$PWD/expediente"
```

Sale el comparativo renglón por renglón y la diferencia en pesos.

### Lo que hay que entender antes de decidir

El tope conjunto de 1.340 UVT es lo que estrangula la Ruta B. Pero la Ruta A tiene su propio estrangulamiento, que no es un tope sino un requisito: **solo cuentan los costos que estén soportados con documento válido y, si son pagos a personas, con sus aportes verificados.**

Entonces la comparación real no es «mis gastos» contra «el 25%». Es:

> **costos con soporte válido** contra **lo que la Ruta B logra restar después del tope**

Mucha gente asume que gana la Ruta A «porque tengo muchos gastos», y al filtrar por soporte real la mitad desaparece.

## Cómo se calcula el 25% — dos errores caros

**1. El tope es de 790 UVT ANUALES**, no de 240 UVT mensuales. La Ley 2277 de 2022 art. 2 lo cambió; el texto viejo es de la Ley 1607 de 2012 y sigue circulando. La diferencia es de 3,6 veces.

**2. La base no es el ingreso bruto.** El inciso 2 del num. 10 exige detraer primero los INCRNGO, las deducciones y las otras rentas exentas:

```
base = rentas de trabajo − INCRNGO − deducciones − otras rentas exentas
exención = min(base × 25%, 790 UVT)
```

Si alguien te muestra un cálculo del 25% sobre el bruto y topado en 2.880 UVT, está usando la norma derogada.

## La regla de los "2+ trabajadores por 90 días" — derogada

Circula mal explicada en las dos direcciones, así que conviene responderla con precisión.

La regla **existió** y sí condicionaba la declaración anual: estaba en el **art. 206 par. 5** (redacción de la Ley 2010 de 2019), no en el art. 383.

**La Ley 2277 de 2022 art. 2 reescribió ese parágrafo y la eliminó.** Hoy la exención procede «en relación con las rentas de trabajo que no provengan de una relación laboral o legal y reglamentaria», sin condición de equipo.

Conclusión práctica: **tener contratistas no te saca de la Ruta B.** Pero si vas a citarlo frente a un contador, cita la Ley 2277 de 2022 art. 2, no el art. 383 — ese artículo no dice nada de trabajadores ni de 90 días, y quedarías mal.

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
