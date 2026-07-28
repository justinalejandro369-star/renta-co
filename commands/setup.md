---
description: Crea el expediente, protege los datos con .gitignore y arranca el proceso de la declaración
argument-hint: "[--con-hooks] [--sin-red] [--anio 2025]"
---

Invoca la skill `renta-onboarding` y ejecuta su Paso 1 y Paso 2.

Argumentos: $ARGUMENTS

- `--con-hooks` → además instala el hook `pre-commit` que corre
  `scripts/escanear_privacidad.py --staged` y bloquea el commit si encuentra
  datos personales.
- `--sin-red` → el motor NO guarda esta preferencia; el flag vive en
  `importar`. Explícale al usuario que tendrá que pasar `--sin-red` cada vez
  que importe, y cómo cargar la serie a mano en
  `expediente/02-datos/trm-cache.csv` (columnas `fecha,trm`). Déjalo anotado
  en `expediente/00-crudo/LEEME.md` para que no se le olvide.
- `--anio N` → año gravable. Por defecto, el año anterior al actual.

Orden estricto, sin saltarse pasos:

1. **Primero el `.gitignore`.** Antes de crear un solo archivo con datos.
   Si ya existe, agrega las reglas que falten sin borrar lo que haya.
2. Crea el árbol `expediente/` con sus seis subdirectorios.
3. Copia `templates/perfil.ejemplo.toml` → `expediente/perfil.toml`.
4. Verifica que exista `knowledge/ag<año>/parametros.toml`. Si no, dilo y
   ofrece crearlo a partir de `ag2025`, advirtiendo que hay que verificar
   cada cifra contra la norma vigente.
5. Haz las **cinco** preguntas de arranque de `renta-onboarding`, y no más.
   La quinta —«¿tuviste salario, pensión, ganancia ocasional o arriendos?»—
   es la que detecta lo que este motor NO cubre, y va al principio, no al
   final. Sin ella, un pensionado obtiene una liquidación completa de
   honorarios sin una sola advertencia: es el único error de esta
   herramienta que no se ve mirando el resultado. Nunca la saltes.
6. Da la instrucción de soltar todo en `expediente/00-crudo/` sin ordenar.

Termina confirmando, en una línea, que los datos quedaron fuera de git.
