# 📖 Exemplos de Uso - DealHunter Pro

Este documento contém exemplos práticos de como usar o DealHunter Pro após a refatoração.

## 🚀 Executando o Projeto

### Modo Local (Estrutura Nova)

```bash
# 1. Instale dependências
cd app
pip install -r requirements.txt

# 2. Configure variáveis de ambiente
cp .env.development .env
# Edite .env com suas credenciais

# 3. Execute o scraping
python src/main.py

# 4. Em outro terminal, inicie os workers
python -m adapters.workers.enrichment_worker

# 5. (Opcional) Inicie o dashboard RQ
python -m adapters.workers.start_dashboard
# Acesse: http://localhost:9181
```

## 💻 Exemplos de Código

### 1. Usando o ScrapeService

```python
"""Exemplo de uso do ScrapeService."""

from __future__ import annotations

import asyncio
from shared.config.settings import get_config
from core.use_cases.scrape_service import ScrapeService

async def exemplo_scraping():
    """Exemplo de execução de scraping."""
    # Carrega configuração
    config = get_config()
    
    # Cria serviço
    service = ScrapeService(config)
    
    # Executa scraping
    result = await service.run_scrape()
    
    # Exibe resultados
    print(f"Coletadas: {result['metrics']['collected_count']}")
    print(f"Filtradas: {result['metrics']['filtered_count']}")
    
    # Imprime ofertas
    service.print_offers(result["shown_offers"])

if __name__ == "__main__":
    asyncio.run(exemplo_scraping())
```

### 2. Usando o EnrichmentService

```python
"""Exemplo de enriquecimento de oferta."""

from __future__ import annotations

import asyncio
from core.use_cases.enrichment_service import enrich_offer

async def exemplo_enriquecimento():
    """Exemplo de enriquecimento de uma oferta."""
    url = "https://www.mercadolivre.com.br/produto/MLB123456"
    price_cents = 9999
    
    result = await enrich_offer(
        url=url,
        current_price_cents=price_cents,
        use_browser_pool=True  # Usa pool de browsers (mais rápido)
    )
    
    if result:
        print(f"Preço antigo: {result.old_price_cents}")
        print(f"Desconto: {result.discount_pct}%")
        print(f"Link afiliado: {result.affiliate_link}")

if __name__ == "__main__":
    asyncio.run(exemplo_enriquecimento())
```

### 3. Usando o OfferFilter

```python
"""Exemplo de filtragem de ofertas."""

from __future__ import annotations

from shared.config.settings import ScrapeConfig, get_config
from core.use_cases.offer_filter import OfferFilter
from core.domain import ScrapedOffer

def exemplo_filtro():
    """Exemplo de filtragem de ofertas."""
    # Obtém configuração
    config = get_config()
    
    # Cria filtro
    filter_service = OfferFilter(config.scrape)
    
    # Lista de ofertas de exemplo
    ofertas = [
        ScrapedOffer(
            marketplace="ML",
            external_id="MLB123",
            title="Produto 1",
            url="https://...",
            image_url=None,
            price_cents=5000,
            old_price_cents=10000,
            discount_pct=50,
            commission_pct=10,
            affiliate_link=None,
            affiliation_id=None,
        ),
        # ... mais ofertas
    ]
    
    # Filtra ofertas
    filtradas = filter_service.filter_offers(ofertas)
    
    print(f"Total: {len(ofertas)}")
    print(f"Filtradas: {len(filtradas)}")
    
    return filtradas

if __name__ == "__main__":
    exemplo_filtro()
```

### 4. Usando o DatabaseService

```python
"""Exemplo de uso do DatabaseService."""

from __future__ import annotations

import asyncio
from shared.config.settings import get_config
from adapters.database import DatabaseService, get_session, init_db

async def exemplo_database():
    """Exemplo de operações com banco de dados."""
    config = get_config()
    
    # Inicializa banco
    init_db(config.database)
    
    # Obtém sessão
    async for client in get_session():
        db_service = DatabaseService(client)
        
        # Busca ofertas que precisam de enriquecimento
        ofertas = await db_service.offers.get_offers_needing_enrichment(
            limit=10,
            missing_old_price=True,
            missing_discount=True,
        )
        
        print(f"Encontradas {len(ofertas)} ofertas que precisam enriquecimento")
        
        # Atualiza uma oferta
        if ofertas:
            oferta = ofertas[0]
            atualizada = await db_service.offers.update_offer_enrichment(
                offer_id=oferta["id"],
                old_price_cents=9999,
                discount_pct=50,
            )
            print(f"Oferta {atualizada['id']} atualizada")

if __name__ == "__main__":
    asyncio.run(exemplo_database())
```

