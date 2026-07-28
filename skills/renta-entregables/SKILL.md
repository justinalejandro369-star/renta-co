---
name: renta-entregables
description: Produce los entregables finales — checklist de documentos, comparativo de rutas, memo para el contador y borrador del Formulario 210. Úsala cuando ya estén los cálculos y haya que generar los documentos para revisar o presentar, o cuando el usuario pida el resumen, el memo, o el 210.
---

# Entregables

Cinco archivos en `expediente/04-entregables/`. Cada uno tiene su plantilla en `templates/`, con el mismo nombre.

## 1. `checklist-documentos.md`

Lo que falta, **ordenado por pesos**, no por orden alfabético ni por facilidad.

Cada ítem lleva:

- Qué es exactamente y a quién se le pide.
- **Cuánto vale en impuesto**, tomado de la tabla de sensibilidad del motor.
- Si es bloqueante o no.

```markdown
### 5. Certificado de estudio de tu hermana — vale **$3.585.528** de deducción
Se pide en la secretaría de la universidad. Sirve para acreditarla como
dependiente (72 UVT, fuera del tope del 40%). No exige factura ni gasto.
```

Agrupa en cuatro bloques:

- 🔴 **Bloqueantes** — sin esto no se presenta
- 🟠 **Alto impacto** — dinero directo
- 🟡 **Patrimonio** — obligatorio, sin efecto en el impuesto pero sí en riesgo
- 🔵 **Cierre** — baja probabilidad, hay que descartarlo

Poner el valor en pesos al lado de cada papel es lo que hace que la gente efectivamente los consiga.

⚠ **Usa siempre impuesto ahorrado, no base deducida.** Son la tabla de sensibilidad y el perfil, respectivamente, y se diferencian por la tarifa marginal. Mezclarlas en la misma lista infla los números entre 3 y 5 veces y destruye la confianza cuando el usuario lo nota.

## 2. `comparativo.md`

La salida de `"$RAIZ/bin/renta" calcular --csv`, en prosa:

- Tabla renglón por renglón, ambas rutas.
- Cuál gana y por cuánto.
- Tabla de sensibilidad completa.
- **Los supuestos**, marcados como tales, con qué documento los convierte en dato.
- La lista de partidas que **no** son deducibles y por qué — para que nadie las meta después.

## 3. `memo-contador.md`

El más importante y el que casi nadie escribe. Está hecho para que un contador lo lea en cinco minutos y pueda objetar con precisión.

Estructura:

```markdown
# Memo — Declaración de renta AG <año>

## Resumen
Ruta elegida, base gravable, impuesto, saldo. Cuatro líneas.

## Cómo se construyó cada cifra
Renglón → de qué documento salió → qué supuesto tiene, si tiene.

## Los ocho puntos a contrastar
Lo que quiero que revises específicamente, con la norma citada.

## Posiciones que tomé y por qué
Las discutibles, con su fundamento y su riesgo. Sin esconderlas.

## Lo que dejé por fuera a propósito
Partidas que parecían deducibles y no lo son, con el motivo.

## Qué falta
Documentos pendientes y qué cambia cada uno.
```

Escríbelo en primera persona del contribuyente. Va a salir de su correo, no del tuyo.

## 4. `formulario-210.md`

Borrador renglón por renglón, con el número de casilla del Formulario 210 y de dónde sale cada cifra.

⚠ **Verifica la numeración de casillas contra el formulario oficial del año gravable antes de escribirla.** La DIAN cambia renglones entre años y una casilla equivocada es un error de transcripción caro. Si no puedes verificarla, escribe el concepto sin número de casilla y déjalo anotado.

Encabezado obligatorio del archivo:

```
BORRADOR — no presentado ante la DIAN.
Revisar con contador público antes de radicar.
Generado por renta-co el <fecha>. Ver DISCLAIMER.md.
```

## 5. `planeacion-<año en curso>.md`

Invoca `renta-planeacion`. Plantilla en `templates/planeacion.md`.

## Reglas de escritura

**Cifras en pesos, con separador de miles.** `$3.585.528`, no `3585528` ni "tres millones y medio".

**Cada afirmación normativa con su artículo.** El contador va a verificar.

**Marca los supuestos.** Todo lo que no salga de un documento va marcado `SUPUESTO` con qué documento lo cerraría.

**Nunca escribas una cifra que no salga del motor o de un documento.** Si estás estimando, dilo en la misma línea.

## Antes de entregar

Corre `/renta-co:privacidad` sobre `04-entregables/`. Estos archivos son los que la persona va a mandar por correo o por WhatsApp, y son los que más fácil terminan donde no deben.
