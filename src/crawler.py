"""
crawler.py
----------
Gestionează crawling-ul recursiv al unui domeniu: menține coada de
pagini de vizitat, aplică deduplicare, respectă limitele de adâncime,
și încearcă automat dicționarul de căi comune.

Librării folosite:
    - asyncio        → orchestrare task-uri
    - urllib.parse   → normalizare URL-uri, comparare domenii
"""

import asyncio
from urllib.parse import urlparse, urljoin, urldefrag
from src.config import MAX_PAGES, MAX_DEPTH, COMMON_PATHS


class Crawler:
    """
    Crawler recursiv care descoperă toate paginile de pe un domeniu.

    Atribute:
        seed_url:       URL-ul de pornire
        domain:         domeniul (netloc) pe care rămânem
        visited:        set de URL-uri deja vizitate
        queue:          coadă de (url, adâncime) de procesat
        max_pages:      limită maximă de pagini
        max_depth:      adâncime maximă de la seed
    """

    def __init__(self, seed_url: str, max_pages: int = MAX_PAGES,
                 max_depth: int = MAX_DEPTH):
        self.seed_url = self._normalize(seed_url)
        self.domain = urlparse(self.seed_url).netloc
        self.scheme = urlparse(self.seed_url).scheme

        self.visited = set()        # URL-uri deja procesate
        self.discovered = set()     # URL-uri descoperite (vizitate sau în coadă)
        self.queue = asyncio.Queue()

        self.max_pages = max_pages
        self.max_depth = max_depth
        self.pages_processed = 0

    async def initialize(self):
        """
        Populează coada inițială:
        1. URL-ul seed
        2. Căile din dicționarul de căi comune
        """
        # Adăugăm URL-ul de pornire
        await self._enqueue(self.seed_url, depth=0)

        # Adăugăm toate căile din dicționar (cu adâncime 1,
        # ca să nu fie prioritizate peste linkurile directe din seed)
        for path in COMMON_PATHS:
            full_url = f"{self.scheme}://{self.domain}{path}"
            await self._enqueue(full_url, depth=1)

    async def get_next(self) -> dict | None:
        """
        Scoate următorul URL din coadă, dacă nu am depășit limitele.

        Returnează:
            {"url": str, "depth": int} sau None dacă coada e goală / limita atinsă
        """
        if self.pages_processed >= self.max_pages:
            return None

        try:
            item = self.queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

        url, depth = item

        # Verificăm dacă nu am depășit adâncimea maximă
        if depth > self.max_depth:
            return await self.get_next()  # Încercăm următorul

        self.visited.add(url)
        self.pages_processed += 1

        return {"url": url, "depth": depth}

    async def add_links(self, links: list, current_depth: int):
        """
        Adaugă linkuri noi descoperite în coadă (dacă aparțin domeniului).

        Parametri:
            links:          lista de URL-uri găsite pe pagina curentă
            current_depth:  adâncimea paginii curente (linkurile noi vor fi depth+1)
        """
        for link in links:
            normalized = self._normalize(link)

            # Verificăm că aparține aceluiași domeniu
            if not self._is_same_domain(normalized):
                continue

            await self._enqueue(normalized, depth=current_depth + 1)

    async def _enqueue(self, url: str, depth: int):
        """Adaugă un URL în coadă dacă nu a fost deja descoperit."""
        if url in self.discovered:
            return

        self.discovered.add(url)
        await self.queue.put((url, depth))

    def _is_same_domain(self, url: str) -> bool:
        """Verifică dacă un URL aparține aceluiași domeniu cu seed-ul."""
        parsed = urlparse(url)

        # Trebuie să fie HTTP/HTTPS
        if parsed.scheme not in ("http", "https"):
            return False

        return parsed.netloc == self.domain

    @staticmethod
    def _normalize(url: str) -> str:
        """
        Normalizează un URL pentru deduplicare:
        - Elimină fragmentul (#section)
        - Elimină trailing slash redundant
        - Lowercase pe scheme și netloc
        """
        # Eliminăm fragmentul (#...)
        url, _ = urldefrag(url)

        parsed = urlparse(url)

        # Lowercase pe scheme și domeniu
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Normalizăm path-ul (eliminăm trailing slash, cu excepția "/")
        path = parsed.path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        # Reconstruim URL-ul normalizat
        normalized = f"{scheme}://{netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"

        return normalized

    def get_stats(self) -> dict:
        """Returnează statistici curente despre crawling."""
        return {
            "domain": self.domain,
            "pages_processed": self.pages_processed,
            "pages_discovered": len(self.discovered),
            "pages_remaining": self.queue.qsize(),
            "max_pages": self.max_pages,
            "max_depth": self.max_depth,
        }
