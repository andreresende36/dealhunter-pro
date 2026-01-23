#!/bin/bash
# Script para iniciar o stack de monitoramento RQ
# Uso: ./scripts/start_monitoring.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🔍 DealHunter Pro - Iniciando Stack de Monitoramento"
echo "=================================================="
echo ""

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Função para verificar se Redis está online
check_redis() {
    echo -n "Verificando conexão com Redis... "
    if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FALHOU${NC}"
        echo ""
        echo "⚠️  Redis não está rodando ou não está acessível em localhost:6379"
        echo "   Inicie o Redis primeiro:"
        echo "   - docker-compose up -d redis"
        echo "   - ou: redis-server"
        return 1
    fi
}

# Função para verificar se Docker está rodando
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker não está rodando${NC}"
        exit 1
    fi
}

# Função para criar rede se não existir
create_network() {
    if ! docker network inspect dealhunter-network > /dev/null 2>&1; then
        echo "Criando rede Docker 'dealhunter-network'..."
        docker network create dealhunter-network
    fi
}

# Função para validar arquivos de configuração
validate_configs() {
    echo -n "Validando arquivos de configuração... "
    
    local errors=0
    
    if [ ! -f "monitoring/prometheus.yml" ]; then
        echo -e "${RED}❌ monitoring/prometheus.yml não encontrado${NC}"
        errors=$((errors + 1))
    fi
    
    if [ ! -f "monitoring/alerts.yml" ]; then
        echo -e "${RED}❌ monitoring/alerts.yml não encontrado${NC}"
        errors=$((errors + 1))
    fi
    
    if [ ! -f "monitoring/grafana/dashboards/rq-dashboard.json" ]; then
        echo -e "${RED}❌ monitoring/grafana/dashboards/rq-dashboard.json não encontrado${NC}"
        errors=$((errors + 1))
    fi
    
    if [ $errors -eq 0 ]; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ $errors erro(s) encontrado(s)${NC}"
        return 1
    fi
}

# Verificações iniciais
check_docker
check_redis || exit 1
create_network
validate_configs || exit 1

echo ""
echo "🚀 Iniciando containers de monitoramento..."
echo ""

# Inicia o stack de monitoramento
docker-compose -f docker-compose.monitoring.yml up -d

echo ""
echo "⏳ Aguardando serviços iniciarem..."
sleep 5

# Verifica saúde dos serviços
echo ""
echo "🔍 Verificando saúde dos serviços..."

check_service_health() {
    local service=$1
    local port=$2
    local name=$3
    
    echo -n "  $name (porta $port)... "
    if timeout 5 bash -c "cat < /dev/null > /dev/tcp/localhost/$port" 2>/dev/null; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${YELLOW}⏳ Aguardando...${NC}"
        return 1
    fi
}

# Aguarda serviços ficarem prontos
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    all_ready=true
    
    check_service_health "rq-exporter" "9726" "RQ Exporter" || all_ready=false
    check_service_health "prometheus" "9090" "Prometheus" || all_ready=false
    check_service_health "grafana" "3000" "Grafana" || all_ready=false
    
    if [ "$all_ready" = true ]; then
        break
    fi
    
    attempt=$((attempt + 1))
    sleep 2
done

echo ""
echo "=================================================="
echo -e "${GREEN}✅ Stack de Monitoramento Iniciado!${NC}"
echo "=================================================="
echo ""
echo "📊 Acesse os serviços:"
echo ""
echo "  🔹 RQ Exporter:    http://localhost:9726/metrics"
echo "  🔹 Prometheus:     http://localhost:9090"
echo "  🔹 Grafana:        http://localhost:3000"
echo ""
echo "📝 Credenciais do Grafana:"
echo "   Usuário: admin"
echo "   Senha:   admin (altere no primeiro login!)"
echo ""
echo "📈 Dashboard RQ:"
echo "   Após fazer login no Grafana, o dashboard 'RQ Queue Monitoring'"
echo "   estará disponível automaticamente."
echo ""
echo "🛑 Para parar o stack:"
echo "   ./scripts/stop_monitoring.sh"
echo ""
