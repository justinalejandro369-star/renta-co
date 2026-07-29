# Seguridad

## Qué es una vulnerabilidad en este proyecto

Este repositorio no expone un servicio ni guarda datos de nadie: corre en tu
máquina, sobre tus archivos, sin red salvo para la TRM oficial. El modelo de
amenaza es distinto al de una aplicación web, y hay dos clases de falla que
para nosotros pesan tanto como una ejecución remota de código.

**1. Fuga de datos personales.** Cualquier camino por el que un dato del
expediente —una cédula, una cuenta, un nombre, una ruta de tu máquina— pueda
terminar en un commit, en un issue, en la salida de una skill o en un
artefacto publicado. Ya pasó: la ruta HOME real del mantenedor estuvo
publicada en GitHub durante cuarenta commits, y el guardia escrito
específicamente contra ese bug solo corría en su máquina porque su lista de
nombres ficticios incluía el usuario de CI.

Si encuentras una forma de que un dato personal escape al escáner
(`scripts/escanear_privacidad.py`), a `bin/renta privacidad --staged`, al
inventario de `.privacidadignore` o al paso de historia de CI, **eso es una
vulnerabilidad** y agradecemos el reporte privado.

**2. Un número creíble y equivocado.** Este proyecto produce cifras que
alguien transcribe a un formulario con consecuencias legales. Un cálculo
silenciosamente mal —no un error, un resultado plausible— es el peor modo de
falla que tiene. Si encuentras un perfil válido para el que el motor liquida
mal **sin advertirlo**, trátalo como un reporte de seguridad y no como un bug
normal.

Los ejemplos reales que ya costaron: un separador decimal mal interpretado
producía un factor mil con código de salida 0; un empate resuelto por el
orden de una lista movía la base declarada $4.414.472.

## Cómo reportar

Abre un **security advisory privado** en GitHub (pestaña *Security* →
*Report a vulnerability*). Si prefieres un issue público, adelante — pero
**no pegues datos reales en él**. Reproduce contra `expediente.ejemplo/`, o
corre `/renta-co:privacidad` sobre lo que vayas a pegar. Un issue con la
cédula de alguien queda indexado para siempre.

Sin SLA formal: esto lo mantiene una persona. Se responde lo antes posible.

## Alcance

**Dentro:**

- Fuga de datos personales por cualquiera de las compuertas de privacidad
- Liquidación incorrecta y silenciosa para un perfil válido
- Ejecución de código a partir de un archivo de entrada (CSV, TOML, caché de
  TRM) sin que el usuario lo pida
- Escrituras fuera del directorio del expediente
- Cualquier tráfico de red que no sea la consulta de la TRM oficial

**Fuera:**

- Que el motor rechace un caso que declara FUERA DE ALCANCE (salario,
  pensión, ganancia ocasional): eso es la guarda funcionando
- Desacuerdos de interpretación normativa. Van a un issue normal, con la
  fuente primaria — es la conversación más valiosa que puede tener este repo
- Que el resultado difiera del de otro software o del de un contador. Este
  proyecto no reclama autoridad; reclama trazabilidad

## Lo que este proyecto NO promete

- **No es asesoría tributaria.** Ver [DISCLAIMER.md](DISCLAIMER.md).
- **No está verificado por un contador público.** Ver
  [.github/CODEOWNERS](.github/CODEOWNERS): la línea existe y el revisor
  todavía no.
- **Dos normas declaradas como no implementadas correctamente.** La sección
  «Estado» del README se genera de las banderas del propio `knowledge/`.

## Dependencias

Cero dependencias externas de Python, a propósito. La superficie de
suministro es la biblioteca estándar y nada más, así que no hay `pip audit`
que correr ni un `requirements.txt` que envenenar.

`scripts/verificar_citas.py` invoca `curl` como respaldo cuando un servidor
normativo sirve una cadena TLS incompleta. Nunca con `-k` ni `--insecure`: un
chequeo que acepte cualquier certificado no puede afirmar de qué servidor
salió el texto, que es la mitad de su valor.
