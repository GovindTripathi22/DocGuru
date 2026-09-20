#!/usr/bin/env python3
"""
Environment Configuration Consistency Checker.
Verifies that variable names match across .env.example, docker-compose.yml, README.md, and config.py.
Fails with exit code 1 if any discrepancy is detected.
"""

from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def get_env_example_vars() -> set[str]:
    env_path = REPO_ROOT / ".env.example"
    if not env_path.exists():
        raise FileNotFoundError(f"{env_path} not found")
    vars_found = set()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            var_name = line.split("=", 1)[0].strip()
            vars_found.add(var_name)
    return vars_found


def get_config_vars() -> set[str]:
    config_path = REPO_ROOT / "backend" / "app" / "config.py"
    if not config_path.exists():
        raise FileNotFoundError(f"{config_path} not found")
    vars_found = set()
    content = config_path.read_text(encoding="utf-8")
    # Match class Settings field definitions (e.g. MODEL_PROVIDER: ... = ...)
    in_settings = False
    for line in content.splitlines():
        if "class Settings(" in line:
            in_settings = True
            continue
        if in_settings:
            if line.strip().startswith("def ") or line.strip().startswith("@"):
                break
            match = re.match(r"^\s+([A-Z0-9_]+)\s*:\s*", line)
            if match:
                vars_found.add(match.group(1))
    return vars_found


def get_compose_vars() -> set[str]:
    compose_path = REPO_ROOT / "docker-compose.yml"
    if not compose_path.exists():
        raise FileNotFoundError(f"{compose_path} not found")
    content = compose_path.read_text(encoding="utf-8")
    # Match ${VAR_NAME:-...} or ${VAR_NAME}
    matches = re.findall(r"\$\{([A-Z0-9_]+)(?::-[^}]*)?\}", content)
    return set(matches)


def get_readme_vars() -> set[str]:
    readme_path = REPO_ROOT / "README.md"
    if not readme_path.exists():
        raise FileNotFoundError(f"{readme_path} not found")
    content = readme_path.read_text(encoding="utf-8")
    # Match `VAR_NAME` inside markdown table rows
    matches = re.findall(r"\|\s*`([A-Z0-9_]+)`\s*\|", content)
    return set(matches)


def main():
    env_vars = get_env_example_vars()
    config_vars = get_config_vars()
    compose_vars = get_compose_vars()
    readme_vars = get_readme_vars()

    # Note: BACKEND_URL is used by frontend/BFF and present in .env.example, compose, README, but not in backend Settings
    # SESSION_SECRET and BACKEND_API_KEY may appear in compose/frontend
    backend_expected = env_vars - {"BACKEND_URL"}
    
    errors = []

    # 1. Config vs .env.example
    missing_in_config = backend_expected - config_vars
    if missing_in_config:
        errors.append(f"Variables in .env.example missing from Settings in config.py: {sorted(missing_in_config)}")

    # 2. README vs .env.example
    missing_in_readme = env_vars - readme_vars
    if missing_in_readme:
        errors.append(f"Variables in .env.example missing from README.md: {sorted(missing_in_readme)}")

    extra_in_readme = readme_vars - env_vars
    if extra_in_readme:
        errors.append(f"Variables in README.md not present in .env.example: {sorted(extra_in_readme)}")

    # 3. Compose vs .env.example
    compose_backend_vars = {v for v in compose_vars if v not in {"BACKEND_API_KEY", "SESSION_SECRET"}}
    missing_in_compose = env_vars - compose_backend_vars
    if missing_in_compose:
        errors.append(f"Variables in .env.example missing from docker-compose.yml: {sorted(missing_in_compose)}")

    if errors:
        print("ERROR: Environment variable consistency check failed!", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print(f"SUCCESS: All {len(env_vars)} environment variables are consistent across .env.example, config.py, docker-compose.yml, and README.md.")
    sys.exit(0)


if __name__ == "__main__":
    main()
