.PHONY: test ejemplo privacidad verificar limpiar ayuda

ayuda:
	@echo "renta-co"
	@echo ""
	@echo "  make test        corre la suite completa"
	@echo "  make ejemplo     corre el expediente de ejemplo de punta a punta"
	@echo "  make privacidad  escanea el repo en busca de datos personales"
	@echo "  make verificar   test + ejemplo + privacidad (lo que corre CI)"
	@echo "  make limpiar     borra __pycache__ y artefactos"

test:
	python3 -m unittest discover -s engine/tests -t . -v

ejemplo:
	python3 -m engine.cli parametros --anio 2025
	python3 -m engine.cli calcular --expediente expediente.ejemplo

privacidad:
	python3 scripts/escanear_privacidad.py .

verificar: test ejemplo privacidad
	@echo ""
	@echo "✓ Todo verde."

limpiar:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	rm -f expediente.ejemplo/03-analisis/escenarios.csv
