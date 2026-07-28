---
description: Escanea archivos en busca de datos personales antes de compartirlos o commitearlos
argument-hint: "[ruta] [--staged]"
---

Invoca la skill `renta-privacidad`.

Objetivo del escaneo: $ARGUMENTS
Si no se dio ninguno, escanea `expediente/04-entregables/` y, si existe, la
raíz del proyecto excluyendo `expediente/`.

`$RAIZ` es la raíz de renta-co: el directorio que contiene `AGENTS.md` y
`bin/renta`. Instalado como plugin es `$CLAUDE_PLUGIN_ROOT`; clonado, es la
raíz del repo. Resuélvelo antes de correr nada — este comando se puede
invocar sin haber pasado por `/renta-co:setup`, así que no supongas que ya
está definido.

Ejecuta:

```bash
"$RAIZ/bin/renta" privacidad --perfil expediente/perfil.toml <objetivo>
```

Con `--staged`, el escáner mira los blobs del índice de git **del
directorio desde donde se invoca**, que es el repositorio del usuario. No
le pases rutas: se las pide a git.

```bash
"$RAIZ/bin/renta" privacidad --staged
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
