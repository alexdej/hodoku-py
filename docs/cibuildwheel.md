# Building multi-platform wheels with cibuildwheel

## Status: Implemented

The publish workflow (`.github/workflows/publish.yml`) uses cibuildwheel to
build compiled wheels for all platforms on every version-tag push.

## What the workflow does

1. **build_wheels** — runs on `ubuntu-latest`, `windows-latest`, `macos-latest`.
   Builds wheels for CPython 3.11, 3.12, 3.13 using `pypa/cibuildwheel`.
2. **build_sdist** — builds a source distribution as a fallback for unlisted
   platforms.
3. **publish** — downloads all artifacts, publishes to PyPI via trusted
   publishing (OIDC), and creates a GitHub Release.

## What cibuildwheel produces

- Linux: manylinux x86_64 wheels
- macOS: arm64 wheels (native on `macos-latest`)
- Windows: MSVC-compiled wheels
- Plus the sdist as fallback for unlisted platforms

## setup.py notes

The C extensions (`_fish_accel`, `_gen_accel`) are built by `OptionalBuildExt`,
which catches build failures and falls back to pure Python. No platform-specific
link flags are needed — cibuildwheel handles toolchain details for each platform.

## Trusted publishing (PyPI)

The workflow uses PyPI's OIDC trusted publishing instead of API tokens.
Configure at pypi.org → project → Publishing → Add a new publisher:
- Owner: your GitHub username/org
- Repository: hodoku-py
- Workflow: publish.yml

## Release process

```bash
git tag v0.3.0
git push origin v0.3.0  # triggers the workflow
```
