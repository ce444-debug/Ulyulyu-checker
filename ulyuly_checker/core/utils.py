# ============================================================
# core/utils.py — ULYULYU CHECKER v2.7 → v2.8-pre (Mini-refactor)
#
# [2025-11-18] feat: новый модуль общих утилит
#   Причина: убрать дубли парсеров дат/чисел/ключей из ридеров/валидатора,
#            зафиксировать единый контракт данных и подготовить почву под v2.8.
# ============================================================

from __future__ import annotations
import os
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

# --------------------------- конфиг ---------------------------

_CFG_CACHE: Dict[str, Any] | None = None

def _project_root() -> str:
    # ulyuly_checker/  (core/ находится внутри)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def load_config() -> Dict[str, Any]:
    """Ленивая загрузка config.json с кэшем."""
    global _CFG_CACHE
    if _CFG_CACHE is not None:
        return _CFG_CACHE
    candidates = [
        os.path.join(_project_root(), "config.json"),
        os.path.join(os.path.dirname(__file__), "config.json"),
        os.path.join(os.getcwd(), "config.json"),
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    _CFG_CACHE = data
                    return _CFG_CACHE
        except Exception:
            pass
    _CFG_CACHE = {}
    return _CFG_CACHE

# --------------------------- нормализация текста/ключей ---------------------------

def clean_text(s: Any) -> str:
    """Базовая очистка: пробелы, NBSP, скрытые символы, схлопывание."""
    if s is None:
        return ""
    t = str(s)
    t = t.replace("\u00A0", " ")
    t = re.sub(r"[\u200b\u200e\u202f\t\r\n]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def clean_key(s: Any) -> str:
    """Очистка для сравнения заголовков/ярлыков."""
    t = clean_text(s).lower()
    t = t.replace("№", "номер")
    t = t.replace("иин/бин", "бин").replace("бин/иин", "бин")
    t = t.replace("счёт", "счет").replace("счет-фактура", "счет фактура")
    t = t.replace("получател", "покупател")  # унификация buyer-маркеров
    t = re.sub(r"[^\w\s]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

# --------------------------- числа/даты ---------------------------

def only_digits(s: Any) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())

def parse_number(val: Any) -> Optional[float]:
    """Безопасное приведение к числу: убираем пробелы, NBSP, апострофы, ','→'.'"""
    if val is None:
        return None
    s = str(val)
    s = s.replace("\u00A0", "").replace("\u202F", "").replace(" ", "")
    s = s.replace("'", "").replace("\u2019", "").replace("\u2018", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

_MONTHS_RU = {
    "января":1,"февраля":2,"марта":3,"апреля":4,"мая":5,"июня":6,
    "июля":7,"августа":8,"сентября":9,"октября":10,"ноября":11,"декабря":12
}

def _excel_serial_to_datetime(value: float) -> Optional[datetime]:
    try:
        base = datetime(1899, 12, 30)  # Windows base (с багом 1900)
        return base + timedelta(days=float(value))
    except Exception:
        return None

def parse_date_any(val: Any) -> Optional[datetime]:
    """Парсинг: datetime, Excel-число, YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY, «от 22 сентября 2025 г.»"""
    # 1) уже datetime
    if isinstance(val, datetime):
        return val.replace(tzinfo=None)

    # 2) Excel serial
    if isinstance(val, (int, float)):
        if 20000 <= float(val) <= 60000:
            dt = _excel_serial_to_datetime(val)
            if dt:
                return dt

    text = clean_text(val)
    if not text:
        return None

    # Numeric формы
    patterns = [
        r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})",
        r"(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})",
        r"(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})",
        r"(?P<y>\d{4})/(?P<m>\d{1,2})/(?P<d>\d{1,2})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            try:
                y = int(m.group("y")); mth = int(m.group("m")); d = int(m.group("d"))
                return datetime(y, mth, d)
            except Exception:
                pass

    # Рус. месяцы: (от) «22» сентября 2025 г.
    m = re.search(
        r"(?:\bот\s+)?[«\"]?(?P<d>\d{1,2})[»\"]?\s+(?P<mon>января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(?P<y>\d{4})",
        text.lower()
    )
    if m:
        try:
            d = int(m.group("d")); y = int(m.group("y"))
            mth = _MONTHS_RU[m.group("mon")]
            return datetime(y, mth, d)
        except Exception:
            return None

    return None

def to_iso(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else ""

def tolerance_compare(a: float, b: float, abs_tol: float = 0.5, rel_tol: float = 0.0005) -> bool:
    """Сравнение с допусками (для сумм)."""
    try:
        if a == b:
            return True
        if abs(a - b) <= abs_tol:
            return True
        if b != 0 and abs(a - b) / abs(b) <= rel_tol:
            return True
    except Exception:
        pass
    return False

# --------------------------- BIN ---------------------------

def is_valid_bin(value: Any) -> bool:
    """Жёсткая проверка БИН/ИИН: 12 цифр, не все одинаковые, не пусто."""
    if value is None:
        return False
    try:
        s = only_digits(str(value))
    except Exception:
        return False
    if len(s) != 12:
        return False
    if len(set(s)) == 1:
        return False
    return True

# --------------------------- нормализация контракта ---------------------------

def normalize_keys(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Приводит поля к канону + дублирует legacy-алиасы, не затрагивая уже заданные.
    Канон:
      supplier_bin, buyer_bin, issue_date (YYYY-MM-DD), turnover_date,
      total_amount, total_net, total_vat, total_gross, lines, _trace
    """
    if not isinstance(doc, dict):
        return {}

    out = dict(doc)  # не портим вход

    # Алиасы БИН
    if "supplier_bin" not in out and "supplier_BIN" in out:
        out["supplier_bin"] = out.get("supplier_BIN") or ""
    if "buyer_bin" not in out:
        for k in ("recipient_BIN", "buyer_BIN", "customer_BIN"):
            if k in out:
                out["buyer_bin"] = out.get(k) or ""
                break

    # Алиасы даты
    if "issue_date" not in out:
        for k in ("date_issue", "document_date", "Дата выписки", "Дата"):
            if k in out and out.get(k):
                out["issue_date"] = out.get(k) or ""
                break

    # Итоги — оставляем как есть, только без изменений ключей
    for k in ("total_amount", "total_net", "total_vat", "total_gross"):
        if k not in out:
            out[k] = out.get(k) or ""

    # Линии/трейс — по умолчанию безопасные значения
    out.setdefault("lines", out.get("lines") or [])
    out.setdefault("_trace", out.get("_trace") or {})

    # Canon → legacy (для обратной совместимости движка/старых правил)
    if "supplier_BIN" not in out and out.get("supplier_bin"):
        out["supplier_BIN"] = out["supplier_bin"]
    if "recipient_BIN" not in out and out.get("buyer_bin"):
        out["recipient_BIN"] = out["buyer_bin"]
    if "date_issue" not in out and out.get("issue_date"):
        out["date_issue"] = out["issue_date"]

    # Нормализация даты в ISO, если возможно
    if out.get("issue_date"):
        dt = parse_date_any(out["issue_date"])
        if dt:
            out["issue_date"] = to_iso(dt)

    return out
