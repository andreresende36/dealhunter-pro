#!/usr/bin/env python3
"""Script para verificar se as variáveis de ambiente estão configuradas corretamente."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Garante que estamos no diretório correto
APP_DIR = Path(__file__).parent
os.chdir(APP_DIR)

# Adiciona o diretório app ao path
sys.path.insert(0, str(APP_DIR))

# Carrega variáveis de ambiente
load_dotenv()


def check_database_config() -> tuple[bool, list[str]]:
    """Verifica configuração do banco de dados."""
    errors = []
    warnings = []

    db_url = os.getenv("DATABASE_URL", "").strip()
    db_host = os.getenv("DB_HOST", "").strip()
    db_user = os.getenv("DB_USER", "").strip()
    db_password = os.getenv("DB_PASSWORD", "").strip()

    if db_url:
        # Verifica formato da URL
        if not db_url.startswith("postgresql"):
            errors.append(
                "DATABASE_URL deve começar com 'postgresql://' ou 'postgresql+asyncpg://'"
            )
        elif not db_url.startswith("postgresql+asyncpg"):
            warnings.append(
                "DATABASE_URL deveria usar 'postgresql+asyncpg://' para melhor performance"
            )
        if "[PASSWORD]" in db_url or "[HOST]" in db_url:
            errors.append(
                "DATABASE_URL contém placeholders. Substitua [PASSWORD] e [HOST] por valores reais."
            )
    elif db_host and db_user and db_password:
        # Usando componentes individuais
        if not db_host or db_host == "localhost":
            warnings.append("DB_HOST está como 'localhost'. Você está usando Supabase?")
        if not db_password:
            errors.append("DB_PASSWORD não está definido")
    else:
        errors.append(
            "DATABASE_URL não configurada. Configure ou use DB_HOST/DB_USER/DB_PASSWORD."
        )

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
        print("   1. Copie o arquivo env.example:")
        print("      cp env.example .env")
        print("   2. Edite o arquivo .env e configure DATABASE_URL")
        print()
        sys.exit(1)

    print(f"✅ Arquivo .env encontrado: {env_file.absolute()}")
    print()

    # Verifica banco de dados
    print("🔍 Verificando configuração do banco de dados...")
    db_ok, db_messages = check_database_config()

    if db_ok:
        print("✅ Configuração do banco de dados OK")
    else:
        print("❌ Problemas encontrados na configuração do banco:")

    for msg in db_messages:
        if msg.startswith("DATABASE_URL"):
            print(f"   ❌ {msg}")
        else:
            print(f"   ⚠️  {msg}")

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
        from config import get_config

        config = get_config()
        print("✅ Configuração importada com sucesso")

        # Mostra resumo (sem senha)
        db_url = config.database.url
        if "@" in db_url:
            # Oculta senha
            parts = db_url.split("@")
            if len(parts) == 2:
                user_pass = parts[0].split("//")[-1]
                if ":" in user_pass:
                    user = user_pass.split(":")[0]
                    db_url_safe = db_url.replace(user_pass, f"{user}:***")
                else:
                    db_url_safe = db_url
            else:
                db_url_safe = db_url
        else:
            db_url_safe = db_url

        print(f"   Database URL: {db_url_safe[:70]}...")
        print(f"   Min Discount: {config.scrape.min_discount_pct}%")
        print(f"   Max Scrolls: {config.scrape.max_scrolls}")
        print(f"   Max Items Print: {config.max_items_print}")

    except Exception as e:
        print(f"❌ Erro ao importar configuração: {type(e).__name__}: {e}")
        print()
        print("💡 Dica: Verifique se todas as dependências estão instaladas:")
        print("   pip install -r requirements.txt")
        sys.exit(1)

    print()
    print("=" * 60)

    if db_ok:
        print("✅ Todas as verificações passaram!")
        print()
        print("📚 Para mais informações, consulte ENV_SETUP.md")
        sys.exit(0)
    else:
        print("❌ Alguns problemas foram encontrados. Corrija antes de continuar.")
        print()
        print("📚 Para mais informações, consulte ENV_SETUP.md")
        sys.exit(1)


if __name__ == "__main__":
    main()
