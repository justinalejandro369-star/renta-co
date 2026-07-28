# renta-co — instrucciones para el agente

Este repositorio ayuda a una persona natural en Colombia a preparar su
declaración de renta. Funciona en Claude Code, Codex CLI, Cursor y cualquier
agente que lea este archivo.

## Qué es esto

Un conductor de proceso + un motor de cálculo determinista.

- **El motor** (`engine/`) hace la aritmética. Python 3.11+, sin dependencias.
- **Las skills** (`skills/`) saben qué preguntar, en qué orden y por qué.
- **El conocimiento** (`knowledge/`) tiene la norma y los parámetros por año
  gravable, cada cifra con su fuente citada.

## Empezar

Si el usuario menciona declaración de renta, DIAN, formulario 210, impuestos
en Colombia, o dice que le toca declarar: **lee `skills/renta-onboarding/SKILL.md`
y síguela.** Es el punto de entrada y conduce todo el proceso.

## Las diez skills

| Skill | Cuándo |
|---|---|
| `renta-onboarding` | Punto de entrada. Crea el expediente y conduce el proceso |
| `renta-clasificar` | El usuario ya soltó sus archivos y hay que identificarlos |
| `renta-ingresos` | Determinar y clasificar ingresos, TRM diaria |
| `renta-patrimonio` | Activos y pasivos a 31 de diciembre |
| `renta-deducciones` | Encontrar todo lo que se puede restar |
| `renta-rutas` | Decidir entre costos y renta exenta del 25% |
| `renta-riesgos` | Registro de riesgos antes de cerrar |
| `renta-entregables` | Checklist, comparativo, memo al contador, borrador 210 |
| `renta-planeacion` | El año en curso, donde todavía se puede cambiar algo |
| `renta-privacidad` | Antes de compartir o commitear cualquier cosa |

## Comandos

```
/renta-co:setup        crea el expediente y arranca
/renta-co:auditar      corre el cálculo completo
/renta-co:estado       en qué va y qué sigue
/renta-co:privacidad   escanea datos personales antes de compartir
```

## Cómo invocar el motor — LEE ESTO ANTES DE CORRER NADA

El motor vive junto a este archivo. El expediente del usuario vive en **su**
proyecto, que es otro directorio. Son dos rutas distintas y confundirlas es
la causa número uno de que nada funcione.

**Usa siempre el lanzador `bin/renta`**, que resuelve su propia ubicación:

```bash
# RAIZ = el directorio que contiene este AGENTS.md.
# Instalado como plugin en Claude Code es $CLAUDE_PLUGIN_ROOT; clonado, es
# la raíz del repo. Resuélvelo UNA vez al empezar y reúsalo.

"$RAIZ/bin/renta" verificar  --expediente "$PWD/expediente"
"$RAIZ/bin/renta" importar   --expediente "$PWD/expediente"
"$RAIZ/bin/renta" calcular   --expediente "$PWD/expediente" --csv
"$RAIZ/bin/renta" parametros --anio 2025
"$RAIZ/bin/renta" privacidad "$PWD/expediente/04-entregables"
```

Reglas:

- **`--expediente` siempre con ruta absoluta.** El lanzador hace `cd` a su
  propia raíz; una ruta relativa apuntaría al sitio equivocado.
- Si `bin/renta` no es ejecutable en el entorno, el equivalente es
  `cd "$RAIZ" && python3 -m engine.cli <subcomando> --expediente <ruta absoluta>`.
- Nunca uses `python` a secas: en muchas máquinas es un shim que apunta a una
  versión anterior a 3.11 y falla por `tomllib`.

Para desarrollar sobre el repo:

```bash
make test        # suite completa
make benchmark   # 14 personas: invariantes, diferencial y anclas
make verificar   # todo lo que corre CI
```

## Reglas que no se rompen

**1. La aritmética la hace el motor, no tú.**
Nunca calcules el impuesto de cabeza ni "estimes" un resultado. Corre el CLI
y lee su salida. La confianza de este proyecto depende de que el número sea
reproducible por cualquiera que lea `engine/depuracion.py`.

**2. Nunca inventes una cifra.**
Si falta un dato, se marca como faltante y se reporta. Un cero supuesto que
se presenta como dato es un error caro y difícil de detectar después.

**3. Los datos personales viven solo en `./expediente/`.**
Nunca los copies a otro archivo, a un resumen, ni a nada que se commitee.
`expediente/` está en `.gitignore` desde el setup.

**4. Todo resultado es un BORRADOR.**
Nunca digas que una declaración "está lista para presentar". Este proyecto no
radica nada ante la DIAN y no reemplaza a un contador público. Ver
`DISCLAIMER.md`.

**5. No antedatar, no inventar gastos, no ocultar ingresos.**
Se documentan operaciones reales con fechas y montos reales, y se toman todas
las deducciones que la ley permite. Si te piden lo contrario: una frase, sin
sermón, y ofrece la alternativa legal.

**6. Las posiciones discutibles se registran, no se esconden.**
Van a `expediente/05-riesgos/` con su fundamento normativo y su probabilidad
de objeción, para que la decisión se tome informada.

**7. Cita la norma y explica qué significa.**
Primero qué implica en plata, después el artículo. Nunca al revés.

## Lo que más plata mueve, en orden

Si tienes poco tiempo o poca atención del usuario, prioriza así:

1. **Dependientes.** 72 UVT c/u, hasta 4, **fuera del tope del 40%**, sin
   factura. Padres y hermanos con ingresos anuales < 260 UVT cuentan, y es
   lo que más gente desconoce.
2. **Aportes obligatorios de salud y pensión.** Son INCRNGO: restan antes del
   tope y no lo consumen.
3. **Certificado de GMF de cada banco.** El 50% es deducible y casi nadie los
   pide todos.
4. **El umbral de consignaciones de 3.500 UVT.** No baja el impuesto, pero es
   la contingencia más grande y menos mirada del perfil freelance.
5. **Ruta A vs Ruta B.** Importante, pero con frecuencia vale menos que el
   punto 1.

## Estructura

```
skills/          las diez skills
commands/        los cuatro comandos
knowledge/       normativa y parámetros por año gravable, con fuentes
engine/          motor determinista + adaptadores de importación + tests
templates/       plantillas de entregables y del perfil
scripts/         escáner de privacidad
expediente.ejemplo/  caso ficticio completo, para probar sin exponer nada
```

## Al contribuir código

- Sin dependencias externas. Es una promesa del proyecto, no una preferencia.
- Cada cifra normativa nueva va en `knowledge/<año>/parametros.toml` **con su
  fuente**, nunca hardcodeada en Python.
- Los tests van con valores calculados a mano contra la norma, no copiados de
  la salida del programa.
- Cualquier muestra de datos en tests o docs va anonimizada. Corre
  `python3 scripts/escanear_privacidad.py` antes de hacer commit.
