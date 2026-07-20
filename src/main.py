"""
main.py
-------
Punctul de intrare al aplicației. Orchestrează întregul pipeline:
  1. Parsează argumentele din linia de comandă
  2. Randează pagina/paginile cu Playwright
  3. Extrage resursele și linkurile cu BeautifulSoup + tinycss2
  4. Descarcă resursele cu aiohttp
  5. Rescrie linkurile cu BeautifulSoup
  6. Salvează snapshot-ul pe disc

Utilizare:
    # Snapshot o singură pagină:
    python main.py https://example.com

    # Snapshot domeniu întreg:
    python main.py https://example.com --mode domain

    # Cu opțiuni:
    python main.py https://example.com --mode domain --max-pages 50 --max-depth 3
"""

import os
import sys
import asyncio
import argparse

# Adăugăm directorul părinte în PYTHONPATH ca să putem importa din src.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import MAX_PAGES, MAX_DEPTH, MAX_CONCURRENT, ASSETS_SUBDIR
from src.renderer import render_page
from src.parser import parse_html, get_page_title
from src.css_parser import extract_css_resources, rewrite_css_urls
from src.fetcher import download_all, save_resource, generate_local_filename
from src.link_rewriter import rewrite_html
from src.storage import create_snapshot_dir, save_manifest, url_to_filename
from src.crawler import Crawler


# ═══════════════════════════════════════════════════════════════════════
#  SNAPSHOT O SINGURĂ PAGINĂ
# ═══════════════════════════════════════════════════════════════════════

