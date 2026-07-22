.PHONY: help setup backend-setup frontend-setup test backend-test frontend-test coverage backend-coverage frontend-coverage clean install-hooks

help:
	@echo "AssetFinder Development Commands"
	@echo "================================"
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
	@echo "Development:"
	@echo "  make backend-run        - Ejecutar API Flask"
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
	cd backend && . venv/bin/activate && pip install -r requirements.txt
	@echo "✓ Backend setup completado"

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

.PHONY: help setup backend-setup frontend-setup test backend-test frontend-test coverage backend-coverage frontend-coverage clean backend-run frontend-serve
