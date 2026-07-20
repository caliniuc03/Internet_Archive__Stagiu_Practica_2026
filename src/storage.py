"""
storage.py
----------
Organizează structura de foldere a snapshot-ului și generează
manifestul JSON cu metadatele capturii.

Librării folosite:
    - os        → creare directoare, manipulare căi
    - json      → serializare manifest
    - datetime  → timestamp snapshot
"""

import os
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.config import OUTPUT_DIR, PAGES_SUBDIR, ASSETS_SUBDIR, MANIFEST_FILE


def create_snapshot_dir(url: str, base_dir: str = OUTPUT_DIR) -> dict:
    """
    Creează structura de directoare pentru un snapshot nou.

    Structura:
        snapshots/
          example.com_2024-01-15_14-30-00/
            pages/          ← HTML-urile paginilor
            assets/         ← resurse (imagini, CSS, JS, fonturi, documente)
            manifest.json   ← metadate despre snapshot

    Parametri:
        url:       URL-ul de pornire
        base_dir:  directorul părinte (implicit: ./snapshots/)

    Returnează:
        {
            "root":    str  - calea completă a directorului snapshot,
            "pages":   str  - calea subdirectorului pages/,
            "assets":  str  - calea subdirectorului assets/
        }
    """
    domain = urlparse(url).netloc or "unknown"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"{domain}_{timestamp}"

    root = os.path.join(base_dir, folder_name)
    pages = os.path.join(root, PAGES_SUBDIR)
    assets = os.path.join(root, ASSETS_SUBDIR)

    os.makedirs(pages, exist_ok=True)
    os.makedirs(assets, exist_ok=True)

    return {"root": root, "pages": pages, "assets": assets}


def save_manifest(snapshot_dir: str, url: str, pages_saved: list,
                  assets_saved: list, mode: str = "single") -> str:
    """
    Generează și salvează manifestul JSON al snapshot-ului.

    Parametri:
        snapshot_dir:  directorul rădăcină al snapshot-ului
        url:           URL-ul de pornire
        pages_saved:   listă de dict-uri cu info despre paginile salvate
        assets_saved:  listă de dict-uri cu info despre resursele salvate
        mode:          "single" (o singură pagină) sau "domain" (tot domeniul)

    Returnează:
        calea fișierului manifest.json creat
    """
    manifest = {
        "snapshot_info": {
            "url": url,
            "mode": mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_pages": len(pages_saved),
            "total_assets": len(assets_saved),
        },
        "pages": pages_saved,
        "assets": assets_saved,
    }

    manifest_path = os.path.join(snapshot_dir, MANIFEST_FILE)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest_path


def url_to_filename(url: str) -> str:
    """
    Convertește un URL de pagină într-un nume de fișier HTML local sigur.

    Exemplu:
        "https://example.com/about/team"  → "about_team.html"
        "https://example.com/"            → "index.html"
        "https://example.com/blog?p=5"    → "blog_p_5.html"
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path:
        return "index.html"

    # Înlocuim separatorii cu underscore
    safe_name = path.replace("/", "_").replace("\\", "_")

    # Adăugăm query params dacă există
    if parsed.query:
        safe_query = parsed.query.replace("&", "_").replace("=", "_")
        safe_name = f"{safe_name}_{safe_query}"

    # Curățăm caractere problematice
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in safe_name)

    # Limităm lungimea
    safe_name = safe_name[:100]

    # Adăugăm extensia .html dacă nu o are
    if not safe_name.endswith(".html"):
        safe_name += ".html"

    return safe_name
