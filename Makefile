.PHONY: test benchmark ejemplo privacidad inventario citas golden verificar limpiar ayuda

ayuda:
	@echo "renta-co"
	@echo ""
	@echo "  make test        corre la suite de tests"
	@echo "  make benchmark   las 7 capas de verificación sobre 20 personas"
	@echo "  make ejemplo     corre el expediente de ejemplo de punta a punta"
	@echo "  make privacidad  escanea el repo en busca de datos personales"
	@echo "  make inventario  regenera la línea base de lo que .privacidadignore excluye"
	@echo "  make citas       chequea las citas de knowledge/ contra la fuente (USA RED)"
	@echo "  make golden      APRUEBA la línea base del motor. Mira el diff antes de commitear"
	@echo "  make verificar   todo lo anterior menos citas (lo que corre CI en cada push)"
	@echo "  make limpiar     borra __pycache__ y artefactos"

test:
	python3 -m unittest discover -s engine/tests -t . -v

benchmark:
	python3 -m benchmark.correr

ejemplo:
	python3 -m engine.cli parametros --anio 2025
	python3 -m engine.cli calcular --expediente expediente.ejemplo

privacidad:
	python3 scripts/escanear_privacidad.py .

# El modo estricto sale 1 A PROPÓSITO (los tests traen cédulas de prueba),
# así que no se puede usar como compuerta. La compuerta es que lo que hay en
# los archivos excluidos esté INVENTARIADO. MIRA EL DIFF antes de commitear:
# una línea nueva acá es un dato que entró a un archivo que nadie revisa.
inventario:
	python3 scripts/escanear_privacidad.py --inventario > scripts/privacidad-esperado.txt
	@git diff --stat -- scripts/privacidad-esperado.txt || true

# USA RED, y por eso NO entra en `verificar`. Un chequeo de red que puede
# poner en rojo la aritmética del motor produce rojos que no significan nada,
# y un rojo que no significa nada se empieza a ignorar. Corre solo en el job
# semanal (.github/workflows/citas.yml) o a mano.
citas:
	python3 scripts/verificar_citas.py

# Aprueba la línea base del golden master. NO lo corras por reflejo cuando el
# benchmark se ponga rojo: cada línea que cambie es una decisión que estás
# tomando, y tiene que caber en el mensaje del commit. Un `--aprobar` reflejo
# convierte esta capa en un archivo que se regenera solo, o sea en nada.
golden:
	python3 -m benchmark.golden --aprobar
	@git diff --stat -- benchmark/golden.json || true

verificar: test benchmark ejemplo privacidad
	@echo ""
	@echo "✓ Todo verde."

limpiar:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	rm -f expediente.ejemplo/03-analisis/escenarios.csv
