.PHONY: test benchmark ejemplo privacidad verificar limpiar ayuda

ayuda:
	@echo "renta-co"
	@echo ""
	@echo "  make test        corre la suite de tests"
	@echo "  make benchmark   14 personas: invariantes + diferencial + anclas"
	@echo "  make ejemplo     corre el expediente de ejemplo de punta a punta"
	@echo "  make privacidad  escanea el repo en busca de datos personales"
	@echo "  make verificar   todo lo anterior (lo que corre CI)"
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

verificar: test benchmark ejemplo privacidad
	@echo ""
	@echo "✓ Todo verde."

limpiar:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	rm -f expediente.ejemplo/03-analisis/escenarios.csv
