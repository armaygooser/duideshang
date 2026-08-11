from functools import lru_cache
from pathlib import Path

import yaml

API_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = API_ROOT / "knowledge"


@lru_cache
def load_yaml(name: str) -> dict:
    with (KNOWLEDGE_DIR / name).open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def pricing_rules() -> dict:
    return load_yaml("pricing_rules.yaml")


def acceptance_templates() -> dict:
    return load_yaml("acceptance_templates.yaml")
