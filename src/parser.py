"""
parser.py
---------
Extrage din HTML toate resursele externe (imagini, CSS, JS, fonturi,
documente) și linkurile interne (spre alte pagini de pe același domeniu).

Librării folosite:
    - bs4 (BeautifulSoup)  → parsare HTML, navigare DOM, căutare tag-uri
    - lxml                 → motor rapid de parsare (folosit de BeautifulSoup)
"""

from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from src.config import ALL_RESOURCE_EXTENSIONS, DOC_EXTENSIONS


def parse_html(html: str, base_url: str) -> dict:
    """
    Analizează HTML-ul și extrage toate referințele externe.

    Parametri:
        html:      conținutul HTML al paginii
        base_url:  URL-ul paginii (necesar pentru a transforma
                   căile relative în URL-uri absolute)

    Returnează:
        {
            "images":      list  - URL-uri imagini (<img src>),
            "stylesheets": list  - URL-uri foi de stil (<link rel="stylesheet">),
            "scripts":     list  - URL-uri scripturi (<script src>),
            "fonts":       list  - URL-uri fonturi (din <link>),
            "documents":   list  - URL-uri documente (.pdf, .docx etc.),
            "favicons":    list  - URL-uri favicon/icon,
            "internal_links": list - linkuri spre alte pagini de pe același domeniu,
            "external_links": list - linkuri spre alte domenii
        }
    """
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc

    result = {
        "images": [],
        "stylesheets": [],
        "scripts": [],
        "fonts": [],
        "documents": [],
        "favicons": [],
        "internal_links": [],
        "external_links": [],
    }

    # ── 1. Imagini: <img src="...">, <img srcset="..."> ──────────────
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and not src.startswith("data:"):
            result["images"].append(urljoin(base_url, src))

        # srcset conține mai multe URL-uri separate prin virgulă:
        # "img1.jpg 480w, img2.jpg 800w"
        srcset = img.get("srcset")
        if srcset:
            for entry in srcset.split(","):
                parts = entry.strip().split()
                if parts:
                    result["images"].append(urljoin(base_url, parts[0]))

    # ── 2. Elemente <picture> → <source srcset="..."> ────────────────
    for source in soup.find_all("source"):
        srcset = source.get("srcset")
        if srcset:
            for entry in srcset.split(","):
                parts = entry.strip().split()
                if parts:
                    result["images"].append(urljoin(base_url, parts[0]))

    # ── 3. Foi de stil: <link rel="stylesheet" href="..."> ───────────
    for link in soup.find_all("link"):
        rel = link.get("rel", [])
        href = link.get("href")
        if not href:
            continue

        full_url = urljoin(base_url, href)

        if "stylesheet" in rel:
            result["stylesheets"].append(full_url)
        elif "icon" in rel or "shortcut" in rel:
            result["favicons"].append(full_url)
        elif "preload" in rel:
            # Fonturi preîncărcate: <link rel="preload" as="font" href="...">
            as_type = link.get("as", "")
            if as_type == "font":
                result["fonts"].append(full_url)
            elif as_type == "style":
                result["stylesheets"].append(full_url)

    # ── 4. Scripturi: <script src="..."> ──────────────────────────────
    for script in soup.find_all("script"):
        src = script.get("src")
        if src:
            result["scripts"].append(urljoin(base_url, src))

    # ── 5. Linkuri (<a href="...">) → interne vs externe ─────────────
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue

        # Ignorăm ancore, mailto, javascript:, tel:
        if href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Verificăm dacă e un document descărcabil
        path_lower = parsed.path.lower()
        ext = "." + path_lower.rsplit(".", 1)[-1] if "." in path_lower else ""
        if ext in DOC_EXTENSIONS:
            result["documents"].append(full_url)
            continue

        # Clasificăm: intern (același domeniu) vs extern
        if parsed.netloc == base_domain or parsed.netloc == "":
            result["internal_links"].append(full_url)
        else:
            result["external_links"].append(full_url)

    # ── 6. Imagini din CSS inline: style="background-image: url(...)" ─
    for tag in soup.find_all(style=True):
        style = tag["style"]
        result["images"].extend(_extract_urls_from_inline_style(style, base_url))

    # ── Deduplicare pe fiecare categorie ──────────────────────────────
    for key in result:
        result[key] = sorted(set(result[key]))

    return result


def _extract_urls_from_inline_style(style_text: str, base_url: str) -> list:
    """
    Extrage URL-uri din atribute style inline.
    Ex: style="background-image: url('/img/bg.png')"
    """
    import re
    urls = []
    # Căutăm pattern-ul url(...) în textul CSS inline
    pattern = r"url\(\s*['\"]?([^'\")\s]+)['\"]?\s*\)"
    for match in re.finditer(pattern, style_text):
        url = match.group(1)
        if not url.startswith("data:"):
            urls.append(urljoin(base_url, url))
    return urls


def get_page_title(html: str) -> str:
    """Extrage titlul paginii (<title>...</title>)."""
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    return title_tag.get_text(strip=True) if title_tag else "Fără titlu"
