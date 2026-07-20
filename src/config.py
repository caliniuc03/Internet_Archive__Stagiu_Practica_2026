"""
config.py
---------
Configurări globale ale aplicației: constante, dicționar de căi comune,
extensii de fișiere recunoscute, user-agent, limite de crawling.
"""

import os

# ── Directorul implicit de output ────────────────────────────────────
OUTPUT_DIR = os.path.join(os.getcwd(), "snapshots")

# ── User-Agent realist (ca să nu fim blocați de servere) ─────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# ── Limite de crawling ───────────────────────────────────────────────
MAX_PAGES = 100             # nr. maxim de pagini pe domeniu
MAX_DEPTH = 5               # adâncime maximă de la pagina seed
MAX_CONCURRENT = 5          # descărcări paralele simultane
REQUEST_DELAY = 0.5         # secunde între cereri (rate limiting)
PAGE_TIMEOUT_MS = 30000     # timeout randare pagină (ms)
EXTRA_WAIT_MS = 2000        # așteptare suplimentară după networkidle (ms)

# ── Extensii de resurse pe care le descărcăm ─────────────────────────
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp"}
FONT_EXTENSIONS = {".woff", ".woff2", ".ttf", ".eot", ".otf"}
DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar"}
STYLE_EXTENSIONS = {".css"}
SCRIPT_EXTENSIONS = {".js", ".mjs"}

ALL_RESOURCE_EXTENSIONS = (
    IMAGE_EXTENSIONS | FONT_EXTENSIONS | DOC_EXTENSIONS |
    STYLE_EXTENSIONS | SCRIPT_EXTENSIONS
)

# ── Dicționar de căi comune (încercate automat la crawling domeniu) ──
COMMON_PATHS = [
    "/",
    "/index",
    "/index.html",
    "/home",
    "/about",
    "/about-us",
    "/contact",
    "/profile",
    "/login",
    "/register",
    "/admin",
    "/sitemap.xml",
    "/robots.txt",
    "/files",
    "/documents",
    "/downloads",
    "/blog",
    "/news",
    "/api",
    "/rss",
    "/feed",
    "/faq",
    "/help",
    "/support",
    "/privacy",
    "/terms",
    "/services",
    "/products",
    "/gallery",
    "/media",
    "/search",
    "/404",
]

# ── Subdirectoare în snapshot ─────────────────────────────────────────
PAGES_SUBDIR = "pages"
ASSETS_SUBDIR = "assets"
MANIFEST_FILE = "manifest.json"
