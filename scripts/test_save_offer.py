#!/usr/bin/env python3
"""Script de teste para verificar se ofertas estão sendo salvas no banco."""

from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path
from config import get_config
from database import DatabaseService, get_session, init_db
from models import ScrapedOffer

# Ajusta o path para o diretório app (pai do diretório debug)
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))


async def test_save_offer():
    """Testa salvamento de uma oferta simples."""
    config = get_config()

    # Verifica se configuração do Supabase está configurada
    if not config.database.supabase_url or not config.database.supabase_key:
        print("❌ SUPABASE_URL ou chave de API não configuradas!")
        return False

    print(f"✅ Configuração do Supabase OK: {config.database.supabase_url[:50]}...")

    # Cria uma oferta de teste
    test_offer = ScrapedOffer(
        marketplace="Mercado Livre",
        external_id="TEST-MLB-1234567890",
        title="Oferta de Teste",
        url="https://produto.mercadolivre.com.br/TEST-MLB-1234567890",
        image_url="https://example.com/image.jpg",
        price_cents=10000,  # R$ 100,00
        old_price_cents=15000,  # R$ 150,00
        discount_pct=33,
        commission_pct=None,
        affiliate_link=None,
        affiliation_id=None,
        source="test_script",
    )

    try:
        print("\n🔄 Inicializando banco...")
        init_db(config.database)

        print("🔄 Salvando oferta de teste...")
        async for session in get_session():
            try:
                db_service = DatabaseService(session)

                # Salva apenas 1 oferta de teste
                scrape_run = await db_service.save_scrape_run_with_offers(
                    offers=[test_offer],
                    min_discount_pct=30,
                    max_scrolls=4,
                    number_of_pages=1,
                    config_snapshot={"test": True},
                    save_price_history=True,
                    save_affiliate_info=False,
                )

                scrape_run_id = scrape_run["id"]
                print("✅ Oferta salva com sucesso!")
                print(f"   ScrapeRun ID: {scrape_run_id}")
                print(f"   External ID: {test_offer.external_id}")
                break
            except Exception as e:
                print(f"❌ ERRO ao salvar: {type(e).__name__}: {e}")
                print("\nTraceback:")
                print(traceback.format_exc())
                raise

        print("\n✅ Teste concluído! Verifique no Supabase se a oferta foi salva.")
        return True

    except Exception as e:
        print(f"\n❌ ERRO no teste: {type(e).__name__}: {e}")
        print("\nTraceback completo:")
        print(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = asyncio.run(test_save_offer())
    sys.exit(0 if success else 1)
