# 📊 Monitoramento RQ - DealHunter Pro

Sistema completo de monitoramento para filas Redis Queue (RQ) usando RQ Exporter, Prometheus e Grafana.

## 🎯 Visão Geral

Este sistema de monitoramento fornece:

- **Métricas em tempo real** de todas as filas RQ
- **Dashboards visuais** no Grafana
- **Alertas automáticos** para problemas críticos
- **Histórico de 30 dias** de métricas
- **Análise de performance** (latência, throughput, taxa de falha)

## 📋 Pré-requisitos

- Docker e Docker Compose instalados
- Redis rodando e acessível (localhost:6379 ou via Docker)
- Portas disponíveis: 9726 (RQ Exporter), 9090 (Prometheus), 3000 (Grafana)

## 🚀 Início Rápido

### 1. Iniciar o Stack de Monitoramento

```bash
# Opção 1: Usando o script (recomendado)
./scripts/start_monitoring.sh

# Opção 2: Manualmente
docker-compose -f docker-compose.monitoring.yml up -d
```

### 2. Acessar os Serviços

Após iniciar, aguarde ~30 segundos e acesse:

- **Grafana**: http://localhost:3000
  - Usuário: `admin`
  - Senha: `admin` (altere no primeiro login!)

- **Prometheus**: http://localhost:9090

- **RQ Exporter**: http://localhost:9726/metrics

### 3. Visualizar Dashboard

1. Faça login no Grafana
2. O dashboard **"RQ Queue Monitoring"** será carregado automaticamente
3. Use o filtro **"Fila"** no topo para selecionar filas específicas

## 📊 Métricas Disponíveis

### Métricas Principais

| Métrica | Descrição | Tipo |
|---------|-----------|------|
| `rq_workers` | Número de workers ativos por fila | Gauge |
| `rq_queue_length` | Tamanho da fila (jobs pendentes) | Gauge |
| `rq_jobs` | Jobs por status (queued/started/finished/failed) | Counter |
| `rq_job_duration_seconds` | Histograma de duração de jobs | Histogram |
| `rq_finished_jobs_total` | Total de jobs finalizados com sucesso | Counter |
| `rq_failed_jobs_total` | Total de jobs que falharam | Counter |

### Painéis do Dashboard

#### Visão Geral
- **Workers Ativos por Fila**: Número atual de workers processando jobs
- **Jobs Pendentes por Fila**: Quantidade de jobs aguardando processamento
- **Taxa de Falha**: Percentual de jobs que falharam
- **Total de Jobs Processados (24h)**: Contador de jobs finalizados nas últimas 24h
- **Total de Jobs Falhados (24h)**: Contador de jobs que falharam nas últimas 24h
- **Latência Média P50**: Tempo médio de processamento (percentil 50)
- **Total de Workers Ativos**: Soma de todos os workers ativos

#### Gráficos Temporais
- **Jobs Pendentes ao Longo do Tempo**: Evolução do tamanho das filas
- **Throughput (Jobs por Segundo)**: Taxa de processamento
- **Latência de Processamento (P50/P95/P99)**: Distribuição de tempos de processamento
- **Jobs Processados (Últimas 24h)**: Histórico de jobs finalizados vs falhados

## 🚨 Alertas Configurados

O Prometheus está configurado com as seguintes regras de alerta:

### Alertas de Fila

- **RQQueueTooManyPendingJobs** (Warning)
  - Condição: Fila com >100 jobs pendentes por 5 minutos
  - Severidade: Warning

- **RQQueueCriticalPendingJobs** (Critical)
  - Condição: Fila com >500 jobs pendentes por 2 minutos
  - Severidade: Critical

### Alertas de Workers

- **RQNoWorkersActive** (Critical)
  - Condição: Nenhum worker ativo por 2 minutos
  - Severidade: Critical

- **RQTooFewWorkers** (Warning)
  - Condição: Menos de 2 workers ativos por 5 minutos
  - Severidade: Warning

### Alertas de Performance

- **RQHighFailureRate** (Warning)
  - Condição: Taxa de falha >10% por 5 minutos
  - Severidade: Warning

- **RQCriticalFailureRate** (Critical)
  - Condição: Taxa de falha >25% por 2 minutos
  - Severidade: Critical

- **RQHighProcessingTime** (Warning)
  - Condição: Latência P95 >300 segundos por 10 minutos
  - Severidade: Warning

- **RQLowThroughput** (Warning)
  - Condição: Throughput <0.1 jobs/segundo por 10 minutos
  - Severidade: Warning

## 🔧 Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com:

```bash
# Redis
REDIS_URL=redis://localhost:6379/0

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin  # Altere em produção!
```

### Personalizar Alertas

Edite `monitoring/alerts.yml` para ajustar thresholds ou adicionar novos alertas.

### Personalizar Dashboard

1. Acesse o Grafana
2. Vá em **Dashboards** → **RQ Queue Monitoring**
3. Clique em **Edit** (ícone de lápis)
4. Faça suas alterações
5. Clique em **Save**

Para exportar o dashboard atualizado:

```bash
# O dashboard é salvo automaticamente em:
monitoring/grafana/dashboards/rq-dashboard.json
```

## 📈 Adicionar Métricas Customizadas

### Exemplo: Métrica Customizada na Aplicação

