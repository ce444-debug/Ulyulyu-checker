# ============================================================
# rules_engine.py — ULYULYU CHECKER v2.7.6
# 2025-11-08: reason: добавлено правило BIN012 — контрольная сумма БИН (KZ mod11, 2-раунд);
#                     работает для БИН поставщика и покупателя; код один — BIN012.
# 2025-11-08: reason: BIN-поля — алиасы + фолбэк из raw_text, нормализация (v2.7.5).
# 2025-11-08: reason: поддержан формат даты YYYY.MM.DD; стабильная загрузка чеклиста/конфига.
# ============================================================

import os
import json
import re
from datetime import datetime, date
from typing import Dict, Any, List, Tuple

# --------------------------- загрузка файлов ---------------------------
def _core_dir() -> str:
    return os.path.dirname(__file__)

def _project_root() -> str:
    # core/ → ulyuly_checker/
    return os.path.abspath(os.path.join(_core_dir(), ".."))

def _load_json(candidates) -> Dict[str, Any]:
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}

CONFIG = _load_json([
    os.path.join(_project_root(), "config.json"),
    os.path.join(_core_dir(), "config.json"),
])

CHECKLIST_JSON = _load_json([
    os.path.join(_core_dir(), "rules", "checklist_full_v2.7.json"),
    os.path.join(_core_dir(), "checklist_full_v2.7.json"),  # на случай плоской выкладки
])

RULES = CHECKLIST_JSON.get("rules", {})

# --------------------------- утилиты ---------------------------
def _only_digits(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())

def _is_bin(value: str) -> bool:
    s = _only_digits(value)
    return len(s) == 12

# Поддерживаемые форматы дат (в т.ч. YYYY.MM.DD)
_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d")

def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    s = str(s).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

def _make_item(code: str, level: str, user: Dict[str, Any], value=None) -> Dict[str, Any]:
    item = {"code": code, "level": level, "user": user}
    if value is not None:
        item["value"] = value
    return item

def _first(doc: Dict[str, Any], *keys: str) -> str:
    """Возвращает первое непустое (после strip) значение по алиасам (строкой)."""
    for k in keys:
        if k in doc:
            v = doc.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s != "":
                return s
    return ""

# --------------------------- извлечение из raw_text ---------------------------
# 2025-11-08: reason: фолбэк — парсим БИН из текста по меткам
_BUYER_BIN_LABELS = [
    r"БИН\s*покупател[ьяя]", r"БИН\s*получател[ьяя]", r"BIN\s*(buyer|recipient)",
    r"ИИН/БИН\s*покупател[ьяя]", r"ИИН/БИН\s*получател[ьяя]"
]
_SUPPLIER_BIN_LABELS = [
    r"БИН\s*поставщик[а]", r"BIN\s*(supplier|seller)", r"ИИН/БИН\s*поставщик[а]"
]

def _extract_bin_from_text(text: str, labels: List[str]) -> str:
    """Ищем цифры после метки в пределах строки/абзаца."""
    if not text:
        return ""
    for lab in labels:
        pat = rf"({lab})[^0-9]{{0,80}}([0-9][0-9\ \-\.]{{3,}})"
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            raw = m.group(2)
            if _only_digits(raw):
                return raw.strip()
    return ""

# --------------------------- контрольная сумма BIN (KZ mod11) ---------------------------
# 2025-11-08: reason: добавлен расчёт контрольной суммы для БИН/ИИН по схеме mod11 (2 раунда):
#  round1: sum(d[i] * (i+1)) % 11 → если 10, round2: sum(d[i] * (i+3)) % 11. Контрольная = остаток.
def _kz_mod11_checksum_valid(bin12: str) -> bool:
    digits = _only_digits(bin12)
    if len(digits) != 12:
        return False
    nums = [int(c) for c in digits]
    control = nums[-1]
    # Раунд 1
    s1 = sum(nums[i] * (i + 1) for i in range(11))
    r1 = s1 % 11
    if r1 != 10:
        return control == r1
    # Раунд 2
    s2 = sum(nums[i] * (i + 3) for i in range(11))
    r2 = s2 % 11
    return control == r2

# --------------------------- правила v2.7.6 ---------------------------
def _rule_BIN001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("BIN001", {})
    v_raw = _first(
        doc,
        "supplier_BIN", "supplier_bin", "supplierBin",
        "seller_BIN", "seller_bin", "sellerBin"
    )
    if not v_raw:
        v_raw = _extract_bin_from_text(str(doc.get("raw_text","")), _SUPPLIER_BIN_LABELS)
    if not _is_bin(v_raw):
        return _make_item("BIN001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("BIN001", "OK",
                      {"title": "БИН поставщика распознан", "description": "", "recommendation": ""},
                      value=v_raw)

