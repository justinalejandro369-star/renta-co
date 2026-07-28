---
description: Muestra en qué va el expediente y cuál es el siguiente paso
---

Revisa el estado del expediente y di, en menos de quince líneas, dónde va y
qué sigue.

```bash
"$RAIZ/bin/renta" verificar --expediente "$PWD/expediente"
```

Revisa también:

| Qué | Cómo |
|---|---|
| Archivos sin clasificar | ¿queda algo en `expediente/00-crudo/` que no esté en `01-soportes/`? |
| Ledger construido | ¿existe `expediente/02-datos/ledger.csv`? |
| Movimientos sin clasificar | ¿hay filas con categoría `desconocido`? |
| Cálculo corrido | ¿existe `expediente/03-analisis/escenarios.csv`? |
| Entregables | ¿qué hay en `expediente/04-entregables/`? |
| Riesgos | ¿existe `expediente/05-riesgos/riesgos.md`? |
| Privacidad | ¿se corrió el escaneo después del último cambio? |

Termina con **una sola** acción siguiente, la más importante, con el comando
o la pregunta concreta. No una lista de pendientes: la siguiente cosa que hay
que hacer.
