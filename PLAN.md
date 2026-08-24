# Plan: `mkdocs-autotranslate` — a real MkDocs plugin

**Date**: 2026-08-24 · **Source feature**: specs/003-autotranslate in
`06-apps-aldo-f-github-io` · **Goal**: publish the existing blog translation
gap-filler as an installable, testable MkDocs plugin.

## 0. What already exists (to port)

`06-apps-aldo-f-github-io/scripts/blog_translate.py` (274 lines):
- bidirectional slug-set gap detection (`fill_gaps(root, translator=..., write=...)`)
- DeepL client with free/pro endpoint auto-select (`:fx` key suffix)
- front-matter parser (title translated; date/categories verbatim; drafts skipped)
- fenced-code passthrough + prose batching (≤4000 chars/request)
- provenance comment appended to generated files
- injectable translator → network-free tests

## 1. Architecture

Two surfaces, one core:

| Surface | Mechanism | Behaviour |
|---|---|---|
| **MkDocs plugin** | entry point `mkdocs.plugins`, `BasePlugin` | at build time: compare post slug-sets across language dirs; `report` mode logs gaps, `strict` mode fails the build. Never calls DeepL during build. |
| **CLI** | console script `autotranslate` | dry-run report / `--write` to translate missing posts via DeepL (author-run, reviewed via git diff). |

Core module is shared: plugin = *detection*, CLI = *remediation*.
Rationale: auto-writing files during CI builds is exactly what FR-8's
dry-run-first philosophy forbids without human review.

## 2. Repo layout (new repo: `~/dev/mkdocs-autotranslate`)

```
mkdocs-autotranslate/
├── pyproject.toml              # hatchling backend, entry points:
│                               #   mkdocs.plugins → blog_autotranslate
│                               #   console_scripts → autotranslate
├── README.md                   # install, config reference, DeepL key setup
├── LICENSE                     # MIT
├── .github/workflows/ci.yml    # pytest on 3.11/3.12 + build check
├── src/mkdocs_autotranslate/
│   ├── __init__.py             # version
│   ├── plugin.py               # AutotranslatePlugin(BasePlugin)
│   ├── cli.py                  # argparse main()
│   ├── core.py                 # fill_gaps/parse_post/split_blocks (ported)
│   └── deepl.py                # make_deepl_translator() (ported)
└── tests/
    ├── test_core.py            # unit: parsing, blocks, gap logic
    ├── test_plugin.py          # plugin events vs temp docs tree
    └── test_cli.py             # dry-run/--write against tmp tree, mock translator
```

## 3. Plugin contract

```yaml
plugins:
  - autotranslate:
      languages: [en, nl]       # language dirs under docs/
      (paths option replaces legacy blog_path)
      mode: report              # report | strict (fail build on gaps)
```

Events used: `on_files(files, *, config)` — read-only inspection of the file
list; logs `[autotranslate] N untranslated post(s): en→nl foo.md …`.
`strict` raises `PluginError`.

## 4. Porting rules

- `core.py` becomes path-parameterised: `fill_gaps(docs_dir, languages,
  blog_path, ...)` instead of hard-coded REPO/en/nl.
- Keep `translator=` injection; CLI wires the DeepL backend, plugin never does.
- No new dependencies beyond `requests`→ actually keep stdlib `urllib`
  (zero deps besides mkdocs itself) — smaller install surface.

## 5. Test plan (network-free)

1. **Unit**: front-matter parse variants; code-fence splitting; batching;
   draft skipping; idempotence (second run = no-op); provenance marker.
2. **Plugin**: fake MkDocs `Files` from a temp tree; assert log output in
   report mode and exception in strict mode; unknown-language dir tolerated.
3. **CLI**: dry-run prints WOULD CREATE and writes nothing; `--write` with
   mock translator creates both directions once; re-run writes nothing.
4. **Real-runtime verification** (the bar): editable-install into the hub's
   venv, add plugin to `mkdocs.en.yml` in `report` mode, run the real strict
   EN build of aldo-f.github.io → passes with accurate gap report; then
   remove wiring until the plugin ships (or keep if zero-risk).

## 6. Publishing steps

1. GitHub repo `Aldo-f/mkdocs-autotranslate`; NOT a submodule of ~/dev
   (it's a standalone distributable; link it from the hub's README instead).
2. CI: pytest matrix + `python -m build` sanity.
3. PyPI: check name availability; publish via trusted publishing (OIDC);
   v0.1.0 tag → release workflow.
4. After PyPI live: pin in hub `requirements.txt`, wire plugin into
   `mkdocs.base.yml`, delete `scripts/blog_translate.py` (superseded).

## 7. Acceptance criteria

- [ ] `pip install -e .` works in a clean venv; `mkdocs build` picks up the plugin
- [ ] All tests green offline; no network in test suite
- [ ] Real hub build passes with plugin active in report mode
- [ ] CLI dry-run/--write verified against a scratch copy of the hub docs
- [ ] GitHub repo pushed with green CI badge
