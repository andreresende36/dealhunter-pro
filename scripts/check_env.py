#!/usr/bin/env python3
"""Script para verificar se as variáveis de ambiente estão configuradas corretamente."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Garante que estamos no diretório correto
# Este arquivo está em scripts/, então precisamos ir para o diretório pai (raiz)
ROOT_DIR = Path(__file__).parent.parent
os.chdir(ROOT_DIR)

# Adiciona o diretório src ao path
sys.path.insert(0, str(ROOT_DIR / "src"))

# Carrega variáveis de ambiente
load_dotenv()


def check_supabase_config() -> tuple[bool, list[str]]:
    """Verifica configuração do Supabase."""
    errors = []
    warnings = []

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    if not supabase_url:
        errors.append("SUPABASE_URL não está configurada")
    elif not supabase_url.startswith("https://"):
        errors.append("SUPABASE_URL deve começar com 'https://'")
    elif not ".supabase.co" in supabase_url:
        warnings.append(
            "SUPABASE_URL não parece ser uma URL válida do Supabase (deve conter '.supabase.co')"
        )

    if not supabase_key:
        errors.append("SUPABASE_SERVICE_ROLE_KEY não está configurada")
    elif len(supabase_key) < 100:
        warnings.append(
            "SUPABASE_SERVICE_ROLE_KEY parece muito curta. "
            "Certifique-se de usar a Service Role Key, não a anon key."
        )

    return len(errors) == 0, errors + warnings


def check_redis_config() -> tuple[bool, list[str]]:
    """Verifica configuração do Redis."""
    errors = []
    warnings = []

    redis_url = os.getenv("REDIS_URL", "").strip()

    if not redis_url:
        errors.append("REDIS_URL não está configurada")
    elif not redis_url.startswith("redis://"):
        errors.append("REDIS_URL deve começar com 'redis://'")

    return len(errors) == 0, errors + warnings


def check_optional_config() -> list[str]:
    """Verifica configurações opcionais."""
    warnings = []

    # Verifica se há valores padrão sendo usados
    min_discount = os.getenv("MIN_DISCOUNT_PCT", "50.0")
    if float(min_discount) >= 50.0:
        warnings.append(
            f"MIN_DISCOUNT_PCT está em {min_discount}%. Pode ser muito alto para encontrar ofertas."
        )

    max_scrolls = int(os.getenv("ML_MAX_SCROLLS", "4"))
    if max_scrolls < 4:
        warnings.append(
            f"ML_MAX_SCROLLS está em {max_scrolls}. "
            "Valores baixos podem resultar em poucas ofertas."
        )

    return warnings


def main() -> None:
    """Função principal."""
    print("=" * 60)
    print("Verificação de Configuração de Variáveis de Ambiente")
    print("=" * 60)
    print()

    # Verifica arquivo .env
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ Arquivo .env não encontrado!")
        print()
        print("📝 Para criar o arquivo:")
        print("   1. Copie o arquivo .env.development:")
        print("      cp .env.development .env")
        print("   2. Edite o arquivo .env e configure:")
        print("      - SUPABASE_URL")
        print("      - SUPABASE_SERVICE_ROLE_KEY")
        print("      - REDIS_URL")
        print()
        sys.exit(1)

    print(f"✅ Arquivo .env encontrado: {env_file.absolute()}")
    print()

    # Verifica Supabase
    print("🔍 Verificando configuração do Supabase...")
    supabase_ok, supabase_messages = check_supabase_config()

    if supabase_ok:
        print("✅ Configuração do Supabase OK")
    else:
        print("❌ Problemas encontrados na configuração do Supabase:")

    for msg in supabase_messages:
        if "não está configurada" in msg or "deve começar" in msg:
            print(f"   ❌ {msg}")
        else:
            print(f"   ⚠️  {msg}")

    print()

    # Verifica Redis
    print("🔍 Verificando configuração do Redis...")
    redis_ok, redis_messages = check_redis_config()

    if redis_ok:
        print("✅ Configuração do Redis OK")
    else:
        print("❌ Problemas encontrados na configuração do Redis:")

    for msg in redis_messages:
        print(f"   ❌ {msg}")

    print()

    # Verifica configurações opcionais
    print("🔍 Verificando configurações opcionais...")
    optional_warnings = check_optional_config()

    if optional_warnings:
        for msg in optional_warnings:
            print(f"   ⚠️  {msg}")
    else:
        print("✅ Configurações opcionais OK")

    print()

    # Testa importação de configuração
    print("🔍 Testando importação de configuração...")
    try:
        from shared.config.settings import get_config

        config = get_config()
        print("✅ Configuração importada com sucesso")

        # Mostra resumo (sem chaves sensíveis)
        supabase_url = config.database.supabase_url
        supabase_key_masked = (
            config.database.supabase_key[:20] + "..." + config.database.supabase_key[-10:]
            if config.database.supabase_key
            else "NÃO CONFIGURADA"
        )

        print(f"   Supabase URL: {supabase_url}")
        print(f"   Service Role Key: {supabase_key_masked}")
        print(f"   Redis URL: {config.enrichment.redis_url}")
        print(f"   Min Discount: {config.scrape.min_discount_pct}%")
        print(f"   Max Scrolls: {config.scrape.max_scrolls}")

    except Exception as e:
        print(f"❌ Erro ao importar configuração: {type(e).__name__}: {e}")
        print()
        print("💡 Dica: Verifique se todas as dependências estão instaladas:")
        print("   pip install -r requirements.txt")
        sys.exit(1)

    print()
    print("=" * 60)

    all_ok = supabase_ok and redis_ok

    if all_ok:
        print("✅ Todas as verificações passaram!")
        print()
        print("📚 Próximos passos:")
        print("   1. Execute as migrations: migrations/005_add_performance_indexes.sql")
        print("   2. Inicie o Redis: redis-server")
        print("   3. Inicie o worker: python -m workers.enrichment_worker")
        print("   4. Execute o scraper: python main.py")
        sys.exit(0)
    else:
        print("❌ Alguns problemas foram encontrados. Corrija antes de continuar.")
        print()
        print("💡 Como obter as credenciais do Supabase:")
        print("   1. Acesse: https://supabase.com/dashboard/project/SEU_PROJETO")
        print("   2. Settings → API")
        print("   3. Copie 'URL' para SUPABASE_URL")
        print("   4. Copie 'service_role secret' para SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)


if __name__ == "__main__":
    main()
