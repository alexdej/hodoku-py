PYTHON ?= python
TWINE  ?= twine

.PHONY: build upload upload-test clean

build:
	$(PYTHON) -m build

sdist:
	$(PYTHON) -m build --sdist

pypi: sdist
	$(TWINE) upload dist/*

testpypi: sdist
	$(TWINE) upload --repository testpypi dist/*

clean:
	rm -rf dist/ build/*.egg-info src/*.egg-info
