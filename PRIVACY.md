# Privacidad

Este proyecto toca cédula, extractos bancarios, patrimonio y datos de familia. La privacidad acá es una decisión de arquitectura, no una promesa en un README.

## La regla central

**El código y los datos viven separados, físicamente.**

- `renta-co` es lo que instalas. Es público, no contiene datos y no los recibe.
- `./expediente/` es tuyo. Vive en tu proyecto, en tu máquina, y está ignorado por git desde que `/renta-co:setup` lo crea.

Ningún archivo del expediente entra al árbol del plugin. Ningún dato tuyo llega al repositorio de nadie.

## Qué sale a la red

Exactamente dos cosas, y ninguna lleva datos tuyos:

| Qué | A dónde | Qué se envía |
|---|---|---|
| Serie TRM diaria | `datos.gov.co` (Banco de la República, dato público) | Un rango de fechas — y hay que decir cuál: son **las fechas del primer y del último movimiento en moneda extranjera de tu ledger**. En corridas incrementales, los días nuevos. Como toda petición HTTP, también llega tu IP |
| Consulta de normativa | El buscador o sitio que use tu agente, solo cuando se lo pides | El término de búsqueda |

La TRM se cachea en `expediente/02-datos/trm-cache.csv` después de la primera descarga. Si prefieres cero red, descarga la serie una vez y ponla ahí a mano: `/renta-co:setup --sin-red` te explica cómo.

## Qué garantiza el CI

El repositorio corre un escaneo en cada push y en cada PR: sobre el árbol de trabajo y sobre las líneas que el PR agrega a la historia, porque agregar un dato en un commit y borrarlo en el siguiente dejaba el árbol limpio y el dato vivo para siempre.

Lo que eso **no** garantiza: que el escáner detecte todo (ver sus límites arriba), ni nada sobre archivos en formatos que no sabe abrir. Es una red mecánica que evita el descuido más común, no una prueba de ausencia.

## Qué NO hay

- Sin telemetría.
- Sin analytics.
- Sin llamadas «anónimas» de uso.
- Sin cuenta que crear.
- Sin servidor. No hay backend.
- Sin subida de tus documentos a ningún servicio de OCR o parsing externo.

## Sobre tu agente de IA

Esto merece decirse claro, porque es el punto que la gente pasa por alto:

**El contenido de tus documentos pasa por el modelo de lenguaje que estés usando.** Cuando el agente lee tu extracto para clasificarlo, ese texto va al proveedor de tu agente (Anthropic, OpenAI, o el que sea) bajo los términos que tú ya aceptaste con ellos. `renta-co` no controla eso y no puede.

Qué puedes hacer al respecto:

- Revisa la política de retención de tu proveedor y desactiva el entrenamiento sobre tus datos si la opción existe.
- Si te preocupa, usa un modelo local. Las skills están escritas en Markdown plano y no dependen de ningún proveedor.
- El motor de cálculo (`engine/`) es Python determinista: corre entero sin modelo. Si quieres, puedes llenar `perfil.toml` a mano y no dejar que el agente vea un solo documento.

## Protecciones incluidas

**`.gitignore` generado en el setup.** `/renta-co:setup` escribe las reglas en tu proyecto antes de crear un solo archivo. Cubren `expediente/` y sus variantes de nombre, `perfil.toml`, los formatos de soporte y los CSV.

Lo que **no** cubre, y conviene saberlo: si guardas tu expediente en una carpeta con un nombre que no se parezca a ninguno de los patrones, no queda protegido. Corre `/renta-co:privacidad` antes de commitear y no dependas solo del `.gitignore`.

**Skill `renta-privacidad`.** Escanea texto y detecta cédulas, NIT, cuentas, tarjetas, correos, teléfonos, direcciones, rutas de usuario y los nombres propios de tu `perfil.toml`. Reporta archivo y línea, siempre enmascarado.

Sus límites, dichos de frente:

- **Es una heurística, no una garantía.** Un identificador escrito de una forma que no previmos puede pasar. Clasifica en confianza alta y baja para no ahogarte en falsos positivos, y solo la alta bloquea un commit.
- **No lee PDF, XLSX ni DOCX.** Los reporta como *no escaneados* en vez de omitirlos en silencio, pero revisarlos es tuyo — y son justo los formatos que el onboarding te pide soltar.
- Úsalo como red de seguridad, no como permiso para dejar de mirar.

**Hook pre-commit opcional.** `/renta-co:setup --con-hooks` instala un hook que lee los **blobs del índice** —no el archivo en disco— y bloquea el commit si encuentra algo de confianza alta. Es opcional porque un hook que la gente no entiende termina desactivado con `--no-verify`, y eso es peor que no tenerlo.

**`expediente.ejemplo/`.** Un contribuyente ficticio completo. Prueba el flujo entero, reporta bugs y comparte pantallazos sin exponer nada tuyo.

Si lo usas de plantilla para tus datos, **cópialo a `expediente/` primero**. Los archivos que el motor genera dentro de `expediente.ejemplo/` están ignorados, pero trabajar con datos reales dentro del árbol del repositorio es pedir un accidente.

## Si vas a reportar un bug

No pegues tu expediente. Reproduce el problema contra `expediente.ejemplo/` o corre `/renta-co:privacidad` sobre lo que vas a pegar. Un issue con la cédula de alguien queda indexado por Google para siempre.

## Borrar todo

El plugin no guarda estado en ningún lado propio: ni en `~/.claude`, ni en un caché global, ni en variables de entorno. Todo lo tuyo vive donde apunte `--expediente`.

Con el flujo normal eso es un solo directorio y `rm -rf expediente/` no deja nada. Pero `--expediente` acepta cualquier ruta: si lo corriste apuntando a otro sitio, ahí quedaron el `ledger.csv`, el caché de TRM y los escenarios. Búscalos antes de dar por hecho que borraste todo:

```bash
find . -name 'ledger*.csv' -o -name 'trm-cache.csv' -o -name 'perfil.toml'
```
