---
name: Bug del motor o de la capa de datos
about: Algo se calcula, importa o convierte mal
title: "[bug] "
labels: bug
---

> **No pegues datos reales.** Reproduce contra `expediente.ejemplo/` o corre
> `/renta-co:privacidad` sobre lo que vayas a pegar. Un issue con la cédula
> de alguien queda indexado para siempre.
>
> Si el motor liquida mal **sin advertirlo** —un número plausible y
> equivocado, no un error— trátalo como reporte de seguridad: ver
> [SECURITY.md](../SECURITY.md).

## Perfil mínimo que lo reproduce

```toml
[contribuyente]
anio_gravable = 2025
residente_fiscal = true

[ingresos]
rentas_trabajo_honorarios = 0
```

## Comando

```bash
python3 -m engine.cli calcular --expediente ...
```

## Qué esperabas y qué salió

**Esperado:**
**Obtenido:**
**¿Salió con código de salida 0?** — Importa: un resultado equivocado que
sale en silencio es peor que uno que revienta.

## Entorno

- Python:
- Sistema operativo:
- Commit (`git rev-parse --short HEAD`):
