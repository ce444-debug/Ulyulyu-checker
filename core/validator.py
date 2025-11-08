# 2025-11-06: Smart Priority Sorting + config.rule_priority
# Без изменений в этой версии: принимает уровни из правил (в т.ч. D001 с конфигом).
# 2025-11-08: UI overlay for checklist_full_v2 (user-friendly texts)
# Причина: при наличии checklist_full_v2.json выводить человеко-понятные
#          описания/рекомендации в GUI, а технические детали и коды — только в логах.
#          Логи остаются прежними, так как overlay применяется ПОСЛЕ логирования.
# 2025-11-08: OK/INFO overlay
# Причина: для успешных проверок показывать понятные тексты (например, «БИН корректный»),
#          если такие тексты заданы в checklist_full_v2.json (user.ok / user.success / и т.п.).

from typing import Dict, List, Any, Tuple
import os, json
from .rules_engine import run_all_rules
from .utils import load_checklist, log_validation_result

class ValidationResult:
    def __init__(self, code: str, level: str, message: str):
        self.code = code or "UNK"
        self.level = (level or "INFO").upper()
        self.message = message or ""

    def to_dict(self) -> Dict[str, str]:
        return {"code": self.code, "level": self.level, "message": self.message}

_SEVERITY_RANK = {"ERROR": 0, "WARN": 1, "INFO": 2}

def _group_weight(code: str) -> int:
    c = (code or "").upper()
    if c.startswith(("BIN", "ID")): return 0
    if c.startswith(("D", "DATE")): return 1
    if c.startswith(("TOT", "AMT", "SUM", "VAT", "NEG", "ROUND")): return 2
    if c.startswith(("LIN", "QTY", "PRC", "UOM", "MIS", "STR", "META")): return 3
    return 4

def _load_rule_overrides() -> Dict[str, int]:
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        if not os.path.exists(cfg_path): return {}
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        rp = cfg.get("rule_priority", {})
        out = {}
        for k, v in rp.items():
            try: out[str(k).upper()] = int(v)
            except Exception: continue
        return out
    except Exception:
        return {}

_RULE_PRIORITY_OVERRIDES = _load_rule_overrides()

def _priority_key(vr: 'ValidationResult') -> Tuple[int, int, str]:
    sev = _SEVERITY_RANK.get((vr.level or "INFO").upper(), 2)
    group = _RULE_PRIORITY_OVERRIDES.get((vr.code or "UNK").upper(), _group_weight(vr.code))
    return (sev, group, vr.code or "ZZZ")

# 2025-11-08: overlay loader for checklist_full_v2.json
def _project_root() -> str:
    # .../core/validator.py -> .../
    return os.path.dirname(os.path.dirname(__file__))

def _load_checklist_v2() -> Dict[str, Any]:
    """Ищем checklist_full_v2.json в стандартных местах проекта."""
    candidates = [
        os.path.join(_project_root(), "core", "rules", "checklist_full_v2.json"),
        os.path.join(_project_root(), "rules", "checklist_full_v2.json"),
        os.path.join(_project_root(), "assets", "rules", "checklist_full_v2.json"),
        os.path.join(os.getcwd(), "checklist_full_v2.json"),
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "rules" in data:
                    return data
        except Exception:
            continue
    return {}

def _pick_user_ok_text(user_block: Dict[str, Any]) -> str:
    """Пытаемся найти текст «ОК» в разных возможных ключах user.*"""
    if not isinstance(user_block, dict): return ""
    candidates = [
        "ok", "ok_text", "success", "success_text", "passed", "pass_text",
        "info_ok", "okMessage", "ok_message", "message_ok", "human_ok"
    ]
    for key in candidates:
        val = user_block.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # fallback: если есть title — используем «{title}: проверка пройдена»
    title = user_block.get("title")
    if isinstance(title, str) and title.strip():
        return f"{title.strip()}: проверка пройдена."
    return ""

def _apply_user_overlays(results: List['ValidationResult']) -> List['ValidationResult']:
    """
    Заменяет message на текст из checklist_full_v2.json:
      - для ERROR/WARN → user.description (+ 'Рекомендация: ' + user.recommendation);
      - для INFO/ОК    → user.ok / user.success / ... (если указано).
    """
    v2 = _load_checklist_v2()
    rules = v2.get("rules") or {}
    for vr in results:
        code = (vr.code or "").upper()
        rb = rules.get(code) or {}
        user = rb.get("user") or {}

        if vr.level in ("ERROR", "WARN"):
            desc = (user.get("description") or "").strip()
            rec  = (user.get("recommendation") or "").strip()
            if desc and rec:
                vr.message = f"{desc} Рекомендация: {rec}"
            elif desc:
                vr.message = desc
            elif rec:
                vr.message = f"Рекомендация: {rec}"
            # иначе оставляем message движка правил
        else:
            # INFO / OK
            ok_text = _pick_user_ok_text(user)
            if ok_text:
                vr.message = ok_text
            # иначе оставляем message движка («Проверка пройдена», и т.п.)
    return results

def validate_document(content: Dict[str, Any], template: Dict[str, Any]) -> List['ValidationResult']:
    if not isinstance(content, dict):
        return [ValidationResult("SYS000", "ERROR", "❌ Некорректный формат данных (ожидается dict).")]

    try:
        rule_items = run_all_rules(content, template)
    except Exception as e:
        rule_items = [{"code": "SYSEXC", "level": "ERROR", "message": f"❌ Исключение при выполнении правил: {e}"}]

    results: List[ValidationResult] = []
    for it in rule_items or []:
        vr = ValidationResult(
            code=str(it.get("code", "UNK")),
            level=str(it.get("level", "INFO")).upper(),
            message=str(it.get("message", "")),
        )
        results.append(vr)
        # 2025-11-08: Логируем до применения overlay — в логи уходит технический текст и код
        try: log_validation_result(vr)
        except Exception: pass

    if not results:
        results.append(ValidationResult("SYS001", "INFO", "✅ Все проверки успешно пройдены."))

    # 2025-11-08: UI overlay — человеко-понятные тексты для GUI (включая ОК)
    results = _apply_user_overlays(results)

    return sorted(results, key=_priority_key)