async def snapshot_single_page(url: str) -> str:
    """
    Pipeline complet pentru snapshot-ul unei singure pagini.

    Pași:
        1. Randare HTML cu Playwright
        2. Parsare HTML → listă de resurse
        3. Parsare CSS → resurse suplimentare
        4. Descărcare toate resursele
        5. Rescriere linkuri → căi locale
        6. Salvare HTML + resurse pe disc

    Returnează: calea directorului snapshot creat.
    """
    print(f"\n{'='*60}")
    print(f"  SNAPSHOT PAGINĂ: {url}")
    print(f"{'='*60}\n")

    # ── Pas 1: Randare ────────────────────────────────────────────────
    print("[1/6] Randare pagină cu Playwright (Chromium headless)...")
    rendered = await render_page(url)
    html = rendered["html"]
    final_url = rendered["final_url"]
    print(f"      Status: {rendered['status']}")
    print(f"      URL final: {final_url}")
    print(f"      Resurse detectate de browser: {len(rendered['resources'])}")

    # ── Pas 2: Parsare HTML ───────────────────────────────────────────
    print("[2/6] Parsare HTML (BeautifulSoup + lxml)...")
    parsed = parse_html(html, final_url)
    title = get_page_title(html)
    print(f"      Titlu: {title}")
    print(f"      Imagini: {len(parsed['images'])}")
    print(f"      Foi de stil: {len(parsed['stylesheets'])}")
    print(f"      Scripturi: {len(parsed['scripts'])}")
    print(f"      Documente: {len(parsed['documents'])}")
    print(f"      Linkuri interne: {len(parsed['internal_links'])}")

    # ── Pas 3: Colectare toate URL-urile de descărcat ─────────────────
    all_resource_urls = (
        parsed["images"] + parsed["stylesheets"] + parsed["scripts"] +
        parsed["fonts"] + parsed["documents"] + parsed["favicons"]
    )
    all_resource_urls = list(set(all_resource_urls))  # deduplicare
    print(f"[3/6] Total resurse unice de descărcat: {len(all_resource_urls)}")

    # ── Pas 4: Descărcare resurse ─────────────────────────────────────
    print(f"[4/6] Descărcare resurse (max {MAX_CONCURRENT} paralele)...")
    downloaded = await download_all(all_resource_urls)
    success_count = sum(1 for d in downloaded if d["success"])
    print(f"      Descărcate cu succes: {success_count}/{len(downloaded)}")

    # ── Pas 4b: Parsare CSS descărcate → resurse suplimentare ─────────
    css_extra_urls = []
    css_contents = {}  # Păstrăm conținutul CSS pentru rescriere ulterioară
    for item in downloaded:
        if item["success"] and item["content_type"].startswith("text/css"):
            css_text = item["data"].decode("utf-8", errors="replace")
            css_contents[item["url"]] = css_text
            css_resources = extract_css_resources(css_text, item["url"])
            css_extra_urls.extend(css_resources["urls"])
            css_extra_urls.extend(css_resources["imports"])

    # Descărcăm și resursele din CSS (dacă sunt noi)
    css_extra_urls = [u for u in set(css_extra_urls) if u not in set(all_resource_urls)]
    if css_extra_urls:
        print(f"      Resurse suplimentare din CSS: {len(css_extra_urls)}")
        css_downloaded = await download_all(css_extra_urls)
        downloaded.extend(css_downloaded)

    # ── Pas 5: Creare structură foldere + salvare resurse ─────────────
    print("[5/6] Salvare snapshot pe disc...")
    dirs = create_snapshot_dir(url)
    print(f"      Director: {dirs['root']}")

    # Construim url_map: { url_original → cale_relativă_locală }
    url_map = {}
    assets_saved = []

    for item in downloaded:
        if not item["success"]:
            continue

        local_name = generate_local_filename(item["url"])
        local_path = os.path.join(dirs["assets"], local_name)
        await save_resource(item["data"], local_path)

        # Calea relativă de la pages/ la assets/ (pentru HTML)
        relative_path = f"../{ASSETS_SUBDIR}/{local_name}"
        url_map[item["url"]] = relative_path

        assets_saved.append({
            "url": item["url"],
            "local_file": local_name,
            "size_bytes": len(item["data"]),
            "content_type": item["content_type"],
        })

    # Rescrie CSS-urile salvate pe disc (înlocuiește url-urile interne)
    for css_url, css_text in css_contents.items():
        if css_url in url_map:
            local_name = generate_local_filename(css_url)
            local_path = os.path.join(dirs["assets"], local_name)
            # Construim un url_map relativ la locația CSS-ului
            css_url_map = {}
            for orig_url, rel_path in url_map.items():
                # Din assets/, calea relativă e doar numele fișierului
                css_url_map[orig_url] = os.path.basename(rel_path)
            rewritten_css = rewrite_css_urls(css_text, css_url_map)
            await save_resource(rewritten_css.encode("utf-8"), local_path)

    # ── Pas 6: Rescriere HTML + salvare ───────────────────────────────
    print("[6/6] Rescriere linkuri și salvare HTML...")
    rewritten_html = rewrite_html(html, final_url, url_map)
    page_filename = url_to_filename(final_url)
    page_path = os.path.join(dirs["pages"], page_filename)
    await save_resource(rewritten_html.encode("utf-8"), page_path)

    # Salvăm manifestul
    pages_saved = [{
        "url": final_url,
        "title": title,
        "local_file": page_filename,
        "status": rendered["status"],
    }]

    manifest_path = save_manifest(dirs["root"], url, pages_saved, assets_saved,
                                  mode="single")

    print(f"\n{'─'*60}")
    print(f"  SNAPSHOT COMPLET!")
    print(f"  Director: {dirs['root']}")
    print(f"  Pagini: {len(pages_saved)}")
    print(f"  Resurse: {len(assets_saved)}")
    print(f"  Manifest: {manifest_path}")
    print(f"{'─'*60}\n")

    return dirs["root"]


# ═══════════════════════════════════════════════════════════════════════
#  SNAPSHOT DOMENIU ÎNTREG
# ═══════════════════════════════════════════════════════════════════════

