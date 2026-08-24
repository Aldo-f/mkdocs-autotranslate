## Publishing

Two paths to release a new version:

### A. From your machine (Twine, current default)

```bash
# one-time: put your token in ~/.pypirc (chmod 600) or ~/.config/pypi/token
# see docs/pypirc.example for the .pypirc shape
pip install build twine
python -m build
twine check dist/*
twine upload --username __token__ --password "$(cat ~/.config/pypi/token)" dist/*
```

### B. From CI (tag-triggered, OIDC — needs one-time PyPI trusted publisher)

Requires a pending publisher on pypi.org → Publishing:
project `mkdocs-autotranslate`, owner `Aldo-f`, repo `mkdocs-autotranslate`,
workflow `publish.yml`, environment `pypi`. Then:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z   # publish.yml does the rest
```

Until that publisher is configured on PyPI, path B fails with
`invalid-publisher` (harmless — use path A).
