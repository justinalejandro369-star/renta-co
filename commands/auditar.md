---
description: Corre el cálculo completo — dos rutas, sensibilidad, riesgos y qué falta
argument-hint: "[--anio 2025]"
---

Corre el motor y presenta el resultado. Argumentos: $ARGUMENTS

Si el usuario pasó `--anio N`, agrégalo a AMBOS comandos como `--anio N`. Si no, no pases nada y el motor toma el año del perfil.

`$RAIZ` es la raíz de renta-co: el directorio que contiene `AGENTS.md` y
`bin/renta`. Instalado como plugin es `$CLAUDE_PLUGIN_ROOT`; clonado, es la
raíz del repo. Resuélvelo antes de correr nada — este comando se puede
invocar sin haber pasado por `/renta-co:setup`, así que no supongas que ya
está definido.

`--csv` es una bandera sin valor: escribe `03-analisis/escenarios.csv`. El
año va en `--anio`, aparte.

```bash
"$RAIZ/bin/renta" verificar --expediente "$PWD/expediente"
"$RAIZ/bin/renta" calcular  --expediente "$PWD/expediente" --csv
```

Presenta la salida en este orden, que es el orden en que le importa a la
persona:

1. **Saldo a pagar o a favor** por la ruta que gana. Es lo único que quiere
   saber primero.
2. **Diferencia entre rutas**, en pesos.
3. **Tabla de sensibilidad.** Acá está el valor: qué papel vale la pena
   perseguir y cuál no.
4. **Riesgos en rojo**, empezando por R-01 (umbral de consignaciones).
5. **Qué falta**, ordenado por impacto en pesos.

Reglas:

- No hagas la aritmética tú. Lee la salida del CLI.
- Si `verificar` reporta errores, resuélvelos antes de calcular.
- Marca explícitamente lo que sea supuesto y qué documento lo cerraría.
- Cierra recordando que es un **borrador** y que hay que revisarlo con un
  contador público.

Si el usuario quiere entender por qué gana una ruta, invoca `renta-rutas`.
Si quiere bajar el impuesto, invoca `renta-deducciones`.
