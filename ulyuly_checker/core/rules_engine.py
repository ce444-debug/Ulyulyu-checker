# ============================================================
# rules_engine.py — ULYULYU CHECKER v2.7.9 (Extended Aliases)
# 2025-11-10: reason: расширены алиасы для BIN, DATE и SUM (унификация PDF/Excel/JSON)
# ============================================================

import os
import json
import re
from datetime import datetime, date
from typing import Dict, Any, List

# --------------------------- загрузка ---------------------------
def _core_dir() -> str:
    return os.path.dirname(__file__)

def _project_root() -> str:
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
    os.path.join(_core_dir(), "checklist_full_v2.7.json"),
])

RULES = CHECKLIST_JSON.get("rules", {})

# --------------------------- утилиты ---------------------------
def _only_digits(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())

def _is_bin(value: str) -> bool:
    s = _only_digits(value)
    return len(s) == 12

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
    for k in keys:
        if k in doc:
            v = doc.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s != "":
                return s
    return ""

# --------------------------- BIN extraction ---------------------------
_SUPPLIER_BIN_LABELS = [
    r"БИН\s*поставщик[а]", r"BIN\s*(supplier|seller)", r"ИИН/БИН\s*поставщик[а]",
    r"БИН\s*продавца", r"БИН\s*организации"
]
_BUYER_BIN_LABELS = [
    r"БИН\s*покупател[ьяя]", r"БИН\s*получател[ьяя]", r"BIN\s*(buyer|recipient)",
    r"ИИН/БИН\s*покупател[ьяя]", r"ИИН/БИН\s*получател[ьяя]", r"БИН\s*заказчика"
]

def _extract_bin_from_text(text: str, labels: List[str]) -> str:
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

# --------------------------- контрольная сумма BIN ---------------------------
def _kz_mod11_checksum_valid(bin12: str) -> bool:
    digits = _only_digits(bin12)
    if len(digits) != 12:
        return False
    nums = [int(c) for c in digits]
    control = nums[-1]
    s1 = sum(nums[i] * (i + 1) for i in range(11))
    r1 = s1 % 11
    if r1 != 10:
        return control == r1
    s2 = sum(nums[i] * (i + 3) for i in range(11))
    r2 = s2 % 11
    return control == r2

