#!/usr/bin/env python3
"""Script para testar e diagnosticar conexão com o banco de dados Supabase."""

from __future__ import annotations

import asyncio
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse


# Garante que estamos no diretório correto antes dos imports locais
# Este arquivo está em debug/, então precisamos ir para o diretório pai (app/)
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

from config import get_config  # noqa: E402
from database import get_session, init_db  # noqa: E402


def diagnose_connection() -> bool:
    """
    Diagnostica problemas de conexão básicos (DNS, TCP).
    Não testa a conexão real do banco, apenas conectividade de rede.

    Returns:
        True se os testes básicos passaram, False caso contrário
    """
    print("=" * 60)
    print("Diagnóstico de Conexão com Supabase")
    print("=" * 60)
    print()

    # Carrega configuração
    try:
        config = get_config()
        supabase_url = config.database.supabase_url
        print("✅ Configuração carregada")
        print()
    except Exception as e:
        print(f"❌ Erro ao carregar configuração: {e}")
        return False

    # Parse da URL do Supabase
    try:
        parsed = urlparse(supabase_url)
        host = parsed.hostname
        if not host:
            print("❌ Host não encontrado na URL")
            print(f"   URL: {supabase_url[:50]}...")
            return False

        # Para diagnóstico, usamos porta padrão HTTP/HTTPS do Supabase
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        print("📋 Informações da Conexão:")
        print(f"   Supabase URL: {supabase_url}")
        print(f"   Host: {host}")
        print(f"   Protocolo: {parsed.scheme}")
        print()

    except Exception as e:
        print(f"❌ Erro ao fazer parse da URL: {e}")
        print(f"   URL: {supabase_url[:50]}...")
        return False

    # Teste de DNS
    if not host:
        print("❌ Host não especificado na URL")
        return False

    print("🔄 Testando resolução DNS...")
    try:
        ip = socket.gethostbyname(host)
        print(f"✅ DNS resolvido: {host} -> {ip}")
    except socket.gaierror as e:
        print(f"❌ Erro ao resolver DNS: {e}")
        print("   Verifique se o host está correto")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False
    print()

    # Teste de conectividade TCP
    print(f"🔄 Testando conectividade TCP ({host}:{port})...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            print(f"✅ Porta {port} está acessível")
        else:
            print(f"❌ Porta {port} não está acessível (código: {result})")
            print()
            print("💡 Possíveis soluções:")
            print("   1. Verifique se está usando a porta correta:")
            print("      - 5432 para Session Mode")
            print("      - 6543 para Connection Pooling (recomendado)")
            print("   2. Verifique se o firewall permite conexões")
            print("   3. Tente usar a porta de connection pooling (6543)")
            return False
    except socket.timeout:
        print(f"❌ Timeout ao conectar em {host}:{port}")
        print("   O servidor pode estar bloqueando a conexão")
        return False
    except OSError as e:
        print(f"❌ Erro de rede: {e}")
        print()
        print("💡 Possíveis causas:")
        print("   1. Firewall bloqueando conexão")
        print("   2. Host/porta incorretos")
        print("   3. Problema de rede local")
        print("   4. Supabase pode estar bloqueando seu IP")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False
    print()

    # Sugestões
    print("=" * 60)
    print("✅ Diagnóstico básico concluído")
    print("=" * 60)
    print()
    print("💡 Se a conectividade TCP está OK mas ainda há erro:")
    print("   1. Verifique as credenciais (usuário/senha)")
    print("   2. Verifique se o banco de dados existe")
    print("   3. Verifique se o Supabase permite conexões do seu IP")
    print("   4. Tente usar a porta de connection pooling (6543)")
    print()
    return True


async def test_connection() -> bool:
    """Testa a conexão real com o banco de dados."""
    print("=" * 60)
    print("Teste de Conexão com Supabase")
    print("=" * 60)
    print()

    # Carrega configuração
    try:
        config = get_config()
        db_config = config.database
        print("✅ Configuração carregada")

        # Mostra informações da configuração Supabase
        print(f"   Supabase URL: {db_config.supabase_url}")
        print(
            f"   Chave: {'Configurada' if db_config.supabase_key else 'Não configurada'}"
        )
        print()
    except Exception as e:
        print(f"❌ Erro ao carregar configuração: {type(e).__name__}: {e}")
        print()
        print("💡 Verifique se o arquivo .env está configurado corretamente.")
        print("   Veja ENV_SETUP.md para instruções.")
        return False

    # Inicializa banco
    try:
        print("🔄 Inicializando conexão com o banco...")
        init_db(db_config)
        print("✅ Conexão inicializada")
        print()
    except Exception as e:
        print(f"❌ Erro ao inicializar conexão: {type(e).__name__}: {e}")
        print()
        print(
            "💡 Verifique se SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY "
            "estão configuradas no arquivo .env"
        )
        return False

    # Testa conexão
    try:
        print("🔄 Testando conexão...")
        async for client in get_session():
            # Teste 1: Query simples (tenta selecionar da primeira tabela)
            try:
                # Tenta fazer um SELECT simples na tabela offers
                client.table("offers").select("id").limit(1).execute()
                print("✅ Conexão com Supabase funcionando")
            except Exception as e:
                # Se a tabela não existir, ainda testamos se a API responde
                error_msg = str(e).lower()
                if "relation" in error_msg or "does not exist" in error_msg:
                    print(
                        "✅ Conexão com Supabase OK (tabelas podem não existir ainda)"
                    )
                else:
                    raise

            # Teste 2: Verificar se as tabelas existem (tentando SELECT em cada uma)
            print()
            print("🔄 Verificando tabelas...")
            expected_tables = [
                "offers",
                "scrape_runs",
                "offer_scrape_runs",
                "price_history",
                "affiliate_info",
            ]

            existing_tables = []
            for table in expected_tables:
                try:
                    # Tenta fazer um SELECT simples para verificar se a tabela existe
                    client.table(table).select("id").limit(0).execute()
                    existing_tables.append(table)
                except Exception:
                    # Tabela não existe ou não está acessível
                    pass

            if existing_tables:
                print(f"✅ Tabelas encontradas: {len(existing_tables)}")
                for table in expected_tables:
                    if table in existing_tables:
                        print(f"   ✅ {table}")
                    else:
                        print(f"   ⚠️  {table} (não encontrada)")

                missing = set[str](expected_tables) - set(existing_tables)
                if missing:
                    print()
                    print("⚠️  Algumas tabelas estão faltando!")
                    print("   Execute as migrações em migrations/ (001, 002, 003)")
                    print("   Veja DATABASE_SETUP.md para instruções.")
            else:
                print("⚠️  Nenhuma tabela encontrada no banco")
                print("   Execute as migrações em migrations/ (001, 002, 003)")
                print("   Veja DATABASE_SETUP.md para instruções.")

            break  # Sair do loop após primeira iteração

        print()
        print("=" * 60)
        print("✅ Teste de conexão concluído com sucesso!")
        print("=" * 60)
        return True

    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Erro ao testar conexão: {type(e).__name__}: {e}")
        print("=" * 60)
        print()

        # Mensagens específicas para erros comuns
        error_msg = str(e).lower()
        if (
            "circuit breaker" in error_msg
            or "unable to establish connection to upstream" in error_msg
        ):
            print("💡 Erro específico: 'Circuit breaker open'")
            print()
            print(
                "   O circuit breaker do Supabase foi ativado devido a muitas falhas."
            )
            print("   Isso pode acontecer quando:")
            print("   1. Muitas tentativas de conexão falharam")
            print("   2. O projeto Supabase pode estar pausado")
            print("   3. Há problemas de rede/infraestrutura temporários")
            print()
            print("   ✅ Soluções:")
            print(
                "   1. Aguarde alguns minutos e tente novamente (circuit breaker se reseta)"
            )
            print("   2. Verifique se o projeto Supabase está ATIVO (não pausado)")
            print("   3. Verifique as credenciais no Supabase Dashboard")
            print("   4. Verifique se Connection Pooling está habilitado")
            print("   5. Tente usar conexão direta (se tiver IPv6)")
            print()
        elif (
            "connection was closed" in error_msg
            or "connectiondoesnotexisterror" in error_msg
        ):
            print(
                "💡 Erro específico: 'Connection was closed in the middle of operation'"
            )
            print()
            print("   Isso geralmente acontece quando:")
            print(
                "   1. O asyncpg usa prepared statements que não funcionam bem com pooler"
            )
            print("   2. A conexão está sendo fechada pelo pooler durante a operação")
            print()
            print("   ✅ Solução aplicada automaticamente:")
            print(
                "      - Desabilitado cache de prepared statements (statement_cache_size=0)"
            )
            print("      - Habilitado pool_pre_ping para detectar conexões fechadas")
            print()
            print("   ⚠️  Ação necessária:")
            print(
                "      O Session Pooler (porta 5432) pode não funcionar bem com asyncpg."
            )
            print("      Recomendado: teste com Transaction Pooler (porta 6543)")
            print()
            print("   Como fazer:")
            print("   1. Supabase Dashboard → Settings → Database → Connect")
            print("   2. Selecione 'Transaction Pooler' → 'URI'")
            print("   3. Copie a string e atualize DATABASE_URL (porta será 6543)")
            print()
            print("   Veja TROUBLESHOOTING_CONNECTION.md para detalhes completos.")
            print()
        elif "connection to database not available" in error_msg.lower():
            print("💡 Erro específico: 'Connection to database not available'")
            print()
            print(
                "   Isso geralmente significa que o pooler não consegue conectar ao banco."
            )
            print("   Tente uma das seguintes soluções:")
            print()
            print("   1. Teste com Transaction Pooler (porta 6543):")
            print("      Altere a porta de 5432 para 6543 na DATABASE_URL")
            print()
            print("   2. Verifique se o Session Pooler está habilitado no Supabase:")
            print("      Settings → Database → Connection Pooling")
            print()
            print("   3. Tente usar a conexão direta:")
            print("      Use o host db.xxxxx.supabase.co (sem pooler) na porta 5432")
            print()
        else:
            print("💡 Possíveis causas:")
            print("   1. DATABASE_URL incorreta no arquivo .env")
            print("   2. Credenciais incorretas (usuário/senha)")
            print("   3. Firewall bloqueando conexão")
            print("   4. Host/porta incorretos")
            print()

        print("   Verifique ENV_SETUP.md e CONNECTION_FIX.md para mais detalhes.")
        return False


async def main() -> None:
    """
    Função principal que executa diagnóstico básico e teste completo.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Testa e diagnostica conexão com banco de dados"
    )
    parser.add_argument(
        "--diagnose-only",
        action="store_true",
        help="Executa apenas diagnóstico básico (DNS, TCP), sem testar conexão SQL",
    )
    parser.add_argument(
        "--skip-diagnose",
        action="store_true",
        help="Pula diagnóstico básico e testa diretamente a conexão SQL",
    )

    args = parser.parse_args()

    success = True

    # Executa diagnóstico básico se não for pulado
    if not args.skip_diagnose:
        success = diagnose_connection()
        if not success:
            print()
            print("⚠️  Diagnóstico básico falhou. Teste de conexão SQL será pulado.")
            print("   Use --skip-diagnose para forçar teste SQL mesmo assim.")
            sys.exit(1)

    # Executa teste completo se não for apenas diagnóstico
    if not args.diagnose_only:
        print()
        print()
        sql_success = await test_connection()
        success = success and sql_success

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
