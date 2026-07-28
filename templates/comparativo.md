# Comparativo de rutas — AG {{año}}

Generado con `python3 -m engine.cli calcular --csv`. UVT {{año}} = {{$X}}.

---

## Las dos rutas

Son **excluyentes** (art. 336 num. 4 ET): se elige una.

| Concepto | Ruta A — costos | Ruta B — 25% exento |
|---|---|---|
| Ingresos brutos cédula general | {{$X}} | {{$X}} |
| − INCRNGO | {{$X}} | {{$X}} |
| = Ingresos netos | {{$X}} | {{$X}} |
| − Costos y gastos | {{$X}} | $0 |
| − Renta exenta 25% | $0 | {{$X}} |
| − Deducciones especiales | {{$X}} | {{$X}} |
| [tope 40% / 1.340 UVT] | {{$X}} | {{$X}} |
| [rechazado por el tope] | {{$X}} | {{$X}} |
| − Dependientes (fuera del tope) | {{$X}} | {{$X}} |
| = **Renta líquida gravable** | **{{$X}}** | **{{$X}}** |
| Impuesto (art. 241) | {{$X}} | {{$X}} |
| − Descuentos | {{$X}} | {{$X}} |
| − Retenciones | {{$X}} | {{$X}} |
| = **Saldo a {{pagar/favor}}** | **{{$X}}** | **{{$X}}** |

**Gana la Ruta {{X}} por {{$X}}.**

---

## Cuánto vale cada palanca

Impuesto ahorrado, en pesos. Ordenado de mayor a menor.

| Palanca | Ruta A | Ruta B | Qué exige |
|---|---|---|---|
| {{}} | {{$X}} | {{$X}} | {{}} |

{{Si la palanca más grande vale más que la diferencia entre rutas, dilo
explícitamente acá. Es la conclusión que le sirve a la persona.}}

---

## Supuestos

Todo lo que no salió de un documento:

| Supuesto | Valor usado | Qué documento lo cierra | Impacto si cambia |
|---|---|---|---|
| {{}} | {{$X}} | {{}} | {{$X}} |

---

## Lo que NO se incluyó, y por qué

| Partida | Monto | Por qué no procede |
|---|---|---|
| Intereses de tarjeta de crédito | {{$X}} | Consumo personal, sin relación de causalidad |
| Traslados entre cuentas propias | {{$X}} | No son ingreso ni gasto |
| Donaciones sin certificado del RTE | {{$X}} | Art. 257 ET exige la certificación |
| {{}} | {{}} | {{}} |

---

## Reproducir

```bash
python3 -m engine.cli calcular --expediente ./expediente
```

Lógica en `engine/depuracion.py`. Parámetros y fuentes en
`knowledge/ag{{año}}/parametros.toml`.
