"""CLI: fill blog translation gaps via DeepL.

Dry-run by default; --write persists translated files next to the originals.
Review the git diff before committing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import fill_gaps, make_deepl_translator


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="autotranslate",
        description="Translate missing blog posts between language trees (DeepL).",
    )
    p.add_argument("--docs-dir", required=True, type=Path,
                   help="Path to the MkDocs docs/ directory")
    p.add_argument("--languages", nargs="+", default=["en", "nl"],
                   help="Language directories under docs-dir (default: en nl)")
    p.add_argument("--paths", nargs="+",
                   default=["blog/posts"],
                   help="Dirs/files/globs under each language dir to compare "
                        "(default: blog/posts)")
    p.add_argument("--exclude", nargs="+", default=[],
                   help="fnmatch patterns of language-relative paths to skip")
    p.add_argument("--write", action="store_true",
                   help="Actually create missing translations (default: dry-run)")
    args = p.parse_args(argv)

    tr = make_deepl_translator() if args.write else None
    rep = fill_gaps(args.docs_dir, languages=args.languages,
                    paths=args.paths, exclude=args.exclude,
                    translator=tr, write=args.write)

    print(f"{'WROTE' if args.write else 'WOULD CREATE'} {len(rep.created)} post(s):")
    for src, dst, s in rep.created:
        print(f"  {src} -> {dst}  {s}")
    for src, dst, s in rep.skipped_drafts:
        print(f"  SKIP draft  {src}/{s}")
    if args.write and rep.chars:
        print(f"~{rep.chars:,} characters sent to DeepL")
    if not rep.created and not rep.skipped_drafts:
        print("Nothing to do — all languages are in sync.")
    elif rep.created and not args.write:
        print("\nRe-run with --write to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
