# Developing
install_all:
	poetry install --with dev

format_all:
	isort mongotic tests
	black mongotic tests

update_all:
	poetry update
	poetry export --without-hashes -f requirements.txt --output requirements.txt
	poetry export --without-hashes --with dev -f requirements.txt --output requirements-dev.txt
