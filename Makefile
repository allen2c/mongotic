# Developing
install:
	poetry install --with dev

fmt:
	isort mongotic tests
	black mongotic tests
	ruff check --fix mongotic tests

update:
	poetry update

test:
	pytest

test_cov:
	pytest --cov-report=html
	@echo "HTML report: htmlcov/index.html"
