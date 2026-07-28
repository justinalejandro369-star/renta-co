---
name: renta-privacidad
description: Escanea archivos en busca de datos personales antes de compartirlos o commitearlos — cédulas, NIT, números de cuenta, nombres, correos, direcciones. Úsala antes de que el usuario mande algo a su contador, pegue un fragmento en un issue, o haga commit. También cuando pregunte si es seguro compartir algo o si sus datos están protegidos.
---

# Escaneo de privacidad

Un expediente tributario es de lo más sensible que hay: cédula, patrimonio, movimientos, familia. Un archivo que termina en un repo público queda indexado para siempre.

## Cuándo se corre

- Antes de mandarle algo al contador.
- Antes de pegar cualquier cosa en un issue, un foro, un chat o un post.
- Antes de cualquier `git commit` en el proyecto del usuario.
- Cuando el usuario pregunte si es seguro compartir algo.
- Al terminar el flujo completo, sin que lo pidan.

## Cómo

```bash
python3 scripts/escanear_privacidad.py expediente/04-entregables/
python3 scripts/escanear_privacidad.py --perfil expediente/perfil.toml archivo.md
```

Con `--perfil` también busca los nombres propios que aparezcan en el perfil, que es lo que un patrón genérico nunca va a atrapar.

## Qué busca

| Patrón | Ejemplo |
|---|---|
| Cédula colombiana | 8–10 dígitos, con o sin puntos |
| NIT con dígito de verificación | `900.123.456-7` |
| Números de cuenta bancaria | secuencias de 9–20 dígitos |
| Tarjetas | 13–19 dígitos, validado con Luhn |
| Correos | cualquiera |
| Teléfonos colombianos | `+57 3XX XXXXXXX`, celulares |
| Direcciones | `Calle`, `Carrera`, `Cra`, `Kr`, `Av`, `Diagonal` + números |
| Nombres del perfil | solo con `--perfil` |
| Rutas de usuario | `/Users/<nombre>`, `/home/<nombre>` |

## Cómo reportar

No basta con decir "encontré 12 coincidencias". Da archivo, línea, tipo, y el fragmento **enmascarado**:

```
expediente/04-entregables/memo-contadora.md
  línea  3  cédula          1.0XX.XXX.781
  línea 14  cuenta bancaria XXXXXXX931
  línea 22  correo          j****@gmail.com
```

**Nunca imprimas el dato completo en el reporte.** Enmascararlo es el punto.

## Qué hacer con cada hallazgo

Distingue lo que es un problema de lo que no:

| Situación | Qué hacer |
|---|---|
| Va a un repo público o un issue | **Bloquear.** Hay que quitarlo o reemplazarlo por un placeholder |
| Va al contador por correo | Está bien que esté — el contador lo necesita. Solo confirma que el destinatario es correcto |
| Está en `expediente/` y se queda ahí | Correcto. Ahí es donde debe estar |
| Está fuera de `expediente/` | **Revisar.** Probablemente se escapó a un archivo que sí se commitea |

La pregunta que decide no es "¿hay datos personales?" sino **"¿a dónde va este archivo?"**. Pregúntalo antes de alarmar.

## Verificar el `.gitignore`

Confirma que el proyecto ignore, como mínimo:

```
expediente/
perfil.toml
*.pdf
*.xlsx
*.zip
ledger*.csv
```

Y comprueba que no haya nada ya rastreado por git que debiera estar ignorado:

```bash
git ls-files | grep -Ei 'expediente|perfil\.toml|\.pdf$|\.xlsx$|ledger.*\.csv'
```

Si algo aparece, avisa: **agregarlo al `.gitignore` no lo saca del historial.** Hay que sacarlo del índice, y si ya se hizo push, el dato está publicado — se debe asumir comprometido y rotar lo que se pueda rotar.

No corras reescrituras de historial por tu cuenta. Explica la situación y deja que el usuario decida.

## Hook opcional

`/renta-co:setup --con-hooks` instala un `pre-commit` que corre este escaneo y bloquea el commit si encuentra algo. Es opcional a propósito: un hook que la gente no entiende termina desactivado con `--no-verify`, y eso es peor que no tenerlo.

## Lo que hay que decirle al usuario

Que el escaneo cubre lo que sale de su máquina en archivos, pero **no** cubre lo que ya pasó por el modelo de lenguaje que está usando. Cuando el agente leyó su extracto para clasificarlo, ese contenido fue al proveedor del agente bajo los términos que él ya aceptó.

Está en `PRIVACY.md` y vale la pena decirlo en voz alta al menos una vez, sin dramatizar: es un hecho del medio, no un defecto de la herramienta.
