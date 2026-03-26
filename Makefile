PYTHON ?= python
CC     ?= gcc

.PHONY: build sdist clean

build:
	$(PYTHON) -m build

sdist:
	$(PYTHON) -m build --sdist

test:
	pytest -m "unit" tests/

lint:
	pytest --cppcheck --flake8 -m "flake8 or cppcheck" src/ tests/

clean:
	rm -rf dist/ build/*.egg-info src/*.egg-info
