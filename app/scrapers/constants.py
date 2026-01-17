"""Constantes do scraper."""

RESOURCE_BLOCK_TYPES = {"image", "font", "media"}
TRACKER_HOST_SNIPPETS = (
    "doubleclick",
    "googletagmanager",
    "google-analytics",
    "facebook",
    "hotjar",
)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_ACCEPT_LANGUAGE = "pt-BR,pt;q=0.9,en;q=0.8"
MAX_CARDS_PER_PAGE = 300
SCROLL_PIXELS = 2400

