# Sistema de Enriquecimento Assíncrono de Ofertas

Este documento descreve como usar o sistema de enriquecimento assíncrono de ofertas implementado com RQ (Redis Queue).

## Visão Geral

O sistema permite enriquecer ofertas coletadas durante o scraping inicial com dados adicionais:
- `old_fraction` e `old_cents` (convertidos em `old_price_cents`)
- `discount_pct` (porcentagem de desconto)
- `affiliate_link` (link de afiliado)
- `affiliation_id` (ID de afiliação)

## Arquitetura

```
Scraping Inicial → Salva no BD → Enfileira Jobs → Workers Processam → Atualiza BD
```

## Pré-requisitos

1. **Redis**: Instale e inicie o Redis
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   sudo systemctl start redis

   # macOS (com Homebrew)
   brew install redis
   brew services start redis

   # Docker
   docker run -d -p 6379:6379 redis:latest
   ```

2. **Dependências Python**: Instale as dependências
   ```bash
   pip install -r app/requirements.txt
   ```

## Configuração

Adicione as seguintes variáveis de ambiente no arquivo `.env`:

```env
# Redis
REDIS_URL=redis://localhost:6379/0

# Configurações de Enriquecimento (opcionais)
ENRICHMENT_QUEUE_NAME=enrichment
ENRICHMENT_WORKER_CONCURRENCY=3
ENRICHMENT_REQUEST_DELAY_S=0.5
ENRICHMENT_JOB_TIMEOUT=10m
```

## Uso

### 1. Iniciar o Worker

O worker processa os jobs de enriquecimento enfileirados:

```bash
# A partir do diretório app/
python -m workers.enrichment_worker
```

Ou:

```bash
cd app
python workers/enrichment_worker.py
```

### 2. Iniciar o Dashboard (Opcional)

O RQ Dashboard permite monitorar jobs em tempo real:

```bash
# A partir do diretório app/
python -m workers.start_dashboard
```

Ou use o comando direto:

```bash
rq-dashboard --redis-url redis://localhost:6379/0 --port 9181
```

Acesse o dashboard em: http://localhost:9181

### 3. Executar Scraping

O scraping inicial automaticamente enfileira jobs de enriquecimento após salvar as ofertas:

```bash
# A partir do diretório app/
python main.py
```

## Fluxo de Execução

1. **Scraping Inicial**: Coleta ofertas da Central de Afiliados
2. **Salvamento**: Salva ofertas básicas no Supabase
3. **Enfileiramento**: Para cada oferta salva, cria um job RQ
4. **Processamento**: Workers processam jobs assincronamente
5. **Atualização**: Dados enriquecidos são salvos no banco

## Monitoramento

### RQ Dashboard

O dashboard mostra:
- Jobs em fila (queued)
- Jobs em processamento (started)
- Jobs completados (finished)
- Jobs falhados (failed)
- Logs e erros
- Estatísticas de performance

### Logs

Os logs são exibidos no console e incluem:
- `[queue]`: Operações de fila
- `[enrichment_job]`: Processamento de jobs
- `[enrichment]`: Extração de dados
- `[worker]`: Status do worker

## Configuração Avançada

### Ajustar Concorrência

Para processar mais jobs simultaneamente, ajuste `ENRICHMENT_WORKER_CONCURRENCY`:

```env
ENRICHMENT_WORKER_CONCURRENCY=5
```

**Nota**: A concorrência real depende de quantos workers você inicia. Cada worker processa um job por vez.

### Ajustar Delay entre Requisições

Para evitar rate limiting, ajuste `ENRICHMENT_REQUEST_DELAY_S`:

```env
ENRICHMENT_REQUEST_DELAY_S=1.0  # 1 segundo entre requisições
```

### Timeout de Jobs

Ajuste o timeout para jobs que demoram mais:

```env
ENRICHMENT_JOB_TIMEOUT=15m  # 15 minutos
```

## Múltiplos Workers

Para processar mais jobs em paralelo, inicie múltiplos workers em terminais diferentes:

```bash
# Terminal 1
python -m workers.enrichment_worker

# Terminal 2
python -m workers.enrichment_worker

# Terminal 3
python -m workers.enrichment_worker
```

## Produção

Para produção, use um gerenciador de processos como `supervisor` ou `systemd`:

### Supervisor

Crie `/etc/supervisor/conf.d/enrichment_worker.conf`:

```ini
[program:enrichment_worker]
command=/path/to/venv/bin/python -m workers.enrichment_worker
directory=/path/to/app
autostart=true
autorestart=true
stderr_logfile=/var/log/enrichment_worker.err.log
stdout_logfile=/var/log/enrichment_worker.out.log
```

### Systemd

Crie `/etc/systemd/system/enrichment-worker.service`:

```ini
[Unit]
Description=Enrichment Worker
After=network.target redis.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/app
ExecStart=/path/to/venv/bin/python -m workers.enrichment_worker
Restart=always

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### Worker não processa jobs

1. Verifique se o Redis está rodando: `redis-cli ping`
2. Verifique se há jobs na fila no dashboard
3. Verifique os logs do worker

### Jobs falhando

1. Verifique os logs do worker para erros específicos
2. Verifique se o Supabase está acessível
3. Verifique se as URLs das ofertas são válidas
4. Aumente o timeout se jobs estão expirando

### Redis connection error

1. Verifique se `REDIS_URL` está correto no `.env`
2. Verifique se o Redis está acessível na URL configurada
3. Teste a conexão: `redis-cli -u redis://localhost:6379/0 ping`

## Estrutura de Arquivos

```
app/
├── queues/
│   ├── __init__.py
│   ├── enrichment_queue.py      # Configuração RQ e enfileiramento
│   └── enrichment_jobs.py        # Jobs RQ
├── services/
│   └── enrichment_service.py    # Lógica de enriquecimento
├── workers/
│   ├── __init__.py
│   ├── enrichment_worker.py      # Worker RQ
│   └── start_dashboard.py       # Script do dashboard
└── database/
    └── repositories.py           # Métodos de atualização
```

## API

### Enfileirar Job Manualmente

```python
from queues import enqueue_enrichment_job
from config import get_config

config = get_config()
job_id = enqueue_enrichment_job(
    offer_id="uuid-da-oferta",
    url="https://produto.mercadolivre.com.br/MLB-123456789",
    current_price_cents=99900,
    config=config.enrichment,
)
```

### Buscar Ofertas que Precisam Enriquecimento

```python
from database import DatabaseService, get_session, init_db
from config import get_config

config = get_config()
init_db(config.database)

async for client in get_session():
    db_service = DatabaseService(client)
    offers = await db_service.offers.get_offers_needing_enrichment(
        limit=100,
        missing_old_price=True,
        missing_discount=True,
        missing_affiliate_link=True,
    )
```

## Notas

- Os dados básicos são salvos primeiro, mesmo que o enriquecimento falhe
- Jobs falhados podem ser reprocessados manualmente
- O sistema é resiliente: falhas em um job não afetam outros
- O enriquecimento é feito de forma assíncrona, não bloqueando o scraping inicial
