"""
link_rewriter.py
-----------------
Rescrie toate URL-urile externe din HTML și CSS, înlocuindu-le
cu căi locale relative, astfel încât snapshot-ul să funcționeze offline.

Librării folosite:
    - bs4 (BeautifulSoup)  → navigare și modificare atribute HTML
    - lxml                 → motor de parsare (sub BeautifulSoup)
    - re                   → regex pentru url(...) din CSS inline
"""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def rewrite_html(html: str, base_url: str, url_map: dict,
                 page_map: dict = None) -> str:
    """
    Rescrie toate URL-urile din HTML cu căi locale.

    Parametri:
        html:      conținutul HTML original
        base_url:  URL-ul paginii (pentru rezolvarea căilor relative)
        url_map:   { url_resursa: cale_locala }
                   ex: {"https://cdn.com/logo.png": "../assets/a1b2_logo.png"}
        page_map:  { url_pagina: cale_locala }  (opțional, pentru linkuri interne)
                   ex: {"https://site.com/about": "./about.html"}

    Returnează:
        HTML-ul cu toate referințele rescrise către fișiere locale
    """
    if page_map is None:
        page_map = {}

    soup = BeautifulSoup(html, "lxml")

    # ── 1. Imagini: <img src="..."> și <img srcset="..."> ────────────
    for img in soup.find_all("img"):
        _rewrite_attr(img, "src", base_url, url_map)
        _rewrite_srcset(img, base_url, url_map)

    # ── 2. Elemente <source srcset="..."> (din <picture>) ────────────
    for source in soup.find_all("source"):
        _rewrite_srcset(source, base_url, url_map)

    # ── 3. Foi de stil: <link rel="stylesheet" href="..."> ───────────
    for link in soup.find_all("link"):
        _rewrite_attr(link, "href", base_url, url_map)

    # ── 4. Scripturi: <script src="..."> ──────────────────────────────
    for script in soup.find_all("script"):
        _rewrite_attr(script, "src", base_url, url_map)

    # ── 5. Linkuri interne: <a href="..."> ────────────────────────────
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue

        full_url = urljoin(base_url, href)

        # Dacă linkul duce la o pagină pe care am salvat-o
        if full_url in page_map:
            a["href"] = page_map[full_url]
        # Dacă linkul duce la un document descărcat
        elif full_url in url_map:
            a["href"] = url_map[full_url]

    # ── 6. CSS inline: style="background-image: url(...)" ────────────
    for tag in soup.find_all(style=True):
        tag["style"] = _rewrite_inline_style(tag["style"], base_url, url_map)

    # ── 7. <style>...</style> embedded ────────────────────────────────
    for style_tag in soup.find_all("style"):
        if style_tag.string:
            style_tag.string = _rewrite_css_text(style_tag.string, base_url, url_map)

    return str(soup)


def _rewrite_attr(tag, attr: str, base_url: str, url_map: dict):
    """Rescrie un singur atribut (src, href) dacă URL-ul e în url_map."""
    value = tag.get(attr)
    if not value or value.startswith("data:"):
        return

    full_url = urljoin(base_url, value)
    if full_url in url_map:
        tag[attr] = url_map[full_url]


def _rewrite_srcset(tag, base_url: str, url_map: dict):
    """Rescrie atributul srcset (care conține mai multe URL-uri)."""
    srcset = tag.get("srcset")
    if not srcset:
        return

    new_entries = []
    for entry in srcset.split(","):
        parts = entry.strip().split()
        if parts:
            full_url = urljoin(base_url, parts[0])
            if full_url in url_map:
                parts[0] = url_map[full_url]
            new_entries.append(" ".join(parts))

    tag["srcset"] = ", ".join(new_entries)


def _rewrite_inline_style(style_text: str, base_url: str, url_map: dict) -> str:
    """Rescrie url(...) din atribute style inline."""
    def replace_url(match):
        raw_url = match.group(1).strip("'\"")
        full_url = urljoin(base_url, raw_url)
        if full_url in url_map:
            return f"url('{url_map[full_url]}')"
        return match.group(0)

    return re.sub(r"url\(\s*([^)]+)\s*\)", replace_url, style_text)


def _rewrite_css_text(css_text: str, base_url: str, url_map: dict) -> str:
    """Rescrie url(...) din blocuri <style>...</style>."""
    return _rewrite_inline_style(css_text, base_url, url_map)
