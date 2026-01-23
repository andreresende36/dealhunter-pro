#!/usr/bin/env python3
"""Script de auditoria completa do projeto DealHunter Pro."""

import ast
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

# Diretório raiz do projeto
PROJECT_ROOT = Path(__file__).parent
APP_DIR = PROJECT_ROOT / "app"


class ImportAnalyzer(ast.NodeVisitor):
    """Analisa imports e uso de símbolos em um arquivo Python."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.imports: dict[str, set[str]] = {}  # module -> {symbols}
        self.imported_modules: set[str] = set()
        self.used_symbols: set[str] = set()
        self.defined_symbols: set[str] = set()
        self.import_froms: dict[str, set[str]] = {}  # module -> {symbols}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module = alias.asname or alias.name.split(".")[0]
            self.imported_modules.add(module)
            self.imports[alias.name] = {module}

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            module_name = node.module.split(".")[0]
            self.imported_modules.add(module_name)
            symbols = {alias.asname or alias.name for alias in node.names}
            self.import_froms[node.module] = symbols
            self.imports[node.module] = symbols

    def visit_Name(self, node: ast.Name) -> None:
        self.used_symbols.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.defined_symbols.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.defined_symbols.add(node.name)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name):
            self.used_symbols.add(node.value.id)
        self.generic_visit(node)


def analyze_file(file_path: Path) -> dict[str, Any]:
    """Analisa um arquivo Python."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        return {"error": str(e), "file": str(file_path)}

    analyzer = ImportAnalyzer(file_path)
    analyzer.visit(tree)

    # Detecta imports não usados
    unused_imports = []
    for module, symbols in analyzer.import_froms.items():
        for symbol in symbols:
            if symbol not in analyzer.used_symbols and symbol not in analyzer.defined_symbols:
                # Verifica se é usado como atributo (ex: module.symbol)
                module_base = module.split('.')[0] if module else ""
                used_as_attr = (
                    f"{module_base}.{symbol}" in content
                    or f"{symbol}(" in content
                    or f"{symbol}[" in content
                    or f"{symbol}." in content
                )
                if not used_as_attr:
                    unused_imports.append(f"from {module} import {symbol}")

    # Imports simples
    for module in analyzer.imported_modules:
        # Verifica se o módulo é usado
        module_used = (
            module in analyzer.used_symbols
            or f"{module}." in content
            or f"import {module}" in content
        )
        if not module_used:
            unused_imports.append(f"import {module}")

    return {
        "file": str(file_path),
        "imports": analyzer.imports,
        "imported_modules": list(analyzer.imported_modules),
        "used_symbols": list(analyzer.used_symbols),
        "defined_symbols": list(analyzer.defined_symbols),
        "unused_imports": unused_imports,
        "line_count": len(content.splitlines()),
    }


def find_all_python_files(directory: Path) -> list[Path]:
    """Encontra todos os arquivos Python no diretório."""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Ignora diretórios comuns
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "venv", ".venv"}]
        for file in files:
            if file.endswith(".py"):
                python_files.append(Path(root) / file)
    return python_files


def find_unused_dependencies(requirements_file: Path, python_files: list[Path]) -> set[str]:
    """Encontra dependências não usadas no requirements.txt."""
    if not requirements_file.exists():
        return set()

    # Lê requirements
    with open(requirements_file, "r") as f:
        requirements = {
            line.split("==")[0].split(">=")[0].split(">")[0].split("<")[0].strip()
            for line in f
            if line.strip() and not line.startswith("#")
        }

    # Mapeia nomes de pacotes para imports
    package_to_import = {
        "playwright": "playwright",
        "python-dotenv": "dotenv",
        "supabase": "supabase",
        "rq": "rq",
        "rq-dashboard": "rq_dashboard",
        "redis": "redis",
        "prometheus-client": "prometheus_client",
        "pytest": "pytest",
        "pytest-asyncio": "pytest_asyncio",
    }

    # Verifica uso em todos os arquivos
    used_packages = set()
    for py_file in python_files:
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
                for req in requirements:
                    import_name = package_to_import.get(req, req.replace("-", "_"))
                    if import_name in content or req.replace("-", "_") in content:
                        used_packages.add(req)
        except Exception:
            pass

    return requirements - used_packages


def find_duplicate_code(files: list[Path], min_lines: int = 10) -> list[dict[str, Any]]:
    """Encontra código duplicado (simplificado - compara linhas)."""
    duplicates = []
    file_contents = {}

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                file_contents[file_path] = lines
        except Exception:
            pass

    # Compara arquivos
    files_list = list(file_contents.items())
    for i, (file1, lines1) in enumerate(files_list):
        for j, (file2, lines2) in enumerate(files_list[i + 1 :], start=i + 1):
            # Encontra sequências comuns
            common = find_common_sequences(lines1, lines2, min_lines)
            if common:
                duplicates.append(
                    {
                        "file1": str(file1),
                        "file2": str(file2),
                        "common_lines": common,
                    }
                )

    return duplicates


def find_common_sequences(lines1: list[str], lines2: list[str], min_len: int) -> list[list[str]]:
    """Encontra sequências comuns entre duas listas de linhas."""
    common = []
    # Implementação simplificada - encontra blocos idênticos
    for i in range(len(lines1) - min_len + 1):
        block = lines1[i : i + min_len]
        for j in range(len(lines2) - min_len + 1):
            if lines2[j : j + min_len] == block:
                common.append(block)
                break
    return common