# --------------------------- правила ---------------------------
def _rule_BIN001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("BIN001", {})
    # 2025-11-10: reason: расширены алиасы для поиска БИН поставщика (PDF, Excel, JSON)
    v_raw = _first(
        doc,
        "supplier_BIN", "supplier_bin", "supplierBin",
        "seller_BIN", "seller_bin", "sellerBin",
        "Поставщик", "Продавец", "BIN продавца", "БИН поставщика"
    )
    if not v_raw:
        v_raw = _extract_bin_from_text(str(doc.get("raw_text", "")), _SUPPLIER_BIN_LABELS)
    if not _is_bin(v_raw):
        return _make_item("BIN001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("BIN001", "OK", {"title": "БИН поставщика распознан"}, value=v_raw)

def _rule_BIN002(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("BIN002", {})
    # 2025-11-10: reason: расширены алиасы для поиска БИН покупателя (PDF, Excel, JSON)
    v_raw = _first(
        doc,
        "recipient_BIN", "recipient_bin", "recipientBin",
        "buyer_BIN", "buyer_bin", "buyerBin",
        "customer_BIN", "customer_bin", "customerBin",
        "Покупатель", "Получатель", "БИН покупателя", "BIN buyer"
    )
    if not v_raw:
        v_raw = _extract_bin_from_text(str(doc.get("raw_text", "")), _BUYER_BIN_LABELS)
    if not _is_bin(v_raw):
        return _make_item("BIN002", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("BIN002", "OK", {"title": "БИН покупателя распознан"}, value=v_raw)

def _rule_BIN007(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("BIN007", {})
    allow_equal = bool(CONFIG.get("bin_rules", {}).get("allow_equal_bins", False))
    sup = _first(doc, "supplier_BIN", "supplier_bin", "seller_BIN", "seller_bin", "Поставщик", "Продавец")
    if not sup:
        sup = _extract_bin_from_text(str(doc.get("raw_text", "")), _SUPPLIER_BIN_LABELS)
    buy = _first(doc, "recipient_BIN", "recipient_bin", "buyer_BIN", "buyer_bin", "Покупатель", "Получатель")
    if not buy:
        buy = _extract_bin_from_text(str(doc.get("raw_text", "")), _BUYER_BIN_LABELS)
    if not sup or not buy:
        return None
    if sup == buy:
        if allow_equal:
            return _make_item("BIN007", "OK", cfg.get("ok_user", {"title": "БИНы совпадают (разрешено)"}), value=f"{sup}/{buy}")
        else:
            return _make_item("BIN007", cfg.get("level", "WARN"), cfg.get("user", {}), value=f"{sup}/{buy}")
    return _make_item("BIN007", "OK", cfg.get("ok_user", {"title": "БИНы различаются"}), value=f"{sup}/{buy}")

def _rule_D000(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("D000", {})
    # 2025-11-10: reason: расширены алиасы даты (PDF/Excel/JSON)
    v_raw = _first(
        doc,
        "issue_date", "date_issue", "document_date", "documentDate",
        "дата_выписки", "дата_составления", "дата", "Дата",
        "Document date", "Дата выписки", "Дата составления"
    )
    dt = _parse_date(v_raw)
    if dt is None:
        return _make_item("D000", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("D000", "OK", {"title": "Дата распознана"}, value=v_raw)

def _rule_D001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("D001", {})
    v_raw = _first(
        doc,
        "issue_date", "date_issue", "document_date", "documentDate",
        "дата_выписки", "дата_составления", "дата", "Дата",
        "Document date", "Дата выписки", "Дата составления"
    )
    dt = _parse_date(v_raw)
    if dt and dt.date() > date.today():
        return _make_item("D001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("D001", "OK", {"title": "Дата не в будущем"}, value=v_raw)

def _rule_TOT001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("TOT001", {})
    # 2025-11-10: reason: расширены алиасы итоговой суммы (PDF/Excel/JSON)
    val = _first(
        doc,
        "total_amount", "total_sum", "total", "amount", "Всего", "Итог",
        "Сумма документа", "Total", "Итого с НДС", "TotalAmount", "AmountTotal"
    )
    if val == "":
        return _make_item("TOT001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=None)
    try:
        num = float(str(val).replace(",", "."))
        if num <= 0:
            return _make_item("TOT001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=val)
    except ValueError:
        return _make_item("TOT001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=val)
    return _make_item("TOT001", "OK", {"title": "Итоговая сумма указана корректно"}, value=val)

def _rule_NEG001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("NEG001", {})
    val = _first(
        doc,
        "total_amount", "total_sum", "total", "amount", "Всего", "Итог",
        "Сумма документа", "Total", "Итого с НДС", "TotalAmount", "AmountTotal"
    )
    if not val:
        return None
    try:
        num = float(str(val).replace(",", "."))
        if num < 0:
            return _make_item("NEG001", cfg.get("level", "WARN"), cfg.get("user", {}), value=val)
    except ValueError:
        return None
    return None

def _rule_BIN012(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not dict(CONFIG).get("bin_rules", {}).get("bin_checksum_enabled", False):
        return []
    cfg = RULES.get("BIN012", {})
    out: List[Dict[str, Any]] = []
    for role, key in {"поставщика": "supplier_BIN", "покупателя": "recipient_BIN"}.items():
        val = _first(doc, key, key.lower())
        if not _is_bin(val):
            continue
        if not _kz_mod11_checksum_valid(val):
            user = cfg.get("user", {}).copy()
            user["title"] = f"{user.get('title', 'Ошибка контрольной суммы')} ({role})"
            out.append(_make_item("BIN012", cfg.get("level", "ERROR"), user, value=val))
        else:
            out.append(_make_item("BIN012", "OK", {"title": f"Контрольная сумма БИН {role}: ОК"}, value=val))
    return out

# --------------------------- движок ---------------------------
_RULE_FUNCS_SEQ = [
    _rule_BIN001, _rule_BIN002, _rule_BIN007, _rule_D000, _rule_D001, _rule_TOT001, _rule_NEG001
]

def run_all_rules(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for fn in _RULE_FUNCS_SEQ:
        try:
            res = fn(doc)
            if isinstance(res, list):
                results.extend(res)
            elif res is not None:
                results.append(res)
        except Exception as e:
            results.append({
                "code": fn.__name__,
                "level": "ERROR",
                "user": {"title": f"Ошибка правила {fn.__name__}", "description": str(e)}
            })
    try:
        results.extend(_rule_BIN012(doc))
    except Exception as e:
        results.append({"code": "BIN012", "level": "ERROR", "user": {"title": "Ошибка BIN012", "description": str(e)}})
    return results

if __name__ == "__main__":
    sample = {"supplier_BIN": "574910337420", "recipient_BIN": "519830113301", "issue_date": "2025-09-25", "total_amount": "1200"}
    for r in run_all_rules(sample):
        print(f"[{r['level']}] {r['code']} — {r['user'].get('title','')} ({r.get('value')})")
