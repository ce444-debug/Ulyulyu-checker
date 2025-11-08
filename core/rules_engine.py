# 2025-11-07: rules_engine v1.10.1 — D001 скрывается, если D000 (дата отсутствует/не распознана)
# Новое в v1.10.1:
# - Если дата отсутствует/не распознана и поле обязательно (require_issue_date=true), правило D001 возвращает None
#   и НЕ отображается. На экране остаётся только D000.
# - Алиасы даты: issue_date | date_issue | invoice_date (без изменений).
# - Остальные правила без изменений.
#
# Совместимость: сигнатуры и формат результатов прежние.

from __future__ import annotations
from typing import Dict, Any, List, Callable, Optional
import os, json, math
from datetime import datetime, date, timedelta

# =========================
# 🔧 Загрузка конфигурации
# =========================
def _project_root() -> str:
    # .../core/rules_engine.py -> .../ (корень проекта)
    return os.path.dirname(os.path.dirname(__file__))

def _load_config() -> Dict[str, Any]:
    candidates = [
        os.path.join(_project_root(), "config.json"),
        os.path.join(os.getcwd(), "config.json"),
        os.path.join(_project_root(), "ulyuly_checker", "config.json"),
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return {}

_CFG: Dict[str, Any] = _load_config()

def _cfg_get_int(key: str, default: int) -> int:
    try:
        return int(_CFG.get(key, default))
    except Exception:
        return default

def _cfg_get_str(key: str, default: str) -> str:
    v = _CFG.get(key, default)
    if not isinstance(v, str):
        return default
    s = v.strip().upper()
    return s if s else default

def _cfg_get_bool(key: str, default: bool) -> bool:
    v = _CFG.get(key, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1","true","yes","y","on")
    if isinstance(v, (int, float)):
        return bool(v)
    return default

# =================================
# 🗓️ Утилиты для даты/чисел/строк
# =================================
_ISO_VARIANTS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d")
_DMY_VARIANTS = ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y")
_MDY_VARIANTS = ("%m/%d/%Y",)

def _parse_date(value: Any) -> Optional[datetime]:
    """
    Принимает строку/дату/datetime и возвращает datetime без TZ.
    Поддерживает ISO, DMY (казахстанский), MDY и распространённые дата-время.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            return None

    s = value.strip()
    for fmt in _ISO_VARIANTS + _DMY_VARIANTS + _MDY_VARIANTS:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # дата-время варианты
    dt_patterns = [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
        "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M",
        "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in dt_patterns:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None

def _as_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).replace(" ", "").replace("\u00A0", "").replace(",", ".")
        return float(s)
    except Exception:
        return None

def _is_12_digits(bin_str: Any) -> bool:
    if not isinstance(bin_str, str):
        try:
            bin_str = str(bin_str)
        except Exception:
            return False
    s = bin_str.strip()
    return len(s) == 12 and s.isdigit()

# ============================
# ✅ Реестр правил (RULE_MAP)
# ============================
def _get_issue_date_raw(doc: Dict[str, Any]) -> Any:
    # Алиасы даты
    for key in ("issue_date", "date_issue", "invoice_date"):
        if key in doc and doc.get(key) not in (None, ""):
            return doc.get(key)
    return None

def check_BIN001(doc: Dict[str, Any], tpl: Dict[str, Any]) -> Dict[str, str]:
    """Поставщик: BIN задан и валиден (12 цифр)."""
    v = doc.get("supplier_bin") or doc.get("supplier_BIN")
    if _is_12_digits(v):
        return {"code": "BIN001", "level": "INFO", "message": "Проверка пройдена."}
    return {"code": "BIN001", "level": "ERROR", "message": "BIN поставщика отсутствует или некорректен."}

def check_BIN002(doc: Dict[str, Any], tpl: Dict[str, Any]) -> Dict[str, str]:
    """Покупатель: BIN задан и валиден (12 цифр)."""
    v = doc.get("buyer_bin") or doc.get("recipient_BIN") or doc.get("buyer_BIN")
    if _is_12_digits(v):
        return {"code": "BIN002", "level": "INFO", "message": "Проверка пройдена."}
    return {"code": "BIN002", "level": "ERROR", "message": "BIN покупателя отсутствует или некорректен."}

def check_D000(doc: Dict[str, Any], tpl: Dict[str, Any]) -> Dict[str, str]:
    """
    Обязательная дата: отсутствует или не распознана.
    Управляется конфигом:
      require_issue_date (bool, default True)
      require_date_severity ("ERROR"|"WARN"|"INFO", default "ERROR")
    """
    raw = _get_issue_date_raw(doc)
    required = _cfg_get_bool("require_issue_date", True)
    if not required:
        return {"code": "D000", "level": "INFO", "message": "Поле даты не обязательно (config)."}
    dt = _parse_date(raw)
    if dt is None:
        sev = _cfg_get_str("require_date_severity", "ERROR")
        if sev not in {"ERROR", "WARN", "INFO"}:
            sev = "ERROR"
        return {"code": "D000", "level": sev, "message": "Дата счёта отсутствует или не распознана."}
    return {"code": "D000", "level": "INFO", "message": "Дата присутствует и распознана."}

def check_D001(doc: Dict[str, Any], tpl: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Дата счёта в будущем.
    Управляется конфигом:
      allow_future_days (int, default 0)
      date_tolerance_minutes (int, default 0)
      date_future_severity ("ERROR"|"WARN"|"INFO", default "ERROR")
    Логика подавления:
      - Если дату не распознали/нет и require_issue_date=true → вернуть None (не показывать D001, см. D000).
    """
    raw = _get_issue_date_raw(doc)
    dt = _parse_date(raw)

    required = _cfg_get_bool("require_issue_date", True)
    if not dt:
        if required:
            return None  # уже будет D000 — не дублируем
        else:
            return None  # для черновиков тоже не шумим по умолчанию

    allow_days = _cfg_get_int("allow_future_days", 0)
    tol_min = _cfg_get_int("date_tolerance_minutes", 0)
    severity = _cfg_get_str("date_future_severity", "ERROR")
    if severity not in {"ERROR", "WARN", "INFO"}:
        severity = "ERROR"

    now = datetime.now()
    limit = now + timedelta(days=allow_days, minutes=tol_min)
    if dt > limit:
        return {"code": "D001", "level": severity, "message": "Дата счёта в будущем."}
    return {"code": "D001", "level": "INFO", "message": "Дата счёта не в будущем."}

def check_TOT001(doc: Dict[str, Any], tpl: Dict[str, Any]) -> Dict[str, str]:
    """Сумма строк равна итогу документа (с небольшой погрешностью округления)."""
    total = _as_float(doc.get("total_amount"))
    if total is None:
        return {"code": "TOT001", "level": "WARN", "message": "Итоговая сумма отсутствует."}

    lines = doc.get("lines") or []
    s = 0.0
    for ln in lines:
        amt = _as_float((ln or {}).get("amount"))
        if amt is not None:
            s += amt

    if math.isclose(s, total, rel_tol=0, abs_tol=0.5):
        return {"code": "TOT001", "level": "INFO", "message": "Итог совпадает с суммой строк."}
    return {"code": "TOT001", "level": "ERROR", "message": "Сумма строк не равна итогу документа."}

def check_NEG001(doc: Dict[str, Any], tpl: Dict[str, Any]) -> Dict[str, str]:
    """Итоговая сумма не должна быть отрицательной."""
    total = _as_float(doc.get("total_amount"))
    if total is None:
        return {"code": "NEG001", "level": "WARN", "message": "Итоговая сумма отсутствует."}
    if total < 0:
        return {"code": "NEG001", "level": "ERROR", "message": "Отрицательная сумма."}
    return {"code": "NEG001", "level": "INFO", "message": "Сумма не отрицательная."}

# Карта правил
RULE_MAP: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, str] | None]] = {
    "BIN001": check_BIN001,
    "BIN002": check_BIN002,
    "D000":   check_D000,
    "D001":   check_D001,
    "TOT001": check_TOT001,
    "NEG001": check_NEG001,
}

# ============================
# ▶️ Запуск всех правил
# ============================
def run_all_rules(document: Dict[str, Any], checklist: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Возвращает список словарей:
      {"code": "...", "level": "ERROR|WARN|INFO", "message": "..."}
    Правила могут возвращать None — такой результат пропускается.
    """
    results: List[Dict[str, str]] = []
    for code, fn in RULE_MAP.items():
        try:
            res = fn(document or {}, checklist or {})
            if isinstance(res, dict) and res.get("code"):
                lvl = str(res.get("level", "INFO")).upper()
                if lvl not in {"ERROR", "WARN", "INFO"}:
                    res["level"] = "INFO"
                results.append(res)
        except Exception as e:
            results.append({"code": code, "level": "ERROR", "message": f"Исключение при выполнении правила: {e}"})
    return results
