"""Unit tests for mkdocs_blog_autotranslate.core (network-free)."""

import textwrap
from pathlib import Path

import pytest

from mkdocs_blog_autotranslate.core import (
    fill_gaps, find_gaps, parse_post, scan_slugs, split_blocks,
)


def make_post(dir_path: Path, slug: str, title="T", date="2026-01-01",
              categories=(), draft=False, body="Hello world."):
    cats = "".join(f"\n  - {c}" for c in categories)
    d = "\ndraft: true" if draft else ""
    dir_path.mkdir(parents=True, exist_ok=True)
    fm = f'---\ntitle: "{title}"\ndate: {date}{d}\ncategories:{cats}\n---\n\n'
    (dir_path / f"{slug}.md").write_text(fm + body + "\n", encoding="utf-8")


@pytest.fixture()
def docs(tmp_path):
    d = tmp_path / "docs"
    return d


# ---- front matter ---------------------------------------------------------

def test_parse_post_basic(docs):
    make_post(docs / "en", "a", title="Hi", date="2026-02-03", categories=("X", "Y"))
    meta, body = parse_post(docs / "en" / "a.md")
    assert meta["title"] == "Hi"
    assert meta["date"] == "2026-02-03"
    assert meta["categories"] == ["X", "Y"]
    assert body == "Hello world."


def test_parse_post_no_frontmatter_gets_derived_title(docs):
    p = docs / "en"
    p.mkdir(parents=True)
    (p / "x.md").write_text("# My Page\n\nSome body text.\n", encoding="utf-8")
    meta, body = parse_post(p / "x.md")
    assert meta["title"] == "My Page"          # derived from first heading
    assert meta["no_frontmatter"] is True
    assert "Some body text." in body


def test_parse_post_empty_file_skipped(docs):
    p = docs / "en"
    p.mkdir(parents=True)
    (p / "empty.md").write_text("", encoding="utf-8")
    assert parse_post(p / "empty.md") == (None, None)


# ---- block splitting ------------------------------------------------------

def test_split_blocks_code_passthrough():
    md = "Para one.\n\n```python\nprint('hi')\n```\n\nPara two."
    chunks = split_blocks(md)
    code = [c for c, is_code in chunks if is_code]
    assert code == ["```python\nprint('hi')\n```"]


def test_split_blocks_batches_prose():
    md = "\n\n".join(f"P{i}." for i in range(50))
    chunks = split_blocks(md)
    assert all(not is_code for _, is_code in chunks)
    # reassembles losslessly modulo whitespace edges
    assert "P0." in chunks[0][0] and "P49." in chunks[-1][0]


# ---- gap detection --------------------------------------------------------

def test_find_gaps_both_directions_and_drafts(docs):
    en, nl = docs / "en" / "blog" / "posts", docs / "nl" / "blog" / "posts"
    make_post(en, "shared")
    make_post(en, "only-en")
    make_post(en, "draft-post", draft=True)
    make_post(nl, "shared")
    make_post(nl, "only-nl")

    slugs = scan_slugs(docs, ("en", "nl"), ["blog/posts"])
    missing, drafts = find_gaps(slugs, ("en", "nl"))
    triples = {(s, d, slug) for s, d, slug in missing}
    assert ("en", "nl", "blog/posts/only-en") in triples
    assert ("nl", "en", "blog/posts/only-nl") in triples
    assert not any("draft-post" in slug for _, _, slug in triples)
    assert drafts == [("en", "nl", "blog/posts/draft-post")]


def test_multi_path_scan_and_gaps(docs):
    en_root, nl_root = docs / "en", docs / "nl"
    make_post(en_root / "blog" / "posts", "post1")
    make_post(en_root / "pages", "about")
    (en_root / "pages" / "nested").mkdir(parents=True)
    (en_root / "pages" / "nested" / "deep.md").write_text(
        '---\ntitle: Deep\ndate: 2026-01-01\n---\n\nx\n', encoding="utf-8")
    make_post(nl_root / "blog" / "posts", "post1")
    # nl has no pages/ at all

    slugs = scan_slugs(docs, ("en", "nl"), ["blog/posts", "pages"])
    missing, _ = find_gaps(slugs, ("en", "nl"))
    triples = {(s, d, slug) for s, d, slug in missing}
    assert ("en", "nl", "pages/about") in triples
    assert ("en", "nl", "pages/nested/deep") in triples
    assert not any(slug.endswith("post1") for _, _, slug in triples)  # in sync


def test_exclude_patterns(docs):
    en_root = docs / "en"
    make_post(en_root / "blog" / "posts", "keep")
    make_post(en_root / "blog" / "posts", "skipme")
    (en_root / "glossary").mkdir(parents=True)
    (en_root / "glossary" / "terms.md").write_text(
        '---\ntitle: Terms\ndate: 2026-01-01\n---\n\nx\n', encoding="utf-8")

    slugs = scan_slugs(docs, ("en",), ["blog/posts", "glossary"],
                       exclude=["**/skipme.md", "glossary/*"])
    assert list(slugs["en"]) == ["blog/posts/keep"]


def test_glob_paths(docs):
    en_root = docs / "en"
    make_post(en_root / "blog" / "posts", "a")
    (en_root / "blog" / "special.md").write_text(
        '---\ntitle: S\ndate: 2026-01-01\n---\n\nx\n', encoding="utf-8")

    slugs = scan_slugs(docs, ("en",), ["blog/*.md"])
    assert set(slugs["en"]) == {"blog/special"}  # *.md glob is non-recursive


# ---- end-to-end gap fill with mock translator ------------------------------

def test_fill_gaps_dry_run_writes_nothing(docs):
    en = docs / "en" / "blog" / "posts"
    make_post(en, "p1", title="One", body="Body one.")
    rep = fill_gaps(docs, translator=lambda t, s, d: t, write=False)
    assert rep.created == [("en", "nl", "blog/posts/p1")]
    assert not (docs / "nl" / "blog" / "posts").exists()


def test_fill_gaps_write_creates_translated_once(docs):
    en = docs / "en" / "blog" / "posts"
    make_post(en, "p1", title="One", date="2026-05-06",
              categories=("A",), body="Body one.\n\n```py\nx=1\n```\n\nMore.")

    def tr(texts, src, dst):
        return [t.upper() for t in texts]

    rep = fill_gaps(docs, translator=tr, write=True)
    assert rep.created == [("en", "nl", "blog/posts/p1")]
    out = docs / "nl" / "blog" / "posts" / "p1.md"
    text = out.read_text(encoding="utf-8")
    assert 'title: "ONE"' in text          # title translated
    assert "date: 2026-05-06" in text      # date verbatim
    assert "- A" in text                   # categories verbatim
    assert "BODY ONE." in text             # prose translated
    assert "```py\nx=1\n```" in text       # code untouched
    assert "translated from `en/blog/posts/p1`" in text  # provenance

    # idempotent: second run creates nothing
    rep2 = fill_gaps(docs, translator=tr, write=True)
    assert rep2.created == []


def test_fill_gaps_skips_drafts_on_write(docs):
    en = docs / "en" / "blog" / "posts"
    make_post(en, "secret", draft=True)
    calls = []
    fill_gaps(docs, translator=lambda t, s, d: calls.append(t) or t, write=True)
    assert not (docs / "nl" / "blog" / "posts" / "secret.md").exists()
    assert calls == []
