"""
renderer.py
-----------
Randare completă a paginilor web folosind Playwright (Chromium headless).
Execută JavaScript-ul paginii și extrage HTML-ul final + lista de resurse
pe care browserul le-a încărcat efectiv din rețea.

Librării folosite:
    - playwright.async_api  → controlează Chromium headless
"""

from playwright.async_api import async_playwright
from src.config import USER_AGENT, PAGE_TIMEOUT_MS, EXTRA_WAIT_MS


async def render_page(url: str, wait_ms: int = EXTRA_WAIT_MS,
                      timeout_ms: int = PAGE_TIMEOUT_MS) -> dict:
    """
    Deschide `url` într-un browser headless, așteaptă randarea completă
    și returnează:
        {
            "html":       str   - HTML-ul final (după execuția JS),
            "resources":  list  - URL-uri ale tuturor resurselor încărcate,
            "status":     int   - codul HTTP al răspunsului principal,
            "final_url":  str   - URL-ul final (după eventuale redirect-uri)
        }
    """
    resources = []

    async with async_playwright() as pw:
        # Pornim un browser Chromium invizibil (fără fereastră)
        browser = await pw.chromium.launch(headless=True)

        # Creăm un context cu User-Agent realist
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        # Interceptăm FIECARE cerere de rețea finalizată de pagină.
        # Asta prinde și resursele încărcate dinamic de JavaScript
        # (imagini lazy-loaded, fonturi, date JSON etc.)
        def on_request_finished(request):
            resources.append(request.url)

        page.on("requestfinished", on_request_finished)

        # Navigăm la URL și așteptăm ca rețeaua să se stabilizeze
        # ("networkidle" = nu mai sunt cereri de rețea noi de 500ms)
        response = await page.goto(url, wait_until="networkidle", timeout=timeout_ms)

        # Așteptare suplimentară pentru conținut care apare cu delay
        # (ex: lazy-load declanșat de un setTimeout)
        await page.wait_for_timeout(wait_ms)

        # Extragem HTML-ul FINAL din DOM (nu cel brut primit de la server)
        html = await page.content()

        final_url = page.url
        status = response.status if response else None

        await browser.close()

    return {
        "html": html,
        "resources": sorted(set(resources)),
        "status": status,
        "final_url": final_url,
    }


async def check_url_alive(url: str, timeout_ms: int = 10000) -> dict:
    """
    Verificare rapidă dacă un URL răspunde (pentru dicționarul de căi comune).
    Nu randează pagina, doar face un request GET și verifică statusul.
    Returnează:
        {
            "url":     str  - URL-ul verificat,
            "alive":   bool - True dacă serverul a răspuns cu 200,
            "status":  int  - codul HTTP
        }
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        try:
            response = await page.goto(url, wait_until="commit", timeout=timeout_ms)
            status = response.status if response else 0
            alive = 200 <= status < 400
        except Exception:
            status = 0
            alive = False
        finally:
            await browser.close()

    return {"url": url, "alive": alive, "status": status}
