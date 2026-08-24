"""MkDocs plugin: report untranslated content at build time.

Detection only — translation itself happens via the `autotranslate` CLI
so machine-translated files are always human-reviewed before commit.
"""

from __future__ import annotations

import logging

try:
    from mkdocs.exceptions import PluginError
except ImportError:  # pragma: no cover - very old mkdocs
    PluginError = RuntimeError

from mkdocs.plugins import BasePlugin
from mkdocs.config import config_options as c

from .core import find_gaps, scan_slugs

log = logging.getLogger("mkdocs.plugins.autotranslate")


class AutotranslatePlugin(BasePlugin):

    config_scheme = (
        ("languages", c.ListOfItems(c.Type(str), default=["en", "nl"])),
        # paths: dirs/files/globs under each language dir to compare.
        # Empty -> fall back to blog_path (backward compatible).
        ("paths", c.ListOfItems(c.Type(str), default=[])),
        ("blog_path", c.Type(str, default="blog/posts")),
        ("exclude", c.ListOfItems(c.Type(str), default=[])),
        ("mode", c.Choice(("report", "strict"), default="report")),
    )

    def on_files(self, files, *, config):
        languages = [l.strip() for l in self.config["languages"] if l.strip()]
        if len(languages) < 2:
            log.warning("[autotranslate] needs >= 2 languages, got %s", languages)
            return files

        paths = [p for p in self.config["paths"]] or [self.config["blog_path"]]
        docs_dir = config["docs_dir"]
        slugs = scan_slugs(docs_dir, languages, paths, self.config["exclude"])
        missing, drafts = find_gaps(slugs, languages)

        if drafts:
            for src, dst, s in drafts:
                log.info("[autotranslate] skipping draft %s/%s.md", src, s)

        if not missing:
            log.info("[autotranslate] all languages in sync (%s) paths=%s",
                     languages, paths)
            return files

        summary = ", ".join(f"{src}->{dst}: {s}.md" for src, dst, s in missing)
        msg = f"[autotranslate] {len(missing)} untranslated post(s): {summary}"
        if self.config["mode"] == "strict":
            raise PluginError(msg)
        log.warning(msg)
        return files
