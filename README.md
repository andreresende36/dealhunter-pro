# 🛒 DealHunter Pro

Sistema inteligente de web scraping e enriquecimento assíncrono de ofertas do Mercado Livre com alta performance e escalabilidade.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Funcionalidades](#funcionalidades)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [Performance e Otimizações](#performance-e-otimizações)
- [Monitoramento](#monitoramento)
- [Testes](#testes)
- [Deploy](#deploy)
- [Troubleshooting](#troubleshooting)

## 🎯 Visão Geral

DealHunter Pro é uma plataforma de scraping otimizada que:

- 🚀 **Coleta ofertas** do Hub de Afiliados do Mercado Livre
- 🎯 **Filtra** produtos por desconto mínimo configurável
- ⚡ **Enriquece** ofertas assincronamente com dados completos
- 💾 **Armazena** tudo em banco Supabase para análise
- 📊 **Monitora** performance com Prometheus e Grafana
- 🔧 **Escala** horizontalmente com múltiplos workers

## 🏗️ Arquitetura

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│   Scraper   │────▶│   Filter     │────▶│   Database    │
│ (Playwright)│     │ (Desconto)   │     │  (Supabase)   │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                                                  ▼
                                         ┌────────────────┐
                                         │  Redis Queue   │
                                         │   (RQ Jobs)    │
                                         └────────┬───────┘
                                                  │
                        ┌─────────────────────────┼─────────────────────────┐
                        ▼                         ▼                         ▼
                  ┌──────────┐             ┌──────────┐             ┌──────────┐
                  │ Worker 1 │             │ Worker 2 │      ...    │ Worker N │
                  │(Browser  │             │(Browser  │             │(Browser  │
                  │  Pool)   │             │  Pool)   │             │  Pool)   │
                  └──────────┘             └──────────┘             └──────────┘
                        │                         │                         │
                        └─────────────────────────┴─────────────────────────┘
                                                  │
                                                  ▼
                                         ┌────────────────┐
                                         │  Update DB     │
                                         │ (Enrichment)   │
                                         └────────────────┘
```

### Componentes Principais

1. **Scraper**: Coleta inicial de ofertas usando Playwright
2. **Filter**: Aplica regras de negócio (desconto mínimo)
3. **Database**: Persistência em Supabase com histórico
4. **Queue**: Enfileiramento em lote com Redis
5. **Workers**: Processamento paralelo com browser pool
6. **Monitoring**: Métricas Prometheus e dashboards Grafana

## ✨ Funcionalidades

### Core Features

- ✅ Scraping com scroll infinito inteligente
- ✅ Extração robusta de preços e descontos
- ✅ Browser pool para performance (5-10x mais rápido)
- ✅ Enfileiramento em lote com Redis pipeline
- ✅ Retry automático com backoff exponencial
- ✅ Rate limiting para evitar bloqueios
- ✅ Circuit breaker para proteção contra falhas
- ✅ Health checks e graceful shutdown
- ✅ Conexão thread-safe ao banco de dados

### Otimizações de Performance

| Otimização      | Ganho Estimado | Descrição                            |
| --------------- | -------------- | ------------------------------------ |
| Browser Pool    | **10x**        | Reutilização de contextos Playwright |
| Batch Enqueuing | **20x**        | Redis pipeline para enfileiramento   |
| Índices DB      | **5x**         | Queries otimizadas com índices       |
| Async/Sync Fix  | **30%**        | Event loop único e eficiente         |
| Thread-safe DB  | N/A            | Evita race conditions                |

## 📦 Requisitos

- Python 3.13+
- Redis 7+
- Supabase (PostgreSQL)
- Docker & Docker Compose (opcional)

## 🚀 Instalação

### Opção 1: Docker (Recomendado)

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/dealhunter-pro.git
cd dealhunter-pro

# Configure o .env
cp .env.development .env
# Edite .env com suas credenciais

# Inicie todos os serviços
docker-compose up -d

# Verifique os logs
docker-compose logs -f
```

### Opção 2: Instalação Local

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/dealhunter-pro.git
cd dealhunter-pro

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale dependências de produção
pip install -r requirements.txt

# Ou instale dependências de desenvolvimento (inclui testes)
pip install -r requirements-dev.txt

# Instale Playwright browsers
playwright install chromium

# Configure o .env
cp .env.development .env
# Edite .env com suas credenciais
```

## ⚙️ Configuração

### Variáveis de Ambiente

Copie `.env.development` para `.env` e configure:

```bash
# Ambiente
ENVIRONMENT=development  # development, staging, production

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-key-here

# Redis
REDIS_URL=redis://localhost:6379/0

# Scraping
ML_MAX_SCROLLS=4
ML_SCROLL_DELAY_S=0.45
MIN_DISCOUNT_PCT=50

# Enrichment
ENRICHMENT_WORKER_CONCURRENCY=3
ENRICHMENT_REQUEST_DELAY_S=0.5
```

### Configuração por Ambiente

O sistema suporta configurações específicas por ambiente:

- **Development**: Debug ativo, poucos workers, métricas desabilitadas
- **Staging**: Configuração intermediária para testes
- **Production**: Otimizado para máxima performance

Veja [src/shared/config/environments.py](src/shared/config/environments.py) para detalhes.

### Migrations de Banco de Dados

Execute as migrations para criar índices de performance:

```bash
# Via SQL Editor do Supabase
# 1. Acesse: https://supabase.com/dashboard/project/SEU_PROJETO
# 2. SQL Editor → New Query
# 3. Copie o conteúdo de migrations/005_add_performance_indexes.sql
# 4. Cole no editor e execute (Run)
```

## 🎮 Uso

### Modo Local

```bash
# Inicie Redis
redis-server

# Terminal 1: Execute scraping
# A partir da raiz do projeto
python src/main.py

# Terminal 2: Inicie workers
# Opção 1: Com PYTHONPATH (recomendado)
PYTHONPATH=src python -m adapters.workers.enrichment_worker

# Opção 2: Executar diretamente
python src/adapters/workers/enrichment_worker.py

# Opção 3: Exportar PYTHONPATH permanentemente (opcional)
export PYTHONPATH=src
python -m adapters.workers.enrichment_worker 

# Terminal 3: Inicie RQ Dashboard (opcional)
# Opção 1: Com PYTHONPATH (recomendado)
PYTHONPATH=src python -m adapters.workers.start_dashboard

# Opção 2: Executar diretamente
python src/adapters/workers/start_dashboard.py

# Opção 3: Exportar PYTHONPATH permanentemente (opcional)
export PYTHONPATH=src
python -m adapters.workers.start_dashboard

# Acesse: http://localhost:9181
```

### Modo Docker

```bash
# Inicie tudo
docker-compose up -d

# Execute scraping
docker-compose run --rm app python src/main.py

# Escalone workers
docker-compose up -d --scale worker=5

# Veja dashboard
open http://localhost:9181
```

### Com Monitoramento

```bash
# Inicie com Prometheus e Grafana
docker-compose --profile monitoring up -d

# Acesse:
# - RQ Dashboard: http://localhost:9181
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

## 🏎️ Performance e Otimizações

### Browser Pool

Configurável via `BROWSER_POOL_SIZE` (padrão: 3)

```python
# Uso automático no enrichment_service
from core.use_cases.enrichment_service import enrich_offer

result = await enrich_offer(
    url=url,
    use_browser_pool=True  # 10x mais rápido
)
```

### Batch Operations

Enfileiramento em lote automaticamente ativo:

```python
# Antes: 100 ofertas = 200 queries + 100 Redis commands
# Depois: 100 ofertas = 2 queries + 1 Redis pipeline
```

### Rate Limiting

Proteção automática contra bloqueios:

```python
# Configuração padrão: 10 req/min para ML
# Ajuste em src/shared/utils/rate_limiter.py
```

### Circuit Breaker

Proteção contra falhas em cascata:

- Abre após 5 falhas consecutivas
- Fecha após 2 sucessos
- Timeout de 60s

## 📊 Monitoramento

### Métricas Disponíveis

```
# Scraping
dealhunter_scrape_duration_seconds
dealhunter_offers_collected_total
dealhunter_scraping_errors_total

# Enrichment
dealhunter_enrichment_duration_seconds
dealhunter_enrichment_success_total
dealhunter_jobs_enqueued_total

# Workers
dealhunter_active_workers
dealhunter_queue_size

# Database
dealhunter_database_queries_total
dealhunter_database_query_duration_seconds

# Rate Limiting
dealhunter_rate_limit_hit_total
dealhunter_circuit_breaker_state
```

### Dashboards

Acesse Grafana em `http://localhost:3000` para visualizar:

- Performance de scraping
- Throughput de workers
- Latência de enriquecimento
- Estado de circuit breakers
- Tamanho de filas

## 🧪 Testes

```bash
# Execute todos os testes
pytest

# Com cobertura (estrutura nova)
pytest --cov=src --cov-report=html

# Com cobertura (estrutura antiga - compatibilidade)
pytest --cov=app --cov-report=html

# Apenas testes rápidos
pytest -m "not slow"

# Testes específicos
pytest tests/test_utils.py
```

## 🚢 Deploy

### Produção

```bash
# 1. Configure variáveis de produção
cp .env.production .env
# Edite com credenciais reais

# 2. Build da imagem
docker build -t dealhunter-pro:latest .

# 3. Push para registry
docker tag dealhunter-pro:latest registry.com/dealhunter-pro:latest
docker push registry.com/dealhunter-pro:latest

# 4. Deploy com docker-compose
ENVIRONMENT=production docker-compose up -d --scale worker=10
```

### Escalabilidade

**Workers**: Escale horizontalmente conforme necessário

```bash
# 10 workers paralelos
docker-compose up -d --scale worker=10

# Ou via Kubernetes
kubectl scale deployment dealhunter-worker --replicas=20
```

**Redis**: Use Redis Cluster para alta disponibilidade

**Database**: Supabase escala automaticamente

## 🔧 Troubleshooting

### Redis não conecta

```bash
# Verifique se Redis está rodando
redis-cli ping
# PONG

# Teste conexão
redis-cli -u redis://localhost:6379/0
```

### Workers não processam jobs

```bash
# Verifique logs
docker-compose logs worker

# Verifique fila
redis-cli
> LLEN "rq:queue:enrichment"

# Limpe fila
> DEL "rq:queue:enrichment"
```

### Scraping muito lento

1. Aumente `BROWSER_POOL_SIZE`
2. Reduza `ENRICHMENT_REQUEST_DELAY_S`
3. Escale workers: `docker-compose up -d --scale worker=5`

### Rate limit do ML

1. Aumente `ML_SCROLL_DELAY_S`
2. Reduza `ENRICHMENT_WORKER_CONCURRENCY`
3. Verifique métricas de rate limiting

## 📚 Documentação Adicional

- [ENRICHMENT_README.md](ENRICHMENT_README.md) - Detalhes do sistema de enriquecimento
- [FASE6_RELATORIO_FINAL.md](FASE6_RELATORIO_FINAL.md) - Relatório completo da refatoração
- [migrations/](migrations/) - Scripts de banco de dados

### Estrutura do Código

O projeto foi refatorado seguindo **Clean Architecture**:

- **`src/core/`**: Regras de negócio puras (domain + use_cases)
- **`src/adapters/`**: Integrações externas (database, external APIs, queues, workers)
- **`src/shared/`**: Recursos compartilhados (config, constants, utils)

### Exemplos de Imports

**Antes (estrutura antiga):**
```python
from config import get_config
from models import ScrapedOffer
from services import ScrapeService
```

**Depois (estrutura nova):**
```python
from shared.config.settings import get_config
from core.domain import ScrapedOffer
from core.use_cases.scrape_service import ScrapeService
```

Veja [FASE6_RELATORIO_FINAL.md](FASE6_RELATORIO_FINAL.md) para detalhes completos da refatoração.

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 📞 Suporte

- Issues: https://github.com/seu-usuario/dealhunter-pro/issues
- Email: seu-email@exemplo.com

---

**Desenvolvido com ❤️ e otimizado para performance máxima**
