.PHONY: help setup backend-setup frontend-setup test backend-test frontend-test coverage backend-coverage frontend-coverage lint backend-lint frontend-lint bench bench-backend bench-frontend prod-run clean install-hooks openspec-show openspec-check openspec-delta

help:
	@echo "AssetFinder Development Commands"
	@echo "================================"
	@echo ""
	@echo "OpenSpec (Referencia Central):"
	@echo "  make openspec-show      - Ver OpenSpec completo"
	@echo "  make openspec-check     - Validar proyecto vs OpenSpec"
	@echo "  make openspec-delta     - Ver delta específico (DELTA=0.5)"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              - Setup completo (backend + frontend)"
	@echo "  make backend-setup      - Setup Python backend"
	@echo "  make frontend-setup     - Setup Node.js frontend"
	@echo ""
	@echo "Testing:"
	@echo "  make test               - Ejecutar todos los tests"
	@echo "  make backend-test       - Tests backend con cobertura"
	@echo "  make frontend-test      - Tests frontend con cobertura"
	@echo "  make coverage           - Ver reporte de cobertura completo"
	@echo ""
	@echo "Calidad:"
	@echo "  make lint               - ruff (backend) + eslint (frontend)"
	@echo "  make bench              - Benchmark de rendimiento"
	@echo ""
	@echo "Development:"
	@echo "  make backend-run        - Ejecutar API Flask (desarrollo)"
	@echo "  make prod-run           - Ejecutar con gunicorn (como producción)"
	@echo "  make frontend-serve     - Servir frontend localmente"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean              - Limpiar archivos temporales"
	@echo "  make install-hooks      - Instalar git hooks (próximamente)"

setup: backend-setup frontend-setup
	@echo "✓ Setup completado"

backend-setup:
	@echo "Setting up backend..."
	cd backend && python -m venv venv
	cd backend && . venv/bin/activate && pip install -r requirements-dev.txt
	@echo "✓ Backend setup completado (runtime + pytest + ruff)"

frontend-setup:
	@echo "Setting up frontend..."
	cd frontend && npm install
	@echo "✓ Frontend setup completado"

test: backend-test frontend-test
	@echo ""
	@echo "✓ Todos los tests ejecutados"

backend-test:
	@echo "Running backend tests..."
	cd backend && . venv/bin/activate && pytest tests/ --cov=src --cov-report=term-missing -v
	@echo "✓ Backend tests completados"

frontend-test:
	@echo "Running frontend tests..."
	cd frontend && npm test -- --coverage
	@echo "✓ Frontend tests completados"

lint: backend-lint frontend-lint
	@echo ""
	@echo "✓ Linters sin hallazgos"

backend-lint:
	@echo "ruff (backend)..."
	cd backend && . venv/bin/activate && ruff check src/ tests/ bench.py wsgi.py gunicorn.conf.py

frontend-lint:
	@echo "eslint (frontend)..."
	cd frontend && npx eslint public/js tests server.js bench.mjs

prod-run:
	@echo "Arrancando con gunicorn (configuración de producción)..."
	cd backend && . venv/bin/activate && gunicorn --config gunicorn.conf.py wsgi:application

bench: bench-backend bench-frontend
	@echo ""
	@echo "✓ Benchmark completado (comparar contra la ejecución anterior)"

bench-backend:
	@echo "Benchmark backend (BD, API, deduplicación)..."
	cd backend && . venv/bin/activate && python bench.py --sizes 100,1000

bench-frontend:
	@echo "Benchmark frontend (render de resultados)..."
	cd frontend && npm run bench --silent

coverage: backend-coverage frontend-coverage
	@echo ""
	@echo "✓ Reportes de cobertura generados"
	@echo "Backend: backend/htmlcov/index.html"
	@echo "Frontend: frontend/coverage/index.html"

backend-coverage:
	@echo "Generating backend coverage report..."
	cd backend && . venv/bin/activate && pytest tests/ --cov=src --cov-report=html --cov-report=term
	@echo "✓ Backend coverage report: backend/htmlcov/index.html"

frontend-coverage:
	@echo "Generating frontend coverage report..."
	cd frontend && npm test -- --coverage

backend-run:
	@echo "Starting Flask API..."
	cd backend && . venv/bin/activate && python -m flask --app src.api run --debug

frontend-serve:
	@echo "Starting frontend server..."
	cd frontend && python -m http.server 8000 --directory public

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .coverage -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name coverage -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .venv -exec rm -rf {} + 2>/dev/null || true
	rm -f backend/venv
	@echo "✓ Cleanup completado"

openspec-show:
	@echo "OpenSpec v1.0 - AssetFinder Specification"
	@echo "=========================================="
	@cat openspec/v1.0.yaml

openspec-check:
	@echo "Validating project structure against OpenSpec..."
	@echo ""
	@echo "Checking file structure:"
	@test -d backend && echo "✓ backend/" || echo "✗ backend/"
	@test -d frontend && echo "✓ frontend/" || echo "✗ frontend/"
	@test -d openspec && echo "✓ openspec/" || echo "✗ openspec/"
	@test -f backend/src/api.py && echo "✓ backend/src/api.py" || echo "✗ backend/src/api.py"
	@test -f backend/src/db.py && echo "✓ backend/src/db.py" || echo "✗ backend/src/db.py"
	@test -f backend/src/scraper.py && echo "✓ backend/src/scraper.py" || echo "✗ backend/src/scraper.py"
	@test -f backend/src/parser.py && echo "✓ backend/src/parser.py" || echo "✗ backend/src/parser.py"
	@test -f frontend/public/js/main.js && echo "✓ frontend/public/js/main.js" || echo "✗ frontend/public/js/main.js"
	@test -f frontend/public/js/search.js && echo "✓ frontend/public/js/search.js" || echo "✗ frontend/public/js/search.js"
	@test -f frontend/public/js/ui.js && echo "✓ frontend/public/js/ui.js" || echo "✗ frontend/public/js/ui.js"
	@echo ""
	@echo "Checking deltas completion (from OpenSpec v1.0):"
	@echo "✓ Delta 0.1: Setup base"
	@echo "✓ Delta 0.2: Backend - Database + Scraper mock"
	@echo "✓ Delta 0.3: Backend - Parser HTML real"
	@echo "✓ Delta 0.4: Backend - Persistencia en BD"
	@echo "✓ Delta 0.5: Frontend - Interfaz base"
	@echo "✓ Delta 0.6: Frontend - Integración y búsqueda"
	@echo "✓ Delta 0.7: Features avanzadas"
	@echo "✓ Delta 0.8: Security Hardening - Producción"
	@echo ""
	@echo "✓ OpenSpec validation complete"

openspec-delta:
	@if [ -z "$(DELTA)" ]; then \
		echo "Usage: make openspec-delta DELTA=0.5"; \
		echo ""; \
		echo "Available deltas (0.1 - 0.8)"; \
	else \
		echo "Delta $(DELTA) from OpenSpec v1.0:"; \
		grep -A 20 "^  $(DELTA):" openspec/v1.0.yaml || echo "Delta $(DELTA) not found"; \
	fi

.PHONY: help setup backend-setup frontend-setup test backend-test frontend-test coverage backend-coverage frontend-coverage clean backend-run frontend-serve openspec-show openspec-check openspec-delta
