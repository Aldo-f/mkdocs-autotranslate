"""MkDocs plugin: report untranslated blog posts at build time.

Detection only — translation itself happens via the `blog-autotranslate` CLI
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

log = logging.getLogger("mkdocs.plugins.blog_autotranslate")


class BlogAutotranslatePlugin(BasePlugin):

    config_scheme = (
        ("languages", c.ListOfItems(c.Type(str), default=["en", "nl"])),
        ("blog_path", c.Type(str, default="blog/posts")),
        ("mode", c.Choice(("report", "strict"), default="report")),
    )

    def on_files(self, files, *, config):
        languages = [l.strip() for l in self.config["languages"] if l.strip()]
        if len(languages) < 2:
            log.warning("[blog-autotranslate] needs >= 2 languages, got %s", languages)
            return files

        docs_dir = config["docs_dir"]
        slugs = scan_slugs(docs_dir, languages, self.config["blog_path"])
        missing, drafts = find_gaps(slugs, languages)

        if drafts:
            for src, dst, s in drafts:
                log.info("[blog-autotranslate] skipping draft %s/%s", src, s)

        if not missing:
            log.info("[blog-autotranslate] all languages in sync (%s)", languages)
            return files

        summary = ", ".join(f"{src}->{dst}: {s}.md" for src, dst, s in missing)
        msg = f"[blog-autotranslate] {len(missing)} untranslated post(s): {summary}"
        if self.config["mode"] == "strict":
            raise PluginError(msg)
        log.warning(msg)
        return files
