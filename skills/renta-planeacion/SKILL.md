---
name: renta-planeacion
description: Planeación tributaria del año en curso — dónde de verdad se paga menos el año que viene. Úsala después de cerrar una declaración, o cuando el usuario pregunte cómo pagar menos el próximo año, si le conviene el Régimen Simple, o qué debería hacer distinto.
---

# Planeación del año en curso

La declaración del año pasado ya está escrita: se optimiza en los márgenes. **La del año en curso todavía se puede cambiar entera.**

Esta es la parte que la gente no espera y la que más agradece. Hazla siempre, aunque no la pidan.

## Lo primero: cuántos meses quedan

Calcula cuántos meses faltan para el 31 de diciembre. Casi todo lo que sirve tiene esa fecha límite, y el valor de cada palanca depende de cuánto tiempo queda.

## 1. Aportes voluntarios a AFP o cuenta AFC — la palanca más grande

30% del ingreso, tope 3.800 UVT. Dentro del tope conjunto del 40%.

**La ventana se cierra el 31 de diciembre y no hay prórroga.**

Corre el motor con el año en curso y el ingreso proyectado, con y sin aportes al tope, y muestra la diferencia en pesos. Para un ingreso de tres cifras de millones, suelen ser varios millones de impuesto.

Condiciones que hay que decir completas:

- **AFC**: el retiro antes de 10 años sin destinarlo a vivienda pierde el beneficio y se recupera la retención.
- **AFP voluntario**: el retiro sin cumplir requisitos de pensión también.

Es plata que se inmoviliza. Dilo, con el número al lado, y que decida.

## 2. Facturación electrónica y documento soporte — habilita todo lo demás

Sin factura electrónica a su nombre:

- No hay deducción del 1% por compras (240 UVT, fuera del tope).
- Los costos de la Ruta A quedan sin piso.

Qué hacer desde ya:

- Pedir factura electrónica **con su cédula o NIT** en toda compra grande, y pagar por medio electrónico.
- Si le paga a contratistas: documento soporte al momento del pago, y **pedirle la PILA a cada uno cada mes**, no en julio del año siguiente.

## 3. Seguridad social propia

Cotizar sobre el 40% de los ingresos:

- Los aportes obligatorios son **INCRNGO**: restan antes del tope del 40% y no lo consumen. Es la mejor posición que existe.
- Cierra la exposición ante la UGPP, que es un frente aparte con sus propias sanciones.

Si viene sin cotizar de años anteriores, decirlo: el problema no se resuelve solo y crece.

## 4. Dependientes — revisar cada año

La condición cambia: un hijo cumple 18, un padre empieza a recibir pensión, un hermano entra a estudiar.

72 UVT por dependiente, fuera del tope, sin factura. **Revisarlo cada año y guardar el soporte en el momento**, no cuando toque declarar.

## 5. Donaciones bien hechas

Si dona, que done a una entidad del **Régimen Tributario Especial** y que **exija el certificado en el momento de donar**. Descuento del 25% del valor donado.

Es la diferencia entre donar y que valga $0, y donar exactamente lo mismo y recuperar el 25%.

## 6. Medicina prepagada

16 UVT/mes, tope 192 UVT. Dentro del tope del 40% — verificar con el motor si el tope ya está saturado antes de recomendarla como palanca fiscal. Si lo está, vale cero fiscalmente y la decisión es de salud, no tributaria.

## 7. Régimen Simple — mandarlo al contador, no modelarlo acá

Inscripción hasta el **último día hábil de febrero** del año en que se quiere tributar bajo el régimen. No aplica retroactivamente.

Para servicios profesionales las tarifas son altas y **no admiten costos ni deducciones**, así que para el perfil típico de freelance con costos reales suele no convenir. Hay casos con márgenes altos, pocos gastos y mucho ICA donde sí gana.

**El motor NO lo liquida** — está en «lo que NO hace» del README — y tú tampoco. La comparación Simple vs. ordinario exige las tarifas del art. 908 por grupo de actividad, el descuento del art. 912 y el ICA consolidado, y ninguno de esos está en `knowledge/`. Hacer la cuenta a mano viola la regla del proyecto: **la aritmética la hace el motor**, y un número inventado sobre un régimen al que hay que inscribirse antes de febrero es de los que cuestan un año entero.

Lo que sí haces: decir que existe, decir la fecha límite, decir por qué normalmente no conviene para este perfil, y mandarlo al contador con la cifra de ingresos y de costos reales que el motor SÍ calculó. Si alguien lo implementa, va con sus tarifas en `knowledge/<año>/parametros.toml` y con fuente, como todo lo demás.

## 8. Umbral de consignaciones — vigilarlo durante el año

Si el año pasado quedó cerca de las 3.500 UVT de consignaciones, este año hay que vigilarlo **antes** de pasarse, no después.

**Abrir otra cuenta propia no sirve:** el umbral se mide sobre las consignaciones del contribuyente, no por cuenta. Y ese consejo se lee como esconder el flujo, que es lo contrario de lo que hace esta herramienta.

Lo que sí funciona:

- **Separar el flujo de terceros de verdad.** Que el cliente le pague directo a cada contratista, en vez de que todo pase por ti. Cambia el hecho, no la apariencia.
- **Verificar el calificador.** Solo cuentan las consignaciones provenientes de actividades **gravadas con IVA**. Si tu actividad es exportación de servicios (art. 481 lit. c), la cifra relevante puede ser cero: lo que hay que hacer es dejar el registro en el RUT y el contrato en orden.
- **Inscribirse y facturar a tarifa 0%** si de todos modos se supera. Obliga a declarar IVA, pero a tarifa cero y sin sanción.

## Cierre

Escribe `expediente/04-entregables/planeacion-<año>.md` con:

- **Calendario** con las fechas límite reales, en orden.
- **Cuánto suma todo**, en pesos, si se ejecuta completo.
- **Qué hacer este mes**, concreto. No una lista de buenas intenciones: tres acciones con fecha.

Sé específico con las fechas. "Antes de fin de año" no mueve a nadie; "antes del 31 de diciembre, quedan N meses" sí.
