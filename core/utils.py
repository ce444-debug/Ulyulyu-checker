# 2025-11-05: добавлены функции загрузки чек-листа и логирования проверок
# Причина: интеграция инспекционных правил v1.6 (Logic & Validation)

import json
import os
from datetime import datetime
from typing import Dict, Any


def load_checklist(path: str = "core/rules/checklist_full.json") -> Dict[str, Any]:
    """Загружает чек-лист инспектора из JSON."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[УЛЮЛЮ WARNING] Не найден файл чек-листа: {path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"[УЛЮЛЮ ERROR] Ошибка чтения чек-листа: {e}")
        return {}


def ensure_dir(path: str):
    """Создаёт каталог, если не существует."""
    os.makedirs(path, exist_ok=True)


def log_validation_result(result):
    """Записывает результаты проверки в файл data/results.log."""
    ensure_dir("data")
    log_path = os.path.join("data", "results.log")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{result.level}] [{result.code}] {result.message}\n")
