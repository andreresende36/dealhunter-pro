"""Script para contar itens em arquivo JSON de debug."""

import json
import sys
from pathlib import Path

_DEBUG_DIR = Path("debug")

def _extract_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    raise ValueError("JSON não é uma lista nem possui chave 'items' com lista.")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(f"{_DEBUG_DIR}/items.json")
    if not path.exists():
        print(f"Arquivo não encontrado: {path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"JSON inválido em {path}: {exc}", file=sys.stderr)
        return 1

    try:
        items = _extract_items(data)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(len(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())