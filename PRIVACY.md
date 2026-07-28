# Privacidad

Este proyecto toca cédula, extractos bancarios, patrimonio y datos de familia. La privacidad acá es una decisión de arquitectura, no una promesa en un README.

## La regla central

**El código y los datos viven separados, físicamente.**

- `renta-co` es lo que instalas. Es público, no contiene datos y no los recibe.
- `./expediente/` es tuyo. Vive en tu proyecto, en tu máquina, y está ignorado por git desde que `/renta:setup` lo crea.

Ningún archivo del expediente entra al árbol del plugin. Ningún dato tuyo llega al repositorio de nadie.

## Qué sale a la red

Exactamente dos cosas, y ninguna lleva datos tuyos:

| Qué | A dónde | Qué se envía |
|---|---|---|
| Serie TRM diaria | `datos.gov.co` (Banco de la República, dato público) | Un rango de fechas. Nada más |
| Consulta de normativa | El buscador o sitio que use tu agente, solo cuando se lo pides | El término de búsqueda |

La TRM se cachea en `expediente/02-datos/trm-cache.csv` después de la primera descarga. Si prefieres cero red, descarga la serie una vez y ponla ahí a mano: `/renta:setup --sin-red` te explica cómo.

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

**`.gitignore` generado en el setup.** `/renta:setup` escribe estas reglas en tu proyecto antes de crear un solo archivo:

```
expediente/
perfil.toml
*.pdf
*.xlsx
*.zip
ledger*.csv
```

**Skill `renta-privacidad`.** Escanea cualquier salida antes de que la compartas y detecta cédulas, NIT, números de cuenta, nombres tomados de tu `perfil.toml`, direcciones y correos. Reporta archivo y línea. Úsala antes de mandarle algo a tu contador por correo, o antes de pegar un fragmento en un issue.

**Hook pre-commit opcional.** `/renta:setup --con-hooks` instala un hook que bloquea el commit si detecta esos patrones. Es opcional porque un hook que la gente no entiende termina desactivado.

**`expediente.ejemplo/`.** Un contribuyente ficticio completo. Prueba el flujo entero, reporta bugs y comparte pantallazos sin exponer nada tuyo.

## Si vas a reportar un bug

No pegues tu expediente. Reproduce el problema contra `expediente.ejemplo/` o corre `/renta:privacidad` sobre lo que vas a pegar. Un issue con la cédula de alguien queda indexado por Google para siempre.

## Borrar todo

Tus datos están en un solo directorio. `rm -rf expediente/` y no queda nada. El plugin no guarda estado en ningún otro lado — ni en `~/.claude`, ni en un caché global, ni en variables de entorno.