async def snapshot_domain(url: str, max_pages: int = MAX_PAGES,
                          max_depth: int = MAX_DEPTH) -> str:
    """
    Pipeline complet pentru snapshot-ul unui domeniu întreg.

    Pași:
        1. Inițializare crawler (seed + dicționar căi comune)
        2. Pentru fiecare pagină din coadă:
           a. Randare cu Playwright
           b. Parsare HTML + CSS → resurse + linkuri noi
           c. Adaugă linkurile noi în coada crawler-ului
           d. Descarcă resursele
        3. Rescriere linkuri în toate HTML-urile
        4. Salvare totul pe disc

    Returnează: calea directorului snapshot creat.
    """
    print(f"\n{'='*60}")
    print(f"  SNAPSHOT DOMENIU: {url}")
    print(f"  Max pagini: {max_pages}, Max adâncime: {max_depth}")
    print(f"{'='*60}\n")

    # ── Pas 1: Inițializare crawler ───────────────────────────────────
    crawler = Crawler(url, max_pages=max_pages, max_depth=max_depth)
    await crawler.initialize()
    print(f"[INIT] Coadă inițializată: {crawler.queue.qsize()} URL-uri")
    print(f"       (include {len(COMMON_PATHS)} căi din dicționar)\n")

    # ── Pas 2: Creare structură foldere ───────────────────────────────
    dirs = create_snapshot_dir(url)
    print(f"[DIRS] Director snapshot: {dirs['root']}\n")

    # Colecții globale
    all_pages_data = []     # info despre paginile salvate
    all_assets_data = []    # info despre resursele salvate
    global_url_map = {}     # { url_resursă → cale_locală }
    page_map = {}           # { url_pagină → cale_locală }
    page_html_map = {}      # { url_pagină → HTML randat } (pentru rescriere finală)

    # ── Pas 3: Crawling bucle ─────────────────────────────────────────
    while True:
        item = await crawler.get_next()
        if item is None:
            break

        page_url = item["url"]
        depth = item["depth"]
        page_num = crawler.pages_processed

        print(f"[{page_num}/{max_pages}] Profunzime {depth}: {page_url}")

        # 3a. Randare
        try:
            rendered = await render_page(page_url)
        except Exception as e:
            print(f"         Eroare randare: {e}")
            continue

        if rendered["status"] and rendered["status"] >= 400:
            print(f"         Status {rendered['status']} — sărit")
            continue

        html = rendered["html"]
        final_url = rendered["final_url"]
        title = get_page_title(html)
        print(f"         Titlu: {title}")

        # 3b. Parsare HTML
        parsed = parse_html(html, final_url)

        # 3c. Adăugăm linkurile interne noi în coadă
        await crawler.add_links(parsed["internal_links"], depth)

        # 3d. Colectăm resursele de descărcat
        page_resource_urls = (
            parsed["images"] + parsed["stylesheets"] + parsed["scripts"] +
            parsed["fonts"] + parsed["documents"] + parsed["favicons"]
        )
        # Doar cele pe care nu le-am descărcat deja
        new_urls = [u for u in set(page_resource_urls) if u not in global_url_map]

        if new_urls:
            downloaded = await download_all(new_urls)
            for item_dl in downloaded:
                if not item_dl["success"]:
                    continue

                local_name = generate_local_filename(item_dl["url"])
                local_path = os.path.join(dirs["assets"], local_name)
                await save_resource(item_dl["data"], local_path)

                relative_path = f"../{ASSETS_SUBDIR}/{local_name}"
                global_url_map[item_dl["url"]] = relative_path

                all_assets_data.append({
                    "url": item_dl["url"],
                    "local_file": local_name,
                    "size_bytes": len(item_dl["data"]),
                    "content_type": item_dl["content_type"],
                })

                # Parsare CSS suplimentară
                if item_dl["content_type"].startswith("text/css"):
                    css_text = item_dl["data"].decode("utf-8", errors="replace")
                    css_res = extract_css_resources(css_text, item_dl["url"])
                    extra_css = [u for u in css_res["urls"] + css_res["imports"]
                                 if u not in global_url_map]
                    if extra_css:
                        extra_dl = await download_all(extra_css)
                        for ex_item in extra_dl:
                            if not ex_item["success"]:
                                continue
                            ex_name = generate_local_filename(ex_item["url"])
                            ex_path = os.path.join(dirs["assets"], ex_name)
                            await save_resource(ex_item["data"], ex_path)
                            global_url_map[ex_item["url"]] = f"../{ASSETS_SUBDIR}/{ex_name}"

            print(f"         Resurse noi: {len(new_urls)}")

        # Salvăm HTML-ul și info-ul paginii (rescriem linkurile la final)
        page_filename = url_to_filename(final_url)
        page_map[final_url] = page_filename
        page_html_map[final_url] = html

        all_pages_data.append({
            "url": final_url,
            "title": title,
            "local_file": page_filename,
            "status": rendered["status"],
            "depth": depth,
        })

    # ── Pas 4: Rescriere finală a tuturor HTML-urilor ─────────────────
    print(f"\n[REWRITE] Rescriere linkuri în {len(page_html_map)} pagini...")

    # Construim page_map cu căi relative (de la pages/ la pages/)
    relative_page_map = {url: f"./{filename}" for url, filename in page_map.items()}

    for page_url, html in page_html_map.items():
        rewritten = rewrite_html(html, page_url, global_url_map, relative_page_map)
        page_filename = page_map[page_url]
        page_path = os.path.join(dirs["pages"], page_filename)
        await save_resource(rewritten.encode("utf-8"), page_path)

    # ── Pas 5: Salvare manifest ───────────────────────────────────────
    manifest_path = save_manifest(dirs["root"], url, all_pages_data,
                                  all_assets_data, mode="domain")

    stats = crawler.get_stats()

    print(f"\n{'='*60}")
    print(f"  SNAPSHOT DOMENIU COMPLET!")
    print(f"  Director:           {dirs['root']}")
    print(f"  Pagini salvate:     {len(all_pages_data)}")
    print(f"  Resurse salvate:    {len(all_assets_data)}")
    print(f"  Pagini descoperite: {stats['pages_discovered']}")
    print(f"  Manifest:           {manifest_path}")
    print(f"{'='*60}\n")

    return dirs["root"]


