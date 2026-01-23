#!/usr/bin/env python3
"""Script para atualizar imports após reestruturação."""

import re
from pathlib import Path

# Mapeamento de imports antigos para novos
IMPORT_MAPPINGS = {
    r"^from config import": "from shared.config.settings import",
    r"^from config\.settings import": "from shared.config.settings import",
    r"^from config\.environments import": "from shared.config.environments import",
    r"^from models import": "from core.domain import",
    r"^from models\.offer import": "from core.domain.offer import",
    r"^from database import": "from adapters.database import",
    r"^from database\.connection import": "from adapters.database.connection import",
    r"^from database\.repositories import": "from adapters.database.repositories import",
    r"^from scrapers import": "from adapters.external import",
    r"^from scrapers\.constants import": "from shared.constants.constants import",
    r"^from scrapers\.": "from adapters.external.",
    r"^from services import": "from core.use_cases import",
    r"^from services\.": "from core.use_cases.",
    r"^from utils import": "from shared.utils import",
    r"^from utils\.": "from shared.utils.",
    r"^from queues import": "from adapters.queues import",
    r"^from queues\.": "from adapters.queues.",
    r"^from workers import": "from adapters.workers import",
    r"^from workers\.": "from adapters.workers.",
    r"^import queues\.": "import adapters.queues.",
    r"^import debug\.": "import scripts.",
    r"^from debug\.": "from scripts.",
}

SRC_DIR = Path("src")


def update_file_imports(file_path: Path) -> bool:
    """Atualiza imports em um arquivo."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Erro ao ler {file_path}: {e}")
        return False

    original_content = content
    modified = False

    for old_pattern, new_replacement in IMPORT_MAPPINGS.items():
        pattern = re.compile(old_pattern, re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(new_replacement, content)
            modified = True

    if modified and content != original_content:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Erro ao escrever {file_path}: {e}")
            return False

    return False


def main():
    """Atualiza imports em todos os arquivos Python em src/."""
    updated_count = 0
    for py_file in SRC_DIR.rglob("*.py"):
        if update_file_imports(py_file):
            print(f"✅ Atualizado: {py_file}")
            updated_count += 1

    print(f"\n✅ Total de arquivos atualizados: {updated_count}")


if __name__ == "__main__":
    main()
