"""Plugin tests: on_files behaviour against a real MkDocs config (offline)."""

import logging
from pathlib import Path

import pytest

mkdocs = pytest.importorskip("mkdocs")

from mkdocs.structure.files import Files

from mkdocs_blog_autotranslate.plugin import BlogAutotranslatePlugin


def make_post(dir_path: Path, slug: str, title="T"):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"{slug}.md").write_text(
        f'---\ntitle: "{title}"\ndate: 2026-01-01\n---\n\nHello.\n',
        encoding="utf-8")


def build_plugin(**opts):
    p = BlogAutotranslatePlugin()
    errors, warnings = p.load_config({} if not opts else opts)
    assert not errors and not warnings
    return p


def fake_files():
    return Files([])


@pytest.fixture()
def docs(tmp_path):
    d = tmp_path / "docs"
    (d / "en" / "blog" / "posts").mkdir(parents=True)
    (d / "nl" / "blog" / "posts").mkdir(parents=True)
    cfg = {"docs_dir": str(d)}
    return d, cfg


def test_in_sync_is_silent(docs, caplog):
    d, cfg = docs
    make_post(d / "en" / "blog" / "posts", "same")
    make_post(d / "nl" / "blog" / "posts", "same")
    p = build_plugin()
    with caplog.at_level(logging.INFO, logger="mkdocs.plugins.blog_autotranslate"):
        p.on_files(fake_files(), config=cfg)
    assert "in sync" in caplog.text


def test_report_mode_logs_warning_not_raise(docs, caplog):
    d, cfg = docs
    make_post(d / "en" / "blog" / "posts", "only-en")
    p = build_plugin()  # default mode=report
    result = None
    with caplog.at_level(logging.WARNING, logger="mkdocs.plugins.blog_autotranslate"):
        result = p.on_files(fake_files(), config=cfg)
    assert isinstance(result, Files)          # build continues
    assert "1 untranslated post(s)" in caplog.text
    assert "en->nl: blog/posts/only-en.md" in caplog.text


def test_strict_mode_raises(docs):
    d, cfg = docs
    make_post(d / "en" / "blog" / "posts", "gap")
    p = build_plugin(mode="strict")
    with pytest.raises(Exception) as ei:
        p.on_files(fake_files(), config=cfg)
    assert "untranslated post(s)" in str(ei.value)


def test_drafts_skipped_and_logged(docs, caplog):
    d, cfg = docs
    make_post(d / "en" / "blog" / "posts", "wip-draft")
    (d / "en" / "blog" / "posts" / "wip-draft.md").write_text(
        '---\ntitle: WIP\ndate: 2026-01-01\ndraft: true\n---\n\nx\n',
        encoding="utf-8")
    p = build_plugin(mode="strict")           # draft must NOT trip strict
    with caplog.at_level(logging.INFO, logger="mkdocs.plugins.blog_autotranslate"):
        result = p.on_files(fake_files(), config=cfg)
    assert isinstance(result, Files)
    assert "skipping draft en/blog/posts/wip-draft.md" in caplog.text


def test_single_language_warns_and_noop(docs, caplog):
    d, cfg = docs
    p = build_plugin(languages=["en"])
    with caplog.at_level(logging.WARNING, logger="mkdocs.plugins.blog_autotranslate"):
        res = p.on_files(fake_files(), config=cfg)
    assert isinstance(res, Files)
    assert "needs >= 2 languages" in caplog.text
