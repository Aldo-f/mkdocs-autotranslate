"""Core translation gap-filling logic (ported from 06-apps-aldo-f-github-io).

Path-parameterised so any MkDocs docs_dir works, not just the original hub.
Translator backends are injectable for network-free tests.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

API_FREE = "https://api-free.deepl.com/v2/translate"
API_PRO = "https://api.deepl.com/v2/translate"
BATCH_CHARS = 4000  # stay well under DeepL request limits

PROVENANCE = (
    "\n---\n\n"
    "<!-- translated from `{source}` ({direction}) by deepl on {date}; "
    "review before publishing edits -->\n"
)


@dataclass
class Report:
    created: list = field(default_factory=list)   # (src_lang, dst_lang, slug)
    skipped_drafts: list = field(default_factory=list)
    chars: int = 0


# --------------------------------------------------------------------------
# front matter helpers
# --------------------------------------------------------------------------

FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)


def parse_post(path: Path):
    m = FM_RE.match(path.read_text(encoding="utf-8"))
    if not m:
        return None, None
    fm_raw, body = m.group(1), m.group(2)
    meta: dict = {"categories": []}
    in_cats = False
    for line in fm_raw.splitlines():
        s = line.strip()
        if s.startswith("- ") and in_cats:
            meta["categories"].append(s[2:].strip().strip("'\""))
            continue
        in_cats = False
        if ":" not in s:
            continue
        k, _, v = s.partition(":")
        k, v = k.strip().lower(), v.strip().strip("'\"")
        if k == "categories" and not v:
            in_cats = True
        elif k in ("title", "date", "draft"):
            meta[k] = v
    return meta, body.strip("\n")


def split_blocks(text: str) -> list[tuple[str, bool]]:
    """Split into (chunk, is_code) parts: fenced code blocks stay whole,
    prose splits on blank lines and is batched up to BATCH_CHARS."""
    parts: list[str] = []
    fence: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if fence:  # closing
                fence.append(line)
                parts.append("\n".join(fence))
                fence = []
            else:  # opening — flush prose first
                if buf:
                    parts.append("\n".join(buf))
                    buf = []
                fence.append(line)
            continue
        (fence if fence else buf).append(line)
    if fence:
        parts.append("\n".join(fence))  # unterminated fence: keep verbatim
    if buf:
        parts.append("\n".join(buf))

    # batch consecutive prose blocks up to BATCH_CHARS; code blocks standalone
    out: list[tuple[str, bool]] = []  # (chunk, is_code)
    prose: list[str] = []
    size = 0

    def flush():
        nonlocal prose, size
        if prose:
            out.append(("\n\n".join(prose), False))
            prose, size = [], 0

    for p in parts:
        if p.lstrip().startswith("```"):
            flush()
            out.append((p, True))
            continue
        p = p.strip("\n")  # drop blank-line edges; joiner re-adds spacing
        if not p:
            continue
        prose.append(p)
        size += len(p)
        if size >= BATCH_CHARS:
            flush()
    flush()
    return out


def posts_dir(docs_dir: Path, lang: str, blog_path: str) -> Path:
    return Path(docs_dir) / lang / blog_path


def scan_slugs(docs_dir: Path, languages, blog_path: str) -> dict[str, dict[str, dict]]:
    """slug -> {meta, body} per language."""
    slugs: dict[str, dict[str, dict]] = {}
    for lang in languages:
        d = posts_dir(docs_dir, lang, blog_path)
        slugs[lang] = {}
        for p in sorted(d.glob("*.md")) if d.is_dir() else []:
            meta, body = parse_post(p)
            if meta is None:
                continue
            slugs[lang][p.stem] = {"meta": meta, "body": body}
    return slugs


def find_gaps(slugs: dict[str, dict[str, dict]], languages) -> tuple[list, list]:
    """Return (missing, drafts) as (src, dst, slug) tuples, both directions."""
    missing: list[tuple[str, str, str]] = []
    drafts: list[tuple[str, str, str]] = []
    for src, dst in zip(languages, languages[1:] + languages[:1]):
        for s, card in slugs[src].items():
            if s in slugs[dst]:
                continue
            if card["meta"].get("draft", "").lower() == "true":
                drafts.append((src, dst, s))
            else:
                missing.append((src, dst, s))
    return missing, drafts


# --------------------------------------------------------------------------
# translation backends
# --------------------------------------------------------------------------

def deepl_key() -> str | None:
    key = os.environ.get("DEEPL_API_KEY")
    if key:
        return key.strip()
    f = Path.home() / ".config" / "deepl" / "api_key"
    if f.is_file():
        return f.read_text(encoding="utf-8").strip()
    return None


def make_deepl_translator(key: str | None = None):
    """Return translate(texts, source, target) -> list[str] using DeepL."""
    key = key or deepl_key()
    if not key:
        raise SystemExit(
            "ERROR: no DeepL key. Set DEEPL_API_KEY or create "
            "~/.config/deepl/api_key (chmod 600)."
        )
    url = API_FREE if key.endswith(":fx") else API_PRO
    lang_map = {"en": "EN", "nl": "NL"}

    def translate(texts: list[str], source: str, target: str) -> list[str]:
        payload = {
            "text": texts,
            "target_lang": lang_map[target],
            "source_lang": lang_map[source],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"DeepL-Auth-Key {key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        return [t["text"] for t in data["translations"]]

    return translate


# --------------------------------------------------------------------------
# gap filling
# --------------------------------------------------------------------------

def fill_gaps(docs_dir: Path, *, languages=("en", "nl"), blog_path: str = "blog/posts",
              translator=None, write: bool = False) -> Report:
    tr = translator or (lambda texts, source, target: texts)
    rep = Report()
    slugs = scan_slugs(docs_dir, languages, blog_path)

    for src, dst in zip(languages, languages[1:] + languages[:1]):
        cards = slugs[src]
        missing = [
            s for s, c in cards.items()
            if s not in slugs[dst] and c["meta"].get("draft", "").lower() != "true"
        ]
        drafts = [
            s for s, c in cards.items()
            if s not in slugs[dst] and c["meta"].get("draft", "").lower() == "true"
        ]
        rep.skipped_drafts.extend((src, dst, s) for s in drafts)
        if not write:
            rep.created.extend((src, dst, s) for s in missing)
            continue
        for s in missing:
            card = cards[s]
            meta, body = card["meta"], card["body"]
            chunks = split_blocks(body)
            prose_idx = [i for i, (_, is_code) in enumerate(chunks) if not is_code]
            prose_texts = [chunks[i][0] for i in prose_idx]
            translated = tr(prose_texts, src, dst) if prose_texts else []
            rep.chars += sum(len(t) for t in prose_texts)

            out_chunks: list[tuple[str, bool]] = list(chunks)
            for i, t in zip(prose_idx, translated):
                out_chunks[i] = (t, False)

            new_body = "\n\n".join(c for c, _ in out_chunks)
            title_t = tr([meta.get("title", s)], src, dst)[0]
            rep.chars += len(meta.get("title", ""))

            cats_yaml = ""
            if meta["categories"]:
                cats_yaml = "".join(f"\n  - {c}" for c in meta["categories"])
            text = (
                "---\n"
                f"title: \"{title_t}\"\n"
                f"date: {meta.get('date', '')}\n"
                f"categories:{cats_yaml}\n"
                "---\n\n"
                f"{new_body.rstrip()}\n"
                + PROVENANCE.format(source=f"{src}/{s}", direction=f"{src}->{dst}",
                                    date=datetime.date.today().isoformat())
            )
            out = posts_dir(docs_dir, dst, blog_path)
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{s}.md").write_text(text, encoding="utf-8")
            rep.created.append((src, dst, s))
    return rep
