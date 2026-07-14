"""
Configurari globale ale aplicatiei 
-constante
-cai comune
-extensii de fisiere 
-user-agent 
"""
import os 
#Directorul implicit de output 
OUTPUT_DIR =os.path.join(os.getcwd(),"snapshots")

#User-Agent realist (ca sa nu ne blocheze serverele)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; win64; x64)"
    "Chrome/125.0.0.0 Safari/537.36" 
)

#Limite de crawling
MAX_PAGES = 100 #nr maxim de pagini de domeniu
MAX_DEPTH = 5 #adancimea maxima de la pagina seed
MAX_CONCURRENT = 5 #descarcari paralele simultane
REQUEST_DELAY = 0.5 #secunde intre cereri
PAGE_TIMEOUT_MS = 30000 #timeout randare pagina (ms)
EXTRA_WAIT_MS = 2000 #astepare suplimentara 


#Extensii de resure pe care le descarcam
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

