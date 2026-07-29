# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado: [SemVer](https://semver.org/lang/es/).

> **Este proyecto no tiene todavía una versión etiquetada, y es a propósito.**
> Etiquetar `v1.0.0` un motor que declara dos normas mal implementadas sería
> firmar algo que no está firmado. Ver la sección «Estado» del README, que se
> genera de las banderas de `knowledge/` y no se escribe a mano.
>
> El changelog empieza en la ronda 8. Las siete anteriores están en el
> historial de commits, donde cada mensaje explica **qué se rompió y cómo**,
> que en este repositorio vale más que un resumen.

## [Sin publicar] — ronda 8

Todo lo de esta ronda salió de un escuadrón de mejora que miró afuera: qué
hacen otros proyectos de impuestos open source, cómo verifican los que
verifican de verdad, y qué hace un contador que este motor no hacía.

### Añadido

- **Chequeo de citas contra la fuente primaria**
  (`scripts/verificar_citas.py`, solo stdlib). Detecta el *soft-404* por la
  URL FINAL y no por el estado HTTP —la URL muerta que tuvo este repo
  devolvía 302 → `norma_error.php` → **HTTP 200**, y cualquier link-checker
  del mercado la reporta sana—, comprueba que cada `cita_literal` aparezca
  palabra por palabra, y congela el `sha256` del texto contra el *content
  drift*. Corre en un job **semanal** aparte, nunca en `make test`.
- **Relación metamórfica de homogeneidad en UVT** (séptima de la quinta
  capa). Escalar todos los pesos y la UVT por *k* tiene que escalar el
  impuesto por *k*: atrapa cualquier cifra escrita en pesos donde el Estatuto
  la pone en UVT, que es el error invisible por excelencia porque no cambia
  nada hasta que la UVT cambia.
- **Sexta capa: cobertura del espacio de entrada.** Mide qué regiones no
  visita ninguna persona del corpus. Nueve huecos al empezar, incluidos los
  dos tramos superiores del art. 241 y las dos zonas de castigo que el motor
  calcula y anuncia sin que nadie las hubiera visto funcionar.
- **Séptima capa: golden master** (`benchmark/golden.json`). La única que
  pregunta «¿esto cambió, y alguien lo decidió?». Habría atrapado las dos
  regresiones de la ronda 7 en el commit siguiente.
- **Octava capa: oráculo del formulario 210.** Las ecuaciones entre casillas
  impresas en el formulario son aritmética publicada por la autoridad. Es el
  único oráculo externo disponible sin credenciales.
- **R-15** · renta por comparación patrimonial (arts. 236 y 237).
- **R-16** · beneficio de auditoría (art. 689-3): firmeza en 6 meses en vez
  de 36. Cero menciones en el repo hasta ahora, y es la palanca de planeación
  más grande que existe para el perfil objetivo.
- **R-17** · conciliación contra la información exógena, con plantilla propia
  (`templates/conciliacion-exogena.md`) que cubre el lado de las retenciones.
- **Firmeza y conservación** en `knowledge/`, en la plantilla de riesgos y en
  `PRIVACY.md`, que enseñaba a borrar el expediente sin decir que es el papel
  de trabajo de la declaración.
- `CODEOWNERS`, `SECURITY.md`, `CHANGELOG.md` y plantillas de issue.
- Tres personas nuevas en el benchmark (P18–P20), escritas contra la
  medición de cobertura y no contra una intuición de qué faltaba.

### Corregido

- **Cuarta cita inexacta**, encontrada por `verificar_citas.py` en su primera
  corrida: el Decreto 2231 art. 3 dice «reglamentaria: caso en el cual» con
  dos puntos, y el TOML tenía coma. Dos revisiones humanas la leyeron al lado
  de la fuente y ninguna la vio.
- **Quinta cita inexacta**, y la única cuyo error cambiaba el CÁLCULO: el
  art. 237 no son «ajustes por inflación» sino la fórmula de comparación.
  Con la descripción inventada, R-15 habría acusado de patrimonio
  injustificado a quien tiene rentas exentas altas.
- **Las cuatro casillas del 210 no cuadraban entre sí.** Se aproximaban al
  múltiplo de mil por separado, así que quien transcribiera la base y
  liquidara sobre ella obtenía otro impuesto: 3 de 40 liquidaciones del
  benchmark discrepaban en $1.000. El redondeo ahora se encadena.
- **El inventario de privacidad filtraba las joyas de la corona.**
  Descartaba cédula, cuenta, NIT y tarjeta «porque los tests las producen de
  por sí», así que una cédula real en un archivo excluido pasaba los tres
  pasos de CI en verde. Una lista de excepciones por forma es una lista de lo
  que hay que usar para colar un dato.
- **`ag2026` heredaba `url_verificada` de `ag2025`**: presentaba como propias
  citas que nadie abrió para ese año.
- **`LICENSE`** tenía texto pegado después del MIT, así que GitHub la
  clasificaba como «Other» mientras el badge decía MIT.

### Cambiado

- El README se reencuadra como **auditor de segunda opinión**, no como
  preparador, y su sección «Estado» se **genera** de las banderas
  `motor_implementa_correctamente` con
  `scripts/estado_del_motor.py`. Escribirla a mano habría reproducido en un
  mes el desfase que ya tuvo el catálogo de riesgos.
- El escáner de privacidad ya no reporta un digesto hexadecimal de 32+
  caracteres como cédula. Octava vez que un artefacto de este repo dispara al
  detector que el repo escribió; las anteriores se cerraron con «descríbelo,
  no lo transcribas», pero con un `sha256` esa regla no sirve porque el hash
  ES el dato.

### Sin resolver

Las doce ALTA de la ronda 7 que no toca esta ronda siguen abiertas, entre
ellas el techo de costos aplicado al revés de la norma y los costos sin
atribuir sin ningún techo. Están en el handoff, con lo que cuesta cada una en
pesos.
