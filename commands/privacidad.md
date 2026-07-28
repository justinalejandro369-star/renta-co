---
description: Escanea archivos en busca de datos personales antes de compartirlos o commitearlos
argument-hint: "[ruta] [--staged]"
---

Invoca la skill `renta-privacidad`.

Objetivo del escaneo: $ARGUMENTS
Si no se dio ninguno, escanea `expediente/04-entregables/` y, si existe, la
raíz del proyecto excluyendo `expediente/`.

Ejecuta:

```bash
python scripts/escanear_privacidad.py --perfil expediente/perfil.toml <objetivo>
```

Después del escaneo:

1. Reporta los hallazgos **enmascarados**, con archivo y línea.
2. Para cada uno, pregunta o deduce **a dónde va ese archivo**. Es lo que
   decide si es un problema. Un dato personal dentro de `expediente/` está
   donde debe estar.
3. Verifica el `.gitignore` y corre:
   `git ls-files | grep -Ei 'expediente|perfil\.toml|\.pdf$|\.xlsx$|ledger.*\.csv'`
4. Si algo ya está rastreado por git, **dilo con claridad**: agregarlo al
   `.gitignore` no lo saca del historial, y si ya se hizo push hay que
   asumirlo publicado. No reescribas historial por tu cuenta.
