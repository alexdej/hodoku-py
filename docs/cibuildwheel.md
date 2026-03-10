# Building multi-platform wheels with cibuildwheel

When ready to ship compiled wheels for all platforms, add a GitHub Actions
workflow using `cibuildwheel`. This gives users a fast compiled wheel via
`pip install hodoku-py` with no compiler required on their end.

## What to do

### 1. Fix `setup.py` for MSVC compatibility

The `extra_link_args=["-static-libgcc"]` flag is MinGW-only. MSVC (used by
cibuildwheel on Windows) doesn't accept it. Make it conditional:

```python
import sys

extra_link_args = []
if sys.platform == "win32":
    # Only needed when building with MinGW, not MSVC
    import shutil
    if shutil.which("gcc") and not shutil.which("cl"):
        extra_link_args = ["-static-libgcc"]

ext = Extension(
    "hodoku.solver._fish_accel",
    sources=["src/hodoku/solver/_fish_accel.c"],
    extra_link_args=extra_link_args,
)
```

### 2. Add the workflow

Create `.github/workflows/build-wheels.yml`:

```yaml
on:
  push:
    tags:
      - "v*"  # trigger on version tags only

jobs:
  build_wheels:
    name: Build wheels on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]

    steps:
      - uses: actions/checkout@v4
      - uses: pypa/cibuildwheel@v2.22
        env:
          CIBW_BUILD: "cp311-* cp312-* cp313-*"
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.os }}
          path: ./wheelhouse/*.whl

  build_sdist:
    name: Build sdist
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install build && python -m build --sdist
      - uses: actions/upload-artifact@v4
        with:
          name: sdist
          path: dist/*.tar.gz

  upload_pypi:
    needs: [build_wheels, build_sdist]
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # for trusted publishing
    steps:
      - uses: actions/download-artifact@v4
        with:
          pattern: wheels-*
          merge-multiple: true
          path: dist
      - uses: actions/download-artifact@v4
        with:
          name: sdist
          path: dist
      - uses: pypa/gh-action-pypi-publish@release/v1
```

### 3. Set up trusted publishing on PyPI

Rather than storing an API token as a secret, use PyPI's trusted publishing:
- Go to pypi.org → your project → Publishing → Add a new publisher
- Set: owner = your GitHub username, repo = hodoku-py, workflow = build-wheels.yml

This lets the workflow publish without any stored credentials.

### 4. Release process

```bash
jj tag v0.2.0
git push origin v0.2.0  # triggers the workflow
```

## What cibuildwheel produces

- Linux: manylinux wheels (run on any Linux distro)
- macOS: separate wheels for x86_64 and arm64
- Windows: MSVC-compiled wheels
- Plus the sdist as fallback for unlisted platforms
