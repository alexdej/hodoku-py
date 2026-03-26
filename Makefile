PYTHON ?= python
CC     ?= gcc

.PHONY: build sdist clean flake8 cppcheck lint

build:
	$(PYTHON) -m build

sdist:
	$(PYTHON) -m build --sdist

C_SOURCES = $(wildcard src/hodoku/*/_*_accel.c)
PY_INCLUDE = $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('INCLUDEPY'))")

# Lint python code (flake8)
flake8:
	@echo "=== flake8 ==="
	flake8 src/
	@echo "lint: all checks passed"

# Lint C extensions (cppcheck + gcc warnings)
cppcheck:
	@echo "=== cppcheck ==="
	cppcheck --enable=warning,style,performance,portability \
		--check-level=exhaustive --error-exitcode=1 \
		--suppress=missingIncludeSystem \
		$(C_SOURCES)
	@echo "lint: all checks passed"

lint: flake8 cppcheck

clean:
	rm -rf dist/ build/*.egg-info src/*.egg-info
