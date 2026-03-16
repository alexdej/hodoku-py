PYTHON ?= python
TWINE  ?= twine
CC     ?= gcc

.PHONY: build upload upload-test clean lint

build:
	$(PYTHON) -m build

sdist:
	$(PYTHON) -m build --sdist

pypi: sdist
	$(TWINE) upload dist/*

testpypi: sdist
	$(TWINE) upload --repository testpypi dist/*

C_SOURCES = $(wildcard src/hodoku/*/_*_accel.c)
PY_INCLUDE = $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('INCLUDEPY'))")

# Lint C extensions (cppcheck + gcc warnings)
lint:
	@echo "=== cppcheck ==="
	cppcheck --enable=warning,style,performance,portability \
		--check-level=exhaustive --error-exitcode=1 \
		--suppress=missingIncludeSystem \
		$(C_SOURCES)
	@echo "=== $(CC) -Wall -Wextra ==="
	$(CC) -fsyntax-only -Wall -Wextra -Wpedantic -Werror \
		-Wno-unused-parameter -Wno-missing-field-initializers \
		-I$(PY_INCLUDE) \
	 	$(C_SOURCES)
	@echo "lint: all checks passed"

clean:
	rm -rf dist/ build/*.egg-info src/*.egg-info
