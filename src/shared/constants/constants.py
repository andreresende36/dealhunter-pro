"""Constantes do scraper."""

# Tipos de recursos a bloquear
RESOURCE_BLOCK_TYPES = {"image", "font", "media"}

# Hosts de trackers a bloquear
TRACKER_HOST_SNIPPETS = (
    "doubleclick",
    "googletagmanager",
    "google-analytics",
    "facebook",
    "hotjar",
)

# User Agent padrão
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Accept Language padrão
DEFAULT_ACCEPT_LANGUAGE = "pt-BR,pt;q=0.9,en;q=0.8"

# Limites e configurações de scraping
MAX_CARDS_PER_PAGE = 300
SCROLL_PIXELS = 2400

# Timeouts (em milissegundos)
TIMEOUT_SHORT = 500  # Para verificações rápidas (cookies, erros)
TIMEOUT_MEDIUM = 1000  # Para cliques e ações simples
TIMEOUT_SELECTOR = 10000  # Para esperar seletores aparecerem
TIMEOUT_PAGE_LOAD = 30000  # Para carregamento completo de página
TIMEOUT_NETWORK_IDLE = 5000  # Para networkidle state

# Delays (em milissegundos)
DELAY_INITIAL_RENDER = 2000  # Aguarda renderização inicial
DELAY_AFTER_SCROLL = 1500  # Aguarda após scroll
DELAY_BETWEEN_ACTIONS = 3000  # Delay entre ações principais

# Percentuais e limites
SCROLL_DROP_THRESHOLD_PCT = 30  # Percentual de queda aceitável no scroll
SCROLL_DELAY_MULTIPLIER = 0.5  # Multiplicador para delay de scroll (50%)
FINAL_WAIT_MULTIPLIER = 3  # Multiplicador para espera final após scrolls

# Limites de retry e processamento
DEFAULT_QUERY_LIMIT = 100  # Limite padrão para queries de banco
