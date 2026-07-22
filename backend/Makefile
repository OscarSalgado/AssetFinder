.PHONY: help setup test coverage run clean lint

help:
	@echo "Backend Commands"
	@echo "================"
	@echo "  make setup      - Setup Python environment"
	@echo "  make test       - Run tests with coverage"
	@echo "  make coverage   - Generate coverage report"
	@echo "  make run        - Run Flask API server"
	@echo "  make clean      - Clean temporary files"
	@echo "  make lint       - Check code (próximamente)"

setup:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

test:
	. venv/bin/activate && pytest tests/ --cov=src --cov-report=term-missing -v

coverage:
	. venv/bin/activate && pytest tests/ --cov=src --cov-report=html --cov-report=term
	@echo "Coverage report: htmlcov/index.html"

run:
	. venv/bin/activate && python -m flask --app src.api run --debug

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage data/assetfinder.db
	@echo "Cleanup completed"
