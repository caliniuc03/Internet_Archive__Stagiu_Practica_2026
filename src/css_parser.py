"""
css_parser.py
-------------
Parsează conținutul fișierelor CSS și extrage toate referințele
către resurse externe: background-image, @font-face, @import etc.

Librării folosite:
    - tinycss2  → parsare CSS, navigare token-uri, extragere url()
"""

from urllib.parse import urljoin
import tinycss2


def extract_css_resources(css_text: str, css_url: str) -> dict:
    """
    Analizează o foaie de stil CSS și extrage toate resursele referite.

    Parametri:
        css_text:  conținutul textual al fișierului CSS
        css_url:   URL-ul fișierului CSS (pentru rezolvarea căilor relative)

    Returnează:
        {
            "urls":     list  - toate URL-urile găsite în url(...),
            "imports":  list  - foi de stil importate prin @import
        }
    """
    urls = []
    imports = []

    tokens = tinycss2.parse_stylesheet(css_text, skip_whitespace=True)
    _scan_token_list(tokens, css_url, urls, imports)

    return {
        "urls": sorted(set(urls)),
        "imports": sorted(set(imports)),
    }


def _scan_token_list(token_list, base_url: str, urls: list, imports: list):
    """
    Parcurge recursiv lista de token-uri CSS și colectează URL-uri.

    Token-urile CSS pot fi de mai multe tipuri:
        - "url"              → url(/img/bg.png)         — un URL direct
        - "function" cu "url" → url("/img/bg.png")      — URL între ghilimele
        - "at-rule" @import  → @import url(...)         — import de alt CSS
        - "at-rule" @font-face → conține src: url(...)  — fonturi
        - "qualified-rule"   → reguli normale cu { content }
    """
    for token in token_list:
        token_type = token.type

        # Token direct de tip url: url(cale/fără/ghilimele)
        if token_type == "url":
            full_url = urljoin(base_url, token.value)
            urls.append(full_url)

        # Funcție url("cale/cu/ghilimele")
        elif token_type == "function" and token.lower_name == "url":
            for arg in token.arguments:
                if arg.type == "string":
                    full_url = urljoin(base_url, arg.value)
                    urls.append(full_url)

        # @import url(...) sau @import "fisier.css"
        elif token_type == "at-rule" and token.lower_at_keyword == "import":
            for prelude_token in token.prelude:
                if prelude_token.type == "url":
                    imports.append(urljoin(base_url, prelude_token.value))
                elif prelude_token.type == "string":
                    imports.append(urljoin(base_url, prelude_token.value))
                elif prelude_token.type == "function" and prelude_token.lower_name == "url":
                    for arg in prelude_token.arguments:
                        if arg.type == "string":
                            imports.append(urljoin(base_url, arg.value))

        # Regulă calificată (ex: .clasa { background: url(...) })
        # sau @font-face { src: url(...) }
        # → parcurgem recursiv conținutul
        if hasattr(token, "content") and token.content:
            _scan_token_list(token.content, base_url, urls, imports)
        if hasattr(token, "prelude") and token.prelude:
            _scan_token_list(token.prelude, base_url, urls, imports)


def rewrite_css_urls(css_text: str, url_map: dict) -> str:
    """
    Înlocuiește toate URL-urile din CSS cu căi locale.

    Parametri:
        css_text:  conținutul CSS original
        url_map:   dicționar { url_original: cale_locala }
                   ex: {"https://cdn.com/bg.png": "./assets/img_a1b2.png"}

    Returnează:
        CSS-ul modificat, cu URL-urile rescrise.
    """
    import re

    def replace_url(match):
        original_url = match.group(1).strip("'\"")
        if original_url in url_map:
            return f"url('{url_map[original_url]}')"
        return match.group(0)

    # Înlocuim toate aparițiile url(...) din CSS
    pattern = r"url\(\s*([^)]+)\s*\)"
    return re.sub(pattern, replace_url, css_text)
