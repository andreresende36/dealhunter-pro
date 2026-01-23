#!/bin/bash
# Script para parar o stack de monitoramento RQ
# Uso: ./scripts/stop_monitoring.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🛑 DealHunter Pro - Parando Stack de Monitoramento"
echo "=================================================="
echo ""

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Parando containers..."
docker-compose -f docker-compose.monitoring.yml down

echo ""
echo -e "${GREEN}✅ Stack de monitoramento parado${NC}"
echo ""
echo "💡 Nota: Os volumes de dados (Prometheus e Grafana) foram preservados."
echo "   Para remover também os volumes, use:"
echo "   docker-compose -f docker-compose.monitoring.yml down -v"
echo ""
