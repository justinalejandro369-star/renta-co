# Memo — Declaración de renta AG {{año}}

Preparado con renta-co el {{fecha}}. **Borrador, no presentado ante la DIAN.**

---

## Resumen

| | |
|---|---|
| Ruta de depuración elegida | {{Ruta A — costos y gastos / Ruta B — renta exenta 25%}} |
| Renta líquida gravable | {{$X}} |
| Impuesto de renta (art. 241) | {{$X}} |
| Retenciones y anticipos | {{$X}} |
| **Saldo a {{pagar/favor}}** | **{{$X}}** |
| Diferencia frente a la otra ruta | {{$X}} |
| Patrimonio líquido a 31-dic | {{$X}} |

---

## Cómo se construyó cada cifra

| Renglón | Valor | De dónde sale | Supuesto |
|---|---|---|---|
| Rentas de trabajo | {{$X}} | {{archivo/certificado}} | {{ninguno / cuál}} |
| Rentas de capital | {{$X}} | {{}} | {{}} |
| INCRNGO | {{$X}} | {{}} | {{}} |
| Costos y gastos | {{$X}} | {{}} | {{}} |
| Deducciones | {{$X}} | {{}} | {{}} |
| Retenciones | {{$X}} | {{}} | {{}} |

Los ingresos en moneda extranjera se convirtieron con **TRM diaria de la
fecha de realización de cada operación** (art. 288 ET), con la serie oficial
del Banco de la República. No se usó promedio anual.

---

## Los puntos que te pido contrastar

1. **Ruta elegida.** Opté por {{ruta}} conforme al art. 336 num. 4 ET. El
   comparativo completo está en `comparativo.md`. La diferencia frente a la
   otra ruta es de {{$X}}.
2. **Dependientes.** Tomé {{N}} dependientes por 72 UVT (art. 336 par., Ley
   2277 de 2022 art. 7), **fuera del tope del 40%**. Soporte: {{cuál}}.
3. **Tope conjunto.** Aplicado en {{$X}} — el menor entre el 40% de los
   ingresos netos y 1.340 UVT. Se rechazaron {{$X}} por exceso.
4. **GMF.** Deduje el 50% del 4x1000 certificado por {{bancos}}, total {{$X}}.
5. **Aportes a seguridad social.** Tratados como INCRNGO, no como deducción,
   para que no consuman el tope del 40%.
6. **Patrimonio.** {{Completo / faltan los saldos de X, marcados como estimados}}.
7. **Umbral de consignaciones.** Total consignado en el año: {{$X}} contra el
   umbral de 3.500 UVT ({{$174.296.500}}). {{Dentro / SUPERADO — ver riesgos}}.
8. **Retención en la fuente.** No practiqué retención a contratistas. El art.
   368-2 ET solo obliga a personas naturales **comerciantes** que superen
   30.000 UVT del año anterior; no cumplo ninguna de las dos condiciones.

---

## Posiciones que tomé y por qué

{{Para cada posición discutible:}}

**{{Posición}}**
Fundamento: {{norma}}.
Riesgo: {{severidad}} — {{qué podría objetar la DIAN}}.
La tomé porque {{razón}}. Está registrada en `05-riesgos/riesgos.md`.

---

## Lo que dejé por fuera a propósito

Partidas que parecen deducibles y no lo son. Las listo para que no se
incluyan por error:

- **Intereses de tarjeta de crédito** ({{$X}}) — consumo personal, no
  financian la actividad productora de renta.
- **Traslados entre cuentas propias** ({{$X}}) — no son ingreso; contarlos
  inflaría la base.
- **Donaciones sin certificado del RTE** ({{$X}}) — sin la certificación del
  art. 257 ET valen $0.
- **Abono a capital del crédito de vivienda** — solo los intereses son
  deducibles.
- {{otros}}

---

## Qué falta

| Documento | Qué cambia | Valor estimado |
|---|---|---|
| {{}} | {{}} | {{$X}} |

---

## Cómo verificar los números

Todo el cálculo es reproducible:

```bash
python3 -m engine.cli calcular --expediente ./expediente
```

El motor es Python sin dependencias y la lógica está en
`engine/depuracion.py`. Los parámetros del año gravable, con la fuente de
cada cifra, están en `knowledge/ag{{año}}/parametros.toml`.

Si ves un error, dímelo con el renglón y lo corrijo.
