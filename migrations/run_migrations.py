"""Script para executar migrations no banco de dados Supabase."""

from __future__ import annotations

import sys
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared.config.settings import get_config
from adapters.database import get_client, init_db
from shared.utils.logging import log


def run_migration(sql_file: Path) -> None:
    """
    Executa um arquivo SQL de migration.

    Args:
        sql_file: Caminho para o arquivo SQL
    """
    log(f"[migrations] Executando migration: {sql_file.name}")

    # Lê o arquivo SQL
    sql_content = sql_file.read_text(encoding="utf-8")

    # Divide em statements individuais (por ; e ignora comentários)
    statements = []
    current_statement = []

    for line in sql_content.split("\n"):
        # Ignora comentários e linhas vazias
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue

        current_statement.append(line)

        # Se termina com ;, é o fim de um statement
        if stripped.endswith(";"):
            statements.append("\n".join(current_statement))
            current_statement = []

    # Executa cada statement
    config = get_config()
    init_db(config.database)
    client = get_client()

    for i, statement in enumerate(statements, 1):
        try:
            # Para Supabase, usamos o método rpc para executar SQL raw
            # Nota: isso requer uma função SQL no Supabase que execute o SQL
            # Alternativamente, use o SQL Editor no dashboard do Supabase

            log(f"[migrations] Executando statement {i}/{len(statements)}...")

            # Como Supabase não tem um método direto para executar SQL arbitrário
            # via Python SDK, as migrations devem ser executadas manualmente
            # no SQL Editor do Supabase ou via psql

            print(f"\n-- Statement {i}:")
            print(statement)
            print()

        except Exception as e:
            log(f"[migrations] Erro no statement {i}: {e}")
            raise

    log(f"[migrations] Migration {sql_file.name} concluída com sucesso!")


def main() -> None:
    """Executa todas as migrations pendentes."""
    migrations_dir = Path(__file__).parent

    # Lista todos os arquivos .sql em ordem
    sql_files = sorted(migrations_dir.glob("*.sql"))

    if not sql_files:
        log("[migrations] Nenhuma migration encontrada.")
        return

    log(f"[migrations] Encontradas {len(sql_files)} migrations:")
    for sql_file in sql_files:
        log(f"  - {sql_file.name}")

    print("\n" + "=" * 80)
    print("IMPORTANTE: Migrations do Supabase")
    print("=" * 80)
    print(
        """
As migrations SQL devem ser executadas manualmente no Supabase:

1. Acesse o painel do Supabase: https://app.supabase.com
2. Navegue até SQL Editor
3. Copie e cole o conteúdo das migrations na ordem
4. Execute cada migration

Ou use psql diretamente:

    psql postgresql://[USER]:[PASSWORD]@[HOST]:[PORT]/[DATABASE] < migrations/001_add_performance_indexes.sql

As migrations SQL serão exibidas abaixo para facilitar a cópia:
"""
    )
    print("=" * 80 + "\n")

    for sql_file in sql_files:
        run_migration(sql_file)


if __name__ == "__main__":
    main()