def find_orphan_files(files: list[Path], analysis_results: list[dict[str, Any]]) -> list[str]:
    """Encontra arquivos que nunca são importados."""
    # Arquivos que são pontos de entrada (main, __init__, etc)
    entry_points = {"main.py", "__init__.py", "runner.py", "enrichment_worker.py"}

    defined_in_files = {}
    for result in analysis_results:
        if "error" in result:
            continue
        file_path = Path(result["file"])
        if file_path.name in entry_points:
            continue
        for symbol in result.get("defined_symbols", []):
            defined_in_files[symbol] = result["file"]

    # Verifica quais arquivos são importados
    imported_files = set()
    for result in analysis_results:
        if "error" in result:
            continue
        for module in result.get("imported_modules", []):
            # Tenta encontrar arquivo correspondente
            for file_path in files:
                if file_path.stem == module or file_path.name == f"{module}.py":
                    imported_files.add(str(file_path))

    # Arquivos órfãos são os que não são importados e não são entry points
    all_files = {str(f) for f in files}
    orphan_files = all_files - imported_files - {
        str(f) for f in files if f.name in entry_points
    }

    return list(orphan_files)


def main():
    """Executa auditoria completa."""
    print("🔍 FASE 1: AUDITORIA COMPLETA\n")
    print("=" * 80)

    # 1. Estrutura de diretórios
    print("\n📁 ÁRVORE DE DIRETÓRIOS:")
    print_tree(APP_DIR)

    # 2. Encontra todos os arquivos Python
    python_files = find_all_python_files(APP_DIR)
    print(f"\n📄 Total de arquivos Python encontrados: {len(python_files)}")

    # 3. Analisa cada arquivo
    print("\n🔎 Analisando arquivos...")
    analysis_results = []
    total_unused_imports = 0

    for py_file in python_files:
        result = analyze_file(py_file)
        analysis_results.append(result)
        if "unused_imports" in result:
            unused_count = len(result["unused_imports"])
            total_unused_imports += unused_count
            if unused_count > 0:
                print(f"  ⚠️  {py_file.relative_to(PROJECT_ROOT)}: {unused_count} imports não usados")

    # 4. Dependências não usadas
    print("\n📦 Verificando dependências...")
    requirements_file = APP_DIR / "requirements.txt"
    unused_deps = find_unused_dependencies(requirements_file, python_files)
    if unused_deps:
        print(f"  ⚠️  Dependências possivelmente não usadas: {', '.join(unused_deps)}")

    # 5. Código duplicado
    print("\n🔄 Procurando código duplicado...")
    duplicates = find_duplicate_code(python_files, min_lines=10)
    if duplicates:
        print(f"  ⚠️  Encontrados {len(duplicates)} pares de arquivos com código duplicado")

    # 6. Arquivos órfãos
    print("\n📭 Procurando arquivos órfãos...")
    orphan_files = find_orphan_files(python_files, analysis_results)
    if orphan_files:
        print(f"  ⚠️  Encontrados {len(orphan_files)} arquivos possivelmente órfãos")

    # 7. Relatório resumido
    print("\n" + "=" * 80)
    print("\n📊 RELATÓRIO RESUMIDO:")
    print(f"  • Total de arquivos Python: {len(python_files)}")
    print(f"  • Imports não utilizados: {total_unused_imports}")
    print(f"  • Dependências não usadas: {len(unused_deps)}")
    print(f"  • Código duplicado: {len(duplicates)} pares")
    print(f"  • Arquivos órfãos: {len(orphan_files)}")

    # Salva relatório detalhado
    save_detailed_report(analysis_results, unused_deps, duplicates, orphan_files)


def print_tree(directory: Path, prefix: str = "", max_depth: int = 3, current_depth: int = 0):
    """Imprime árvore de diretórios."""
    if current_depth >= max_depth:
        return

    try:
        entries = sorted(directory.iterdir())
        dirs = [e for e in entries if e.is_dir() and not e.name.startswith(".")]
        files = [e for e in entries if e.is_file() and e.suffix == ".py"]

        for i, entry in enumerate(dirs + files):
            is_last = i == len(dirs + files) - 1
            current_prefix = "└── " if is_last else "├── "
            print(f"{prefix}{current_prefix}{entry.name}")

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                print_tree(
                    entry,
                    prefix + extension,
                    max_depth,
                    current_depth + 1,
                )
    except PermissionError:
        pass


def save_detailed_report(
    analysis_results: list[dict[str, Any]],
    unused_deps: set[str],
    duplicates: list[dict[str, Any]],
    orphan_files: list[str],
):
    """Salva relatório detalhado em arquivo."""
    report_path = PROJECT_ROOT / "AUDIT_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 🔍 Relatório de Auditoria - DealHunter Pro\n\n")
        f.write("## 📋 FASE 1: AUDITORIA COMPLETA\n\n")

        # Imports não usados
        f.write("### Imports Não Utilizados\n\n")
        for result in analysis_results:
            if "unused_imports" in result and result["unused_imports"]:
                f.write(f"#### {result['file']}\n")
                for imp in result["unused_imports"]:
                    f.write(f"- `{imp}`\n")
                f.write("\n")

        # Dependências
        f.write("### Dependências Não Usadas\n\n")
        for dep in unused_deps:
            f.write(f"- `{dep}`\n")
        f.write("\n")

        # Código duplicado
        f.write("### Código Duplicado\n\n")
        for dup in duplicates:
            f.write(f"- `{dup['file1']}` ↔ `{dup['file2']}`\n")
        f.write("\n")

        # Arquivos órfãos
        f.write("### Arquivos Órfãos\n\n")
        for orphan in orphan_files:
            f.write(f"- `{orphan}`\n")

    print(f"\n✅ Relatório detalhado salvo em: {report_path}")


if __name__ == "__main__":
    main()
