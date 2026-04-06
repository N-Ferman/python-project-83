PORT ?= 8000
start:
	uv run gunicorn -w 5 -b 0.0.0.0:$(PORT) page_analyzer:app
install:
	uv sync 
dev:
	uv run flask --debug --app page_analyzer:app run	
run:
	uv run python example.py
test:
	uv run pytest tests
lint:
	uv run ruff check .
build:
	./build.sh
test-coverage:
	uv run pytest --cov=page_analyzer --cov-report=xml:coverage.xml

check: lint test-coverage