### 5. Usando Scrapers Diretamente

```python
"""Exemplo de uso direto dos scrapers."""

from __future__ import annotations

import asyncio
from shared.config.settings import get_config
from adapters.external import scrape_affiliate_hub

async def exemplo_scraper_direto():
    """Exemplo de uso direto do scraper."""
    config = get_config()
    
    # Executa scraping diretamente
    ofertas = await scrape_affiliate_hub(
        ml_config=config.ml,
        affiliate_config=config.affiliate,
        max_scrolls=4,
        scroll_delay_s=0.45,
        debug=False,
    )
    
    print(f"Coletadas {len(ofertas)} ofertas")
    
    for oferta in ofertas[:5]:  # Primeiras 5
        print(f"- {oferta.title}: R$ {oferta.price_cents / 100:.2f}")

if __name__ == "__main__":
    asyncio.run(exemplo_scraper_direto())
```

### 6. Usando Constantes

```python
"""Exemplo de uso de constantes."""

from shared.constants import (
    TIMEOUT_SELECTOR,
    TIMEOUT_PAGE_LOAD,
    SCROLL_PIXELS,
    DEFAULT_USER_AGENT,
)

def exemplo_constantes():
    """Exemplo de uso de constantes."""
    print(f"Timeout para seletores: {TIMEOUT_SELECTOR}ms")
    print(f"Timeout para carregamento: {TIMEOUT_PAGE_LOAD}ms")
    print(f"Pixels por scroll: {SCROLL_PIXELS}")
    print(f"User Agent padrão: {DEFAULT_USER_AGENT}")

if __name__ == "__main__":
    exemplo_constantes()
```

### 7. Usando Utilitários

```python
"""Exemplo de uso de utilitários."""

from shared.utils.format import format_brl, format_pct
from shared.utils.logging import log
from shared.utils.price import price_to_cents, calc_discount

def exemplo_utilitarios():
    """Exemplo de uso de utilitários."""
    # Formatação
    preco = format_brl(12345)  # R$ 123,45
    desconto = format_pct(50.5)  # 50,5%
    
    log(f"Preço: {preco}")
    log(f"Desconto: {desconto}")
    
    # Parsing de preços
    texto = "R$ 99,90"
    centavos = price_to_cents(texto)  # 9990
    
    # Cálculo de desconto
    desconto_pct = calc_discount(old_cents=10000, price_cents=5000)  # 50
    
    print(f"Centavos: {centavos}")
    print(f"Desconto calculado: {desconto_pct}%")

if __name__ == "__main__":
    exemplo_utilitarios()
```

## 🔧 Scripts Úteis

### Scripts de Debug

Os scripts estão em `scripts/`:

```bash
# Verificar configuração de ambiente
python scripts/check_env.py

# Testar conexão com banco
python scripts/test_db_connection.py

# Testar conexão com Redis
python scripts/test_redis.py

# Contar itens em JSON de debug
python scripts/count_items.py debug/items.json
```

## 📝 Notas Importantes

### Estrutura Nova vs Antiga

O projeto mantém **compatibilidade** com a estrutura antiga (`app/`), mas a estrutura nova (`src/`) é recomendada:

- **Estrutura Nova (`src/`)**: Clean Architecture, mais organizada
- **Estrutura Antiga (`app/`)**: Mantida para compatibilidade

### Imports

**Use imports da nova estrutura:**
```python
# ✅ Correto (nova estrutura)
from shared.config.settings import get_config
from core.domain import ScrapedOffer
from adapters.database import DatabaseService

# ❌ Antigo (ainda funciona, mas não recomendado)
from config import get_config
from models import ScrapedOffer
from database import DatabaseService
```

### Variáveis de Ambiente

Todas as configurações vêm de variáveis de ambiente. Veja `.env.example` para referência completa.

### Dependências

- **Produção**: `requirements.txt`
- **Desenvolvimento**: `requirements-dev.txt` (inclui pytest, etc.)

---

Para mais detalhes, consulte o [README.md](README.md) principal.
