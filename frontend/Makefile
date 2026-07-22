.PHONY: help setup test coverage serve clean

help:
	@echo "Frontend Commands"
	@echo "================="
	@echo "  make setup      - Setup Node.js environment"
	@echo "  make test       - Run tests with coverage"
	@echo "  make coverage   - Generate coverage report"
	@echo "  make serve      - Serve frontend locally (port 8000)"
	@echo "  make clean      - Clean temporary files"

setup:
	npm install

test:
	npm test -- --coverage

coverage:
	npm test -- --coverage
	@echo "Coverage report: coverage/index.html"

serve:
	python -m http.server 8000 --directory public || npx http-server public -p 8000

clean:
	rm -rf node_modules coverage .jest-cache
	@echo "Cleanup completed"
