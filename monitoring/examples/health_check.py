"""
Health check endpoint para verificar saúde dos serviços.

Este módulo fornece endpoints de health check para:
- Redis
- Supabase
- RQ Workers
"""

import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import json
import redis
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Handler HTTP para health checks."""
    
    def do_GET(self):
        if self.path == '/health':
            health_status = self.check_all_services()
            status_code = 200 if health_status['healthy'] else 503
            
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(health_status, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def check_all_services(self) -> dict:
        """Verifica saúde de todos os serviços."""
        checks = {
            'redis': self.check_redis(),
            'supabase': self.check_supabase(),
            'rq_workers': self.check_rq_workers(),
        }
        
        healthy = all(check['status'] == 'healthy' for check in checks.values())
        
        return {
            'healthy': healthy,
            'timestamp': asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else None,
            'checks': checks
        }
    
    def check_redis(self) -> dict:
        """Verifica conexão com Redis."""
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            r = redis.from_url(redis_url)
            r.ping()
            return {
                'status': 'healthy',
                'message': 'Redis está respondendo'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Erro ao conectar ao Redis: {str(e)}'
            }
    
    def check_supabase(self) -> dict:
        """Verifica conexão com Supabase."""
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            
            if not supabase_url or not supabase_key:
                return {
                    'status': 'unhealthy',
                    'message': 'Variáveis de ambiente do Supabase não configuradas'
                }
            
            supabase: Client = create_client(supabase_url, supabase_key)
            # Testa conexão fazendo uma query simples
            supabase.table('scrape_runs').select('id').limit(1).execute()
            
            return {
                'status': 'healthy',
                'message': 'Supabase está respondendo'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Erro ao conectar ao Supabase: {str(e)}'
            }
    
    def check_rq_workers(self) -> dict:
        """Verifica se há workers RQ ativos."""
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            r = redis.from_url(redis_url)
            
            # Verifica workers registrados no Redis
            workers = r.smembers('rq:workers')
            worker_count = len(workers)
            
            if worker_count > 0:
                return {
                    'status': 'healthy',
                    'message': f'{worker_count} worker(s) ativo(s)',
                    'worker_count': worker_count
                }
            else:
                return {
                    'status': 'unhealthy',
                    'message': 'Nenhum worker RQ ativo',
                    'worker_count': 0
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Erro ao verificar workers: {str(e)}'
            }
    
    def log_message(self, format, *args):
        # Suprime logs do servidor HTTP
        pass


def start_health_check_server(port: int = 8080):
    """
    Inicia servidor HTTP para health checks.
    
    Args:
        port: Porta onde o servidor será iniciado (padrão: 8080)
    """
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"🏥 Health check server iniciado em http://localhost:{port}/health")
    server.serve_forever()


def start_health_check_thread(port: int = 8080):
    """
    Inicia servidor de health check em thread separada.
    
    Args:
        port: Porta onde o servidor será iniciado
    """
    thread = Thread(target=start_health_check_server, args=(port,), daemon=True)
    thread.start()
    return thread


# Exemplo de uso:
if __name__ == '__main__':
    start_health_check_server(port=8080)
