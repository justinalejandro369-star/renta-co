# Contribuir a renta-co

Hay tres formas de aportar, en orden de lo que más falta.

---

## 1. Adaptadores de bancos y plataformas

Es lo que más se necesita y lo más fácil de hacer. **Son ~40 líneas.**

Faltan: Davivienda, BBVA, Nu, Nequi, Daviplata, Lulo, Scotiabank, Itaú,
Payoneer, PayPal, Upwork, Binance, Buda, Bitso.

```python
# engine/adapters/mibanco.py
from ..ledger import Movimiento
from .generico import parse_fecha, parse_monto

NOMBRE = "Mi Banco"

def detecta(cabeceras: list[str], nombre: str = "") -> bool:
    ...

def importar(ruta: Path) -> list[Movimiento]:
    ...
```

Regístralo en `engine/adapters/__init__.py`, en `REGISTRO`, **antes** de
`generico` — el genérico siempre va de último.

Reglas:

- **Pasa `sep_decimal` a `parse_monto`.** Los bancos colombianos usan coma
  decimal; las plataformas internacionales, punto. No dejes que la heurística
  adivine si sabes la respuesta.
- **Ante la duda, `categoria="desconocido"`.** Es preferible que el usuario
  clasifique a mano a que un traslado se cuente como ingreso. No clasifiques
  por el signo del monto.
- **Los retiros y las conversiones son `traslado`**, no ingreso ni gasto.
- Incluye un CSV de muestra **anonimizado** en `engine/tests/muestras/` y un
  test que verifique la clasificación.

---

## 2. Años gravables y cambios normativos

`knowledge/` está versionado por año gravable justamente para esto.

Para agregar un año: copia `knowledge/ag2025/` y **verifica cada cifra**
contra la norma vigente. No heredes valores sin verificar — para eso está
`meta.hereda_de`, que los marca como heredados y hace que el motor lo
advierta en la salida.

**Cada cifra necesita su `fuente` y, si existe, su `url`.** Hay un test que
lo verifica (`test_cada_tope_tiene_fuente`). Una cifra sin fuente no entra.

Si cambió una norma, abre un issue con:

- Qué cambió.
- La resolución, decreto, ley o sentencia.
- Desde qué año gravable aplica.

---

## 3. Casos de prueba

El motor solo vale lo que valen sus tests.

Si tienes una declaración real, **anonimízala** — quita cédula, nombres,
números de cuenta, y redondea las cifras — y aporta el caso con el resultado
esperado. Casos con perfiles distintos (asalariado, mixto, arrendador,
pensionado) son los que más falta hacen.

Los valores esperados van **calculados a mano contra la norma**, no copiados
de la salida del programa. Un test que repite lo que el código produce no
prueba nada.

---

## Reglas del proyecto

**Sin dependencias externas.** Es una promesa a los usuarios, no una
preferencia estética: cualquiera puede auditar el cálculo con un Python
limpio. Python 3.11+ por `tomllib`.

**Nada de datos personales, nunca.** Corre esto antes de cada commit:

```bash
python3 scripts/escanear_privacidad.py
```

Si aportas una muestra, revísala dos veces. Un archivo con la cédula de
alguien queda indexado por Google para siempre.

**La aritmética vive en `engine/`, no en las skills.** Las skills conducen la
conversación; el motor calcula. Si una skill hace una cuenta, está mal puesta.

**Cada afirmación normativa con su artículo.** En el código, en las skills y
en la documentación.

---

## Antes de mandar el PR

```bash
python3 -m unittest discover -s engine/tests -t .
python3 -m engine.cli calcular --expediente expediente.ejemplo
python3 scripts/escanear_privacidad.py
```

Los tres tienen que pasar limpios.

---

## Lo que NO se acepta

- Cualquier cosa que sugiera antedatar documentos, inventar gastos u ocultar
  ingresos.
- Telemetría, analytics, o cualquier salida a red que no esté declarada en
  `PRIVACY.md`.
- Integraciones que suban documentos del usuario a servicios de terceros.
- Cifras normativas sin fuente.
- Lenguaje que prometa un resultado ("garantiza que te devuelvan plata") o que
  presente la salida como algo distinto de un borrador.
