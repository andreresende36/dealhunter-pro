"""Script para importar cookies para storage state do Playwright."""

import asyncio
import json

from playwright.async_api import async_playwright  # type: ignore

SAMESITE = {
    "no_restriction": "None",
    "none": "None",
    "lax": "Lax",
    "strict": "Strict",
    "unspecified": "Lax",
    "": "Lax",
}


def normalize(c):
    """Normaliza um cookie para o formato do Playwright."""
    same = SAMESITE.get(str(c.get("sameSite", "")).lower(), "Lax")
    return {
        "name": c["name"],
        "value": c["value"],
        "domain": c.get("domain") or ".mercadolivre.com.br",
        "path": c.get("path") or "/",
        "expires": int(c.get("expirationDate", -1)),
        "httpOnly": bool(c.get("httpOnly", False)),
        "secure": bool(c.get("secure", False)),
        "sameSite": same,
    }


async def main():
    """Função principal para importar cookies."""
    with open("cookies.json", "r", encoding="utf-8") as f:
        raw = json.load(f)

    cookies = [
        normalize(c) for c in raw if "mercadolivre.com.br" in (c.get("domain") or "")
    ]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies(cookies)  # type: ignore
        await context.storage_state(path="storage_state.json")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
