import ast
from pathlib import Path
import sys
import pytest

MODULE_TO_DISTRIBUTION = {
    "PIL": "pillow",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "pdfplumber": "pdfplumber",
    "pypdf": "pypdf",
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic-settings",
    "fastapi": "fastapi",
    "starlette": "fastapi",  # Provided via fastapi/starlette
    "uvicorn": "uvicorn",
    "httpx": "httpx",
    "google": "google-genai",
    "lxml": "lxml",
    "anyio": "anyio",
}


def test_llm_client_has_no_undeclared_ollama_import():
    app_dir = Path(__file__).parents[2] / "app"
    for py_file in app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "import ollama" not in content, f"Found 'import ollama' in {py_file}"


def test_all_backend_imports_are_declared_in_requirements():
    req_file = Path(__file__).parents[2] / "requirements.txt"
    assert req_file.exists()
    
    declared_pkgs = set()
    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg_name = line.split("==")[0].split(">=")[0].split("[")[0].strip().lower()
        declared_pkgs.add(pkg_name)

    app_dir = Path(__file__).parents[2] / "app"
    imported_modules = set()
    for py_file in app_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imported_modules.add(name.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    imported_modules.add(node.module.split(".")[0])

    stdlib = set(sys.stdlib_module_names)
    internal = {"backend", "app"}

    third_party = {m for m in imported_modules if m not in stdlib and m not in internal}

    for mod in third_party:
        dist_name = MODULE_TO_DISTRIBUTION.get(mod, mod.lower().replace("_", "-"))
        assert dist_name in declared_pkgs, f"Imported module '{mod}' maps to '{dist_name}' which is not in requirements.txt"
