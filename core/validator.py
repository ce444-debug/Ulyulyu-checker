# ============================================================
# validator.py — ULYULYU CHECKER v2.7.3
# 2025-11-12: reason: убраны «…», согласована сигнатура validate_document(content, template=None),
#                     конвертация правил rules_engine → GUI (ValidationResult), сортировка по приоритету.
# ============================================================

import os
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

# 2025-11-12: абсолютный импорт, чтобы не падать при пакетах
from core import rules_engine

# --------------------------- конфиг ---------------------------
def _project_root() -> str:
    # core/ → ulyuly_checker/
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _load_config() -> Dict[str, Any]:
    candidates = [
        os.path.join(_project_root(), "config.json"),
        os.path.join(os.path.dirname(__file__), "config.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}

CONFIG = _load_config()
RULE_PRIORITY: Dict[str, int] = CONFIG.get("rule_priority", {})
UI_OVERLAY = bool(CONFIG.get("ui_overlay_enabled", False))
DEBUG_SHOW_VALUES = bool(CONFIG.get("debug_show_values", False))

# --------------------------- тип результата ---------------------------
@dataclass
class ValidationResult:
    code: str
    level: str
    message: str

# --------------------------- утилиты ---------------------------
def _priority_for(code: str) -> int:
    # по заданным, иначе BIN(0)→DATE(1)→прочее(2)
    if code in RULE_PRIORITY:
        return RULE_PRIORITY[code]
    if code.startswith("BIN"): return 0
    if code.startswith("D"):   return 1
    return 2

def _compose_message(item: Dict[str, Any]) -> str:
    """Собираем пользовательский текст и, при включённой отладке, подмешиваем value."""
    u = item.get("user", {})
    title = str(u.get("title", "")).strip()
    desc  = str(u.get("description", "")).strip()
    rec   = str(u.get("recommendation", "")).strip()
    parts = [p for p in (title, desc, rec) if p]
    msg = " — ".join(parts) if parts else str(item.get("message","")).strip()
    if DEBUG_SHOW_VALUES and "value" in item:
        msg = f"{msg} [значение: {item['value']}]"
    return msg

# --------------------------- API ---------------------------
def validate_document(content: Dict[str, Any], template: Dict[str, Any] | None = None) -> List[ValidationResult]:
    """
    content — распарсенные поля (supplier_BIN, recipient_BIN, issue_date, ...).
    template — не используется в v2.7, но оставлен для обратной совместимости с main.py
    """
    raw_items = rules_engine.run_all_rules(content)

    # Валидация возвращает список словарей вида:
    # { code, level, user:{title,description,recommendation}, value? }
    out: List[Tuple[int, ValidationResult]] = []
    for it in raw_items:
        code  = str(it.get("code","")).strip()
        level = str(it.get("level","INFO")).upper()
        msg   = _compose_message(it)
        out.append((_priority_for(code), ValidationResult(code=code, level=level, message=msg)))

    # сортируем по приоритету, затем по коду для стабильности
    out.sort(key=lambda t: (t[0], t[1].code))
    return [x[1] for x in out]

# --------------------------- самотест ---------------------------
if __name__ == "__main__":
    sample = {"supplier_BIN": "220629802621", "recipient_BIN": "", "issue_date": "2030-01-01"}
    for line in validate_document(sample):
        print(f"[{line.level}] {line.code}: {line.message}")
