#!/usr/bin/env python3
"""
build-routes.py — generate one static HTML file per SPA route.

Why this exists
---------------
The site is a client-rendered React SPA on GitHub Pages. Two problems follow:

1. Pages gets a request for /quit-porn, finds no such file, and answers 404.
   The page still renders, because 404.html is a copy of index.html and the
   router takes over, but crawlers are told the page does not exist.

2. react-helmet writes the per-route <title>, description and canonical only
   after JavaScript runs. Social scrapers (Facebook, Twitter/X, iMessage,
   Slack, LinkedIn) do not run JavaScript, so every shared deep link previewed
   with the HOME page's title and description.

Writing a real file per route fixes the first. Baking that route's metadata
into the file fixes the second. Helmet still runs and sets the same values, so
the static tags and the rendered tags agree.

Usage
-----
    python3 tools/build-routes.py          # regenerate every route file
    python3 tools/build-routes.py --check  # verify they are current, write nothing

Run this whenever index.html changes. --check exits non-zero if anything is
stale, so it can gate a deploy.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "index.html"
META = ROOT / "tools" / "route-meta.json"
ORIGIN = "https://thriverecoveryapp.com"


def esc(value: str) -> str:
    """Escape a string for use inside a double-quoted HTML attribute."""
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build(html: str, slug: str, title: str, description: str) -> str:
    """Return index.html rewritten for one route.

    Only the <head> is touched, and only the tags that identify the page. The
    body and the script tags are left byte-for-byte alone, so the SPA boots
    exactly as it does on the home page.
    """
    head_end = html.find("</head>")
    if head_end == -1:
        raise SystemExit("no </head> in index.html")
    head, rest = html[:head_end], html[head_end:]

    t, d = esc(title), esc(description)
    url = f"{ORIGIN}/{slug}"

    # <title> appears twice: the build-time one and helmet's data-rh copy.
    head = re.sub(r"<title(\s[^>]*)?>.*?</title>",
                  lambda m: f"<title{m.group(1) or ''}>{t}</title>", head, flags=re.S)

    # canonical must point at this route, not the home page.
    head = re.sub(r'(<link[^>]*rel="canonical"[^>]*href=")[^"]*(")',
                  lambda m: f"{m.group(1)}{url}{m.group(2)}", head)

    def set_meta(source: str, key: str, attr: str, value: str) -> str:
        pattern = rf'(<meta[^>]*{attr}="{re.escape(key)}"[^>]*content=")[^"]*(")'
        if re.search(pattern, source):
            return re.sub(pattern, lambda m: f"{m.group(1)}{value}{m.group(2)}", source)
        # Not present in the source: append before </head>.
        tag = f'<meta {attr}="{key}" content="{value}">'
        return source + f"\n    {tag}"

    head = set_meta(head, "description", "name", d)
    head = set_meta(head, "og:title", "property", t)
    head = set_meta(head, "og:description", "property", d)
    head = set_meta(head, "og:url", "property", url)
    head = set_meta(head, "twitter:title", "name", t)
    head = set_meta(head, "twitter:description", "name", d)

    return head + rest


def main() -> int:
    check_only = "--check" in sys.argv
    html = SOURCE.read_text(encoding="utf-8")
    routes = json.loads(META.read_text(encoding="utf-8"))

    stale, written = [], 0
    for slug, m in sorted(routes.items()):
        out = build(html, slug, m["title"], m["description"])
        path = ROOT / f"{slug}.html"
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == out:
            continue
        if check_only:
            stale.append(slug)
            continue
        path.write_text(out, encoding="utf-8")
        written += 1

    if check_only:
        if stale:
            print(f"STALE ({len(stale)}): {', '.join(stale)}")
            print("Run: python3 tools/build-routes.py")
            return 1
        print(f"All {len(routes)} route files are current.")
        return 0

    print(f"{written} written, {len(routes) - written} already current "
          f"({len(routes)} routes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
