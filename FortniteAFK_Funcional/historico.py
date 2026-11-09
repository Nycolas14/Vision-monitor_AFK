"""Leitura e gravação do histórico de partidas em JSON."""
import json
from config import HISTORY


def load_history():
    if not HISTORY.exists():
        return []
    try:
        data = json.loads(HISTORY.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_history(records):
    HISTORY.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
