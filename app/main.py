# app/main.py
from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from runner import run_once


async def main() -> None:
    load_dotenv()

    # Para teste: roda uma vez e finaliza (mais simples)
    # Se você quiser loop/scheduler depois, a gente evolui daqui.
    await run_once()


if __name__ == "__main__":
    # Em alguns ambientes (notebooks), pode precisar de asyncio policy,
    # mas em Docker/Linux normalmente isso roda direto.
    asyncio.run(main())
