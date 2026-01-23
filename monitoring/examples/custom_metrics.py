"""
Exemplo de como adicionar métricas customizadas Prometheus na aplicação.

Este arquivo demonstra como integrar métricas customizadas do Prometheus
no código Python do DealHunter Pro.
"""

from prometheus_client import Counter, Histogram, Gauge, start_http_server
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

# ============================================================================
# MÉTRICAS CUSTOMIZADAS
# ============================================================================

# Contador de jobs processados por tipo e status
jobs_processed_total = Counter(
    'dealhunter_jobs_processed_total',
    'Total de jobs processados pela aplicação',
    ['job_type', 'status']  # Labels: tipo de job e status (success/failed)
)

# Histograma de duração de scraping
scraping_duration_seconds = Histogram(
    'dealhunter_scraping_duration_seconds',
    'Duração do processo de scraping em segundos',
    ['source'],  # Label: fonte (ml, affiliate_hub, etc)
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]  # Buckets customizados
)

# Gauge de ofertas coletadas
offers_collected = Gauge(
    'dealhunter_offers_collected',
    'Número atual de ofertas coletadas',
    ['source', 'status']  # Labels: fonte e status (pending/processed)
)

# Contador de erros por tipo
errors_total = Counter(
    'dealhunter_errors_total',
    'Total de erros encontrados',
    ['error_type', 'component']  # Labels: tipo de erro e componente
)

# Histograma de tempo de enriquecimento
enrichment_duration_seconds = Histogram(
    'dealhunter_enrichment_duration_seconds',
    'Duração do processo de enriquecimento em segundos',
    ['offer_id'],
    buckets=[0.5, 1, 2, 5, 10, 30, 60]
)

# ============================================================================
# EXEMPLO DE USO
# ============================================================================

def example_scraping_metrics():
    """Exemplo de como usar métricas durante scraping."""
    source = 'ml'
    start_time = time.time()
    
    try:
        # Simula scraping
        # ... seu código de scraping aqui ...
        
        # Registra duração
        duration = time.time() - start_time
        scraping_duration_seconds.labels(source=source).observe(duration)
        
        # Incrementa contador de sucesso
        jobs_processed_total.labels(job_type='scraping', status='success').inc()
        
        # Atualiza gauge de ofertas coletadas
        offers_collected.labels(source=source, status='pending').set(150)
        
    except Exception as e:
        # Incrementa contador de falha
        jobs_processed_total.labels(job_type='scraping', status='failed').inc()
        
        # Registra erro
        errors_total.labels(error_type=type(e).__name__, component='scraper').inc()
        raise


def example_enrichment_metrics(offer_id: str):
    """Exemplo de como usar métricas durante enriquecimento."""
    start_time = time.time()
    
    try:
        # Simula enriquecimento
        # ... seu código de enriquecimento aqui ...
        
        # Registra duração
        duration = time.time() - start_time
        enrichment_duration_seconds.labels(offer_id=offer_id).observe(duration)
        
        # Incrementa contador de sucesso
        jobs_processed_total.labels(job_type='enrichment', status='success').inc()
        
        # Atualiza gauge
        offers_collected.labels(source='ml', status='processed').inc()
        
    except Exception as e:
        # Incrementa contador de falha
        jobs_processed_total.labels(job_type='enrichment', status='failed').inc()
        
        # Registra erro
        errors_total.labels(error_type=type(e).__name__, component='enricher').inc()
        raise


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

class MetricsHandler(BaseHTTPRequestHandler):
    """Handler HTTP para expor métricas Prometheus."""
    
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(generate_latest())
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suprime logs do servidor HTTP
        pass


def start_metrics_server(port: int = 8000):
    """
    Inicia servidor HTTP para expor métricas Prometheus.
    
    Args:
        port: Porta onde o servidor será iniciado (padrão: 8000)
    """
    server = HTTPServer(('0.0.0.0', port), MetricsHandler)
    print(f"📊 Servidor de métricas iniciado em http://localhost:{port}/metrics")
    print(f"🏥 Health check disponível em http://localhost:{port}/health")
    server.serve_forever()


# ============================================================================
# INTEGRAÇÃO COM ASYNCIO
# ============================================================================

import asyncio
from threading import Thread


def start_metrics_server_thread(port: int = 8000):
    """
    Inicia servidor de métricas em thread separada (compatível com asyncio).
    
    Args:
        port: Porta onde o servidor será iniciado
    """
    def run_server():
        start_metrics_server(port)
    
    thread = Thread(target=run_server, daemon=True)
    thread.start()
    return thread


# ============================================================================
# EXEMPLO DE INTEGRAÇÃO NO CÓDIGO EXISTENTE
# ============================================================================

# No seu main.py ou onde inicia a aplicação:
"""
from monitoring.examples.custom_metrics import (
    start_metrics_server_thread,
    jobs_processed_total,
    scraping_duration_seconds,
    offers_collected
)

# Inicia servidor de métricas
start_metrics_server_thread(port=8000)

# Use as métricas no seu código:
jobs_processed_total.labels(job_type='scraping', status='success').inc()
"""
