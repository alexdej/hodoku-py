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
	pytest --clang-tidy --flake8 src/


clean:
	rm -rf dist/ build/*.egg-info src/*.egg-info
