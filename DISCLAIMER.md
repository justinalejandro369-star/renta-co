# Aviso legal

**`renta-co` no es asesoría tributaria, contable ni legal.**

Es una herramienta de organización documental y de cálculo. Ordena tus soportes, aplica una fórmula pública a los datos que tú le das, y produce un borrador para que lo revises.

## Lo que esto significa en la práctica

**La responsabilidad de la declaración es tuya.** El art. 746 del Estatuto Tributario presume ciertos los hechos declarados, y las sanciones por inexactitud (art. 648 ET) recaen sobre el contribuyente. Ninguna herramienta cambia eso.

**Revisa el resultado con un contador público.** El entregable `memo-contador.md` existe justamente para eso: está escrito para que un profesional lo pueda contrastar renglón por renglón en pocos minutos. No es un extra opcional; es parte del flujo.

**El resultado depende por completo de lo que le des.** Si falta un ingreso, la declaración queda mal. La herramienta te dice qué falta, pero no puede saber lo que nunca vio.

**La normativa cambia.** Los parámetros en `knowledge/` se mantienen por la comunidad y pueden quedar desactualizados. Cada cifra trae su fuente citada — verifícala si el monto es material para ti.

**Nadie presenta nada por ti.** `renta-co` no se conecta al MUISCA, no tiene tu firma electrónica y no radica declaraciones. La presentación la haces tú, en el portal de la DIAN.

## Sin garantía

El software se entrega "tal cual", sin garantía de ningún tipo, según los términos de la licencia MIT. Los autores y contribuyentes no son responsables por sanciones, intereses, mayores impuestos ni ningún otro daño derivado del uso de esta herramienta.

## Sobre posiciones tributarias

Algunas decisiones tributarias son legítimas pero discutibles. Cuando el caso lo amerite, `renta-co` deja registro de la posición en `05-riesgos/` con su fundamento normativo y su probabilidad de objeción, para que la decisión se tome informada.

La herramienta está construida sobre un criterio explícito: **se documentan operaciones reales con fechas y montos reales, y se toman todas las deducciones y descuentos que la ley permite.** No antedata documentos, no inventa gastos y no oculta ingresos. Si le pides que lo haga, no lo va a hacer.
