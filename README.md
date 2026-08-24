# mkdocs-blog-autotranslate

A MkDocs plugin + CLI that keeps a multilingual **blog** in sync across
language trees: it detects posts that exist in one language but not another,
and can create the missing translations via [DeepL](https://www.deepl.com/).

- **Plugin** (`blog-autotranslate`): at build time, reports untranslated
  posts — optionally fails strict builds. Never touches the network.
- **CLI** (`blog-autotranslate`): dry-run report by default; `--write`
  creates missing translated posts for human review before commit.

## Install

```bash
pip install mkdocs-blog-autotranslate
```

## Plugin usage

Add to `mkdocs.yml`:

```yaml
plugins:
  - blog-autotranslate:
      languages: [en, nl]     # directories under docs/
      blog_path: blog/posts   # post dir under each language dir
      mode: report            # report | strict (fail build on gaps)
```

With Material's multi-language recipe you typically run one build per
language config; add the plugin to each (or the shared base config).

## CLI usage

```bash
# dry-run: shows what WOULD be created, writes nothing, needs no API key
blog-autotranslate --docs-dir docs

# apply: creates missing posts via DeepL (review the git diff!)
blog-autotranslate --docs-dir docs --write
```

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--docs-dir` | (required) | Path to your `docs/` directory |
| `--languages` | `en nl` | Language subdirectories to compare |
| `--blog-path` | `blog/posts` | Posts directory under each language |
| `--write` | off | Create files instead of reporting only |

## DeepL key

The CLI looks for a DeepL auth key in `$DEEPL_API_KEY` or
`~/.config/deepl/api_key` (mode 0600). Keys ending in `:fx` automatically
use the free endpoint (`api-free.deepl.com`); all others use the pro
endpoint. Free tier is 500,000 characters/month.

## Guarantees

- Never overwrites existing files (idempotent; re-runs are no-ops)
- Drafts (`draft: true`) are never propagated
- Front matter preserved structurally: title translated, date/categories verbatim
- Fenced code blocks pass through untranslated
- A provenance comment is appended to generated files
- The plugin itself performs no network calls — translation is always an
  explicit author-run step so machine output gets reviewed before publishing

## Development

```bash
pip install -e '.[test]'
pytest
```

## License

MIT
