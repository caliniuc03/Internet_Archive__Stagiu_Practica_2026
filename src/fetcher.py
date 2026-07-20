"""
fetcher.py
----------
Descarcă resurse (imagini, CSS, JS, fonturi, documente) în paralel,
cu limită de concurență și rate limiting, și le salvează pe disc.

Librării folosite:
    - aiohttp   → client HTTP asincron (descărcare paralelă)
    - aiofiles  → scriere fișiere asincronă (nu blochează event loop-ul)
    - asyncio   → orchestrare task-uri paralele + semaphore
"""

import os
import asyncio
import hashlib
from urllib.parse import urlparse

import aiohttp
import aiofiles

from src.config import MAX_CONCURRENT, REQUEST_DELAY, USER_AGENT


async def download_resource(session: aiohttp.ClientSession, url: str,
                            semaphore: asyncio.Semaphore) -> dict:
    """
    Descarcă o singură resursă de la URL-ul dat.

    Parametri:
        session:    sesiunea HTTP reutilizabilă
        url:        URL-ul resursei de descărcat
        semaphore:  limitator de concurență (max N descărcări simultane)

    Returnează:
        {
            "url":          str   - URL-ul original,
            "data":         bytes - conținutul descărcat (sau b"" la eroare),
            "content_type": str   - tipul MIME al răspunsului,
            "status":       int   - codul HTTP,
            "success":      bool  - True dacă s-a descărcat cu succes
        }
    """
    async with semaphore:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.read()
                return {
                    "url": url,
                    "data": data,
                    "content_type": resp.headers.get("Content-Type", ""),
                    "status": resp.status,
                    "success": 200 <= resp.status < 400,
                }
        except Exception as e:
            return {
                "url": url,
                "data": b"",
                "content_type": "",
                "status": 0,
                "success": False,
                "error": str(e),
            }
        finally:
            # Rate limiting: pauză între cereri ca să nu suprasoliciteze serverul
            await asyncio.sleep(REQUEST_DELAY)


async def download_all(urls: list, max_concurrent: int = MAX_CONCURRENT) -> list:
    """
    Descarcă o listă de URL-uri în paralel, cu limită de concurență.

    Parametri:
        urls:            lista de URL-uri de descărcat
        max_concurrent:  nr. maxim de descărcări simultane

    Returnează:
        listă de dict-uri (câte unul per URL, cu datele descărcate)
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    headers = {"User-Agent": USER_AGENT}

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [download_resource(session, url, semaphore) for url in urls]
        results = await asyncio.gather(*tasks)

    return list(results)


async def save_resource(data: bytes, output_path: str) -> str:
    """
    Salvează datele pe disc la calea specificată (asincron).

    Parametri:
        data:         bytes de scris
        output_path:  calea completă a fișierului de creat

    Returnează:
        calea la care a fost salvat fișierul
    """
    # Ne asigurăm că directorul părinte există
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    async with aiofiles.open(output_path, "wb") as f:
        await f.write(data)

    return output_path


def generate_local_filename(url: str) -> str:
    """
    Generează un nume de fișier local unic pentru o resursă, bazat pe
    URL-ul ei. Folosește un hash scurt + extensia originală.

    Exemplu:
        "https://cdn.example.com/images/photo.jpg?v=2"
        → "a1b2c3d4_photo.jpg"
    """
    parsed = urlparse(url)
    path = parsed.path

    # Extragem numele fișierului original și extensia
    original_name = os.path.basename(path) or "resource"
    name, ext = os.path.splitext(original_name)

    # Dacă nu are extensie, încercăm să ghicim din path
    if not ext:
        ext = ".html"

    # Generăm un hash scurt din URL-ul complet (pentru unicitate)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

    # Curățăm numele de caractere problematice
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:30]

    return f"{url_hash}_{safe_name}{ext}"
