"""CLI tests: dry-run vs --write against a temp docs tree (mock DeepL)."""

from pathlib import Path

import pytest

from mkdocs_autotranslate.cli import main


def make_post(dir_path: Path, slug: str, title="T"):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"{slug}.md").write_text(
        f'---\ntitle: "{title}"\ndate: 2026-01-01\ncategories:\n---\n\nHello.\n',
        encoding="utf-8")


@pytest.fixture()
def docs(tmp_path):
    return tmp_path / "docs"


def test_cli_dry_run_no_key_needed(docs, tmp_path, capsys):
    make_post(docs / "en" / "blog" / "posts", "a")
    rc = main(["--docs-dir", str(docs)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WOULD CREATE 1 post(s)" in out
    assert "en -> nl  blog/posts/a" in out
    assert not (docs / "nl").exists()          # nothing written


def test_cli_write_uses_translator(docs, monkeypatch, capsys):
    make_post(docs / "en" / "blog" / "posts", "a", title="Hi")
    seen = {}

    def fake_translator():
        def translate(texts, src, dst):
            seen["call"] = (list(texts), src, dst)
            return [f"[{dst}] {t}" for t in texts]
        return translate

    monkeypatch.setattr(
        "mkdocs_autotranslate.cli.make_deepl_translator", fake_translator)
    rc = main(["--docs-dir", str(docs), "--write"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WROTE 1 post(s)" in out
    out_file = docs / "nl" / "blog" / "posts" / "a.md"
    text = out_file.read_text(encoding="utf-8")
    assert "[nl] Hi" in text
    assert seen["call"][1:] == ("en", "nl")


def test_cli_custom_languages_and_path(docs, capsys):
    make_post(docs / "fr" / "articles", "z")
    rc = main(["--docs-dir", str(docs), "--languages", "fr", "de",
               "--paths", "articles"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "fr -> de  articles/z" in out


def test_cli_in_sync_message(docs, capsys):
    make_post(docs / "en" / "blog" / "posts", "x")
    make_post(docs / "nl" / "blog" / "posts", "x")
    rc = main(["--docs-dir", str(docs)])
    assert rc == 0
    assert "in sync" in capsys.readouterr().out
