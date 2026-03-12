PYTHON ?= python
TWINE  ?= twine

.PHONY: build upload upload-test clean

build:
	$(PYTHON) -m build

sdist:
	$(PYTHON) -m build --sdist

upload: build
	$(TWINE) upload dist/*

upload-test: build
	$(TWINE) upload --repository testpypi dist/*

clean:
	rm -rf dist/ build/*.egg-info src/*.egg-info
