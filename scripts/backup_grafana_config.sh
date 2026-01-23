#!/bin/bash
# Script para fazer backup das configurações do Grafana
# Uso: ./scripts/backup_grafana_config.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

BACKUP_DIR="$PROJECT_ROOT/monitoring/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/grafana_backup_$TIMESTAMP.tar.gz"

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "💾 DealHunter Pro - Backup de Configurações do Grafana"
echo "======================================================"
echo ""

# Cria diretório de backup se não existir
mkdir -p "$BACKUP_DIR"

# Verifica se o container do Grafana está rodando
if ! docker ps | grep -q dealhunter-grafana; then
    echo -e "${YELLOW}⚠️  Container do Grafana não está rodando${NC}"
    echo "   Iniciando container temporariamente para backup..."
    docker-compose -f docker-compose.monitoring.yml up -d grafana
    sleep 5
    TEMP_START=true
else
    TEMP_START=false
fi

echo "Fazendo backup das configurações..."

# Cria backup do volume do Grafana
docker run --rm \
    -v dealhunter-pro_grafana_data:/data:ro \
    -v "$BACKUP_DIR":/backup \
    alpine tar czf /backup/grafana_backup_$TIMESTAMP.tar.gz -C /data .

# Para o container temporário se foi iniciado por este script
if [ "$TEMP_START" = true ]; then
    docker-compose -f docker-compose.monitoring.yml stop grafana
fi

echo ""
echo -e "${GREEN}✅ Backup criado com sucesso!${NC}"
echo ""
echo "📁 Arquivo: $BACKUP_FILE"
echo ""
echo "💡 Para restaurar o backup:"
echo "   docker run --rm \\"
echo "     -v dealhunter-pro_grafana_data:/data \\"
echo "     -v $BACKUP_DIR:/backup \\"
echo "     alpine tar xzf /backup/grafana_backup_$TIMESTAMP.tar.gz -C /data"
echo ""