def _rule_BIN002(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("BIN002", {})
    v_raw = _first(
        doc,
        "recipient_BIN", "recipient_bin", "recipientBin",
        "buyer_BIN", "buyer_bin", "buyerBin",
        "customer_BIN", "customer_bin", "customerBin"
    )
    if not v_raw:
        v_raw = _extract_bin_from_text(str(doc.get("raw_text","")), _BUYER_BIN_LABELS)
    if not _is_bin(v_raw):
        return _make_item("BIN002", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("BIN002", "OK",
                      {"title": "БИН покупателя распознан", "description": "", "recommendation": ""},
                      value=v_raw)

def _rule_D000(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("D000", {})
    v_raw = _first(doc, "issue_date", "date_issue", "document_date", "дата_выписки", "issueDate")
    dt = _parse_date(v_raw)
    if dt is None:
        level = cfg.get("level", CONFIG.get("require_date_severity", "ERROR"))
        return _make_item("D000", level, cfg.get("user", {}), value=v_raw)
    return _make_item("D000", "OK", {"title": "Дата распознана", "description": "", "recommendation": ""}, value=v_raw)

def _rule_D001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("D001", {})
    v_raw = _first(doc, "issue_date", "date_issue", "document_date", "дата_выписки", "issueDate")
    dt = _parse_date(v_raw)
    if dt is None:
        return None  # пусть D000 отработает
    today = date.today()
    if dt.date() > today:
        return _make_item("D001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("D001", "OK", {"title": "Дата не в будущем", "description": "", "recommendation": ""}, value=v_raw)

# 2025-11-08: reason: новое правило BIN012 — контрольная сумма для обоих БИНов (если включено в конфиге)
def _rule_BIN012(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not dict(CONFIG).get("bin_rules", {}).get("bin_checksum_enabled", False):
        return []
    cfg = RULES.get("BIN012", {})
    out: List[Dict[str, Any]] = []

    def _check(one_value: str, role: str) -> None:
        """role: 'поставщика' | 'покупателя'"""
        raw = one_value
        if not _is_bin(raw):
            return  # длина/символы ловят BIN001/BIN002 — здесь только контрольная цифра
        ok = _kz_mod11_checksum_valid(raw)
        if not ok:
            user = cfg.get("user", {}).copy()
            # персонализируем заголовок под роль
            title = user.get("title", "Ошибка контрольной суммы БИН")
            user["title"] = f"{title} ({role})"
            out.append(_make_item("BIN012", cfg.get("level", "ERROR"), user, value=raw))
        else:
            # Информационная запись (можно не выводить в пользовательском режиме)
            out.append(_make_item("BIN012", "OK",
                                  {"title": f"Контрольная сумма БИН {role}: ОК",
                                   "description": "", "recommendation": ""}, value=raw))

    # получаем «как нашли» значения из BIN001/BIN002 логики (повторное извлечение)
    sup = _first(doc, "supplier_BIN", "supplier_bin", "supplierBin", "seller_BIN", "seller_bin", "sellerBin")
    if not sup:
        sup = _extract_bin_from_text(str(doc.get("raw_text","")), _SUPPLIER_BIN_LABELS)
    buy = _first(doc, "recipient_BIN", "recipient_bin", "recipientBin",
                 "buyer_BIN", "buyer_bin", "buyerBin", "customer_BIN", "customer_bin", "customerBin")
    if not buy:
        buy = _extract_bin_from_text(str(doc.get("raw_text","")), _BUYER_BIN_LABELS)

    _check(sup, "поставщика")
    _check(buy, "покупателя")
    return out

# --------------------------- движок ---------------------------
_RULE_FUNCS_SEQ = [
    _rule_BIN001, _rule_BIN002, _rule_D000, _rule_D001,  # базовые
]

def run_all_rules(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    # 1) одиночные правила
    for fn in _RULE_FUNCS_SEQ:
        try:
            item = fn(doc)
            if isinstance(item, list):
                results.extend(item)
            elif item is not None:
                results.append(item)
        except Exception as e:
            results.append({
                "code": fn.__name__,
                "level": "ERROR",
                "user": {
                    "title": "Внутренняя ошибка правила",
                    "description": f"{fn.__name__} упало: {e}",
                    "recommendation": "Сообщите разработчику."
                }
            })
    # 2) составное BIN012
    try:
        results.extend(_rule_BIN012(doc))
    except Exception as e:
        results.append({
            "code": "BIN012",
            "level": "ERROR",
            "user": {
                "title": "Внутренняя ошибка правила",
                "description": f"BIN012 упало: {e}",
                "recommendation": "Сообщите разработчику."
            }
        })
    return results

if __name__ == "__main__":
    sample = {
        "supplier_BIN": "422525832950",
        "recipient_bin": "987650000000",   # неверная КС для примера
        "issue_date": "2025.09.23",
        "raw_text": "… БИН покупателя: 987650000000 …"
    }
    for r in run_all_rules(sample):
        print(f"[{r['level']}] {r['code']} — {r['user'].get('title','')} (value={r.get('value')})")