# ═══════════════════════════════════════════════════════════════════════
#  CLI — LINIA DE COMANDĂ
# ═══════════════════════════════════════════════════════════════════════

# Importăm COMMON_PATHS aici pentru a-l folosi în mesajul de print
from src.config import COMMON_PATHS


def main():
    """Punct de intrare — parsează argumentele și pornește pipeline-ul."""
    parser = argparse.ArgumentParser(
        description="Web Archiver — Snapshot offline pentru pagini/domenii web",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemple:
  python main.py https://example.com
  python main.py https://example.com --mode domain
  python main.py https://example.com --mode domain --max-pages 50 --max-depth 3
        """,
    )

    parser.add_argument("url", help="URL-ul paginii sau domeniului de capturat")

    parser.add_argument(
        "--mode", choices=["single", "domain"], default="single",
        help="'single' = o pagină, 'domain' = tot domeniul (implicit: single)"
    )

    parser.add_argument(
        "--max-pages", type=int, default=MAX_PAGES,
        help=f"Nr. maxim de pagini la crawling domeniu (implicit: {MAX_PAGES})"
    )

    parser.add_argument(
        "--max-depth", type=int, default=MAX_DEPTH,
        help=f"Adâncime maximă de crawling (implicit: {MAX_DEPTH})"
    )

    args = parser.parse_args()

    # Validare URL
    if not args.url.startswith(("http://", "https://")):
        print("Eroare: URL-ul trebuie să înceapă cu http:// sau https://")
        sys.exit(1)

    # Lansare pipeline
    if args.mode == "single":
        asyncio.run(snapshot_single_page(args.url))
    else:
        asyncio.run(snapshot_domain(args.url, args.max_pages, args.max_depth))


if __name__ == "__main__":
    main()