```python
from prometheus_client import Counter, Histogram, Gauge

# Contador de jobs processados por tipo
jobs_processed = Counter(
    'dealhunter_jobs_processed_total',
    'Total de jobs processados',
    ['job_type', 'status']
)

# Histograma de tempo de scraping
scraping_duration = Histogram(
    'dealhunter_scraping_duration_seconds',
    'Duração do scraping',
    ['source']
)

# Gauge de ofertas coletadas
offers_collected = Gauge(
    'dealhunter_offers_collected',
    'Número de ofertas coletadas',
    ['source']
)

# Uso no código
jobs_processed.labels(job_type='enrichment', status='success').inc()
scraping_duration.labels(source='ml').observe(12.5)
offers_collected.labels(source='ml').set(150)
```

### Expor Métricas via HTTP

```python
from prometheus_client import start_http_server

# Inicia servidor HTTP na porta 8000
start_http_server(8000)
```

Adicione ao `prometheus.yml`:

```yaml
- job_name: 'dealhunter-app'
  static_configs:
    - targets: ['app:8000']
```

## 🛠️ Manutenção

### Parar o Stack

```bash
./scripts/stop_monitoring.sh
```

### Ver Logs

```bash
# Todos os serviços
docker-compose -f docker-compose.monitoring.yml logs -f

# Serviço específico
docker-compose -f docker-compose.monitoring.yml logs -f rq-exporter
docker-compose -f docker-compose.monitoring.yml logs -f prometheus
docker-compose -f docker-compose.monitoring.yml logs -f grafana
```

### Backup de Configurações

```bash
# Backup do Grafana (dashboards, datasources, etc)
./scripts/backup_grafana_config.sh

# Backup do Prometheus (dados históricos)
docker run --rm \
  -v dealhunter-pro_prometheus_data:/data:ro \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/prometheus_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
```

### Restaurar Backup

```bash
# Restaurar Grafana
docker run --rm \
  -v dealhunter-pro_grafana_data:/data \
  -v $(pwd)/monitoring/backups:/backup \
  alpine tar xzf /backup/grafana_backup_YYYYMMDD_HHMMSS.tar.gz -C /data

# Reiniciar Grafana
docker-compose -f docker-compose.monitoring.yml restart grafana
```

### Limpar Dados Antigos

```bash
# Remover volumes (apaga TODOS os dados históricos!)
docker-compose -f docker-compose.monitoring.yml down -v
```

## 🔍 Troubleshooting

### RQ Exporter não está coletando métricas

1. Verifique se o Redis está acessível:
   ```bash
   redis-cli -h localhost -p 6379 ping
   ```

2. Verifique logs do RQ Exporter:
   ```bash
   docker-compose -f docker-compose.monitoring.yml logs rq-exporter
   ```

3. Verifique se há filas no Redis:
   ```bash
   redis-cli -h localhost -p 6379 KEYS "rq:queue:*"
   ```

### Prometheus não está scrapando

1. Verifique se o RQ Exporter está respondendo:
   ```bash
   curl http://localhost:9726/metrics
   ```

2. Verifique targets no Prometheus:
   - Acesse http://localhost:9090/targets
   - Verifique se `rq-exporter` está com status "UP"

### Grafana não mostra dados

1. Verifique se o datasource está configurado:
   - Acesse http://localhost:3000/connections/datasources
   - Verifique se "Prometheus" está configurado e testado

2. Verifique se há métricas no Prometheus:
   - Acesse http://localhost:9090
   - Digite `rq_queue_length` e clique em "Execute"
   - Deve retornar resultados

3. Verifique o intervalo de tempo do dashboard:
   - No Grafana, verifique se o intervalo de tempo está correto (últimas 6h por padrão)

### Dashboard não aparece automaticamente

1. Verifique se o arquivo está no lugar correto:
   ```bash
   ls -la monitoring/grafana/dashboards/rq-dashboard.json
   ```

2. Reinicie o Grafana:
   ```bash
   docker-compose -f docker-compose.monitoring.yml restart grafana
   ```

3. Importe manualmente:
   - Acesse http://localhost:3000/dashboard/import
   - Faça upload do arquivo `monitoring/grafana/dashboards/rq-dashboard.json`

## 📚 Recursos Adicionais

### Documentação Oficial

- [RQ Exporter](https://github.com/erikvanbrakel/rq-exporter)
- [Prometheus](https://prometheus.io/docs/)
- [Grafana](https://grafana.com/docs/)

### Queries Prometheus Úteis

```promql
# Taxa de jobs por segundo (últimos 5 minutos)
sum(rate(rq_finished_jobs_total[5m])) by (queue)

# Taxa de falha
sum(rate(rq_failed_jobs_total[5m])) by (queue) 
/ 
sum(rate(rq_finished_jobs_total[5m]) + rate(rq_failed_jobs_total[5m])) by (queue)

# Latência P95
histogram_quantile(0.95, sum(rate(rq_job_duration_seconds_bucket[5m])) by (le, queue))

# Jobs pendentes por fila
sum(rq_queue_length) by (queue)

# Workers ativos por fila
sum(rq_workers) by (queue)
```

## 🔐 Segurança em Produção

### Grafana

1. **Altere a senha padrão** imediatamente após o primeiro login
2. Configure autenticação OAuth/LDAP se necessário
3. Use HTTPS com certificado válido
4. Configure firewall para restringir acesso

### Prometheus

1. Configure autenticação básica ou OAuth
2. Use HTTPS
3. Restrinja acesso à rede interna

### RQ Exporter

1. Não exponha a porta 9726 publicamente
2. Use firewall para restringir acesso

## 📝 Changelog

### v1.0.0 (2026-01-22)
- Implementação inicial do sistema de monitoramento
- Dashboard Grafana completo
- Alertas configurados
- Scripts de inicialização e backup

## 🤝 Contribuindo

Para melhorias ou correções, abra uma issue ou pull request no repositório.

## 📄 Licença

Mesma licença do projeto principal.
