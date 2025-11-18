# ============================================================
# rules_engine.py — ULYULYU CHECKER v2.7.20
#
# [2025-11-18] refactor(mini): перед запуском правил нормализуем
#                  входные данные через core.utils.normalize_keys()
#                  (без изменения логики правил). Остальной код
#                  оставлен как есть для сохранения поведения v2.7.
# (см. историю правок внутри файла)
# ============================================================

import os
import json
import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple

from . import utils  # [2025-11-18] нормализация канона полей

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

# --------------------------- утилиты (оригинал сохранён) ---------------------------

def _only_digits(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())

def _is_bin(value: str) -> bool:
    s = _only_digits(value)
    return len(s) == 12

_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y.%m.%d", "%d-%m-%Y")

def _parse_date_numeric(s: str) -> Optional[datetime]:
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

def _to_number(val: str) -> Optional[float]:
    # оставляем поведение v2.7 (совместимость)
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

# --------------------------- mojibake fixer ---------------------------

def _cyr_count(s: str) -> int:
    return sum(1 for ch in s if ('А' <= ch <= 'я') or ch in 'ЁёІіґҐЇїЙй')

def _fix_mojibake(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    candidates = [text]
    try:
        candidates.append(text.encode('latin-1', errors='strict').decode('cp1251', errors='strict'))
    except Exception:
        pass
    try:
        candidates.append(text.encode('cp1252', errors='strict').decode('utf-8', errors='strict'))
    except Exception:
        pass
    try:
        c1 = text.encode('cp1252', errors='strict').decode('utf-8', errors='strict')
        candidates.append(c1.encode('latin-1', errors='strict').decode('cp1251', errors='strict'))
    except Exception:
        pass
    try:
        d1 = text.encode('latin-1', errors='strict').decode('cp1251', errors='strict')
        candidates.append(d1.encode('cp1252', errors='strict').decode('utf-8', errors='strict'))
    except Exception:
        pass
    return max(candidates, key=_cyr_count)

# --------------------------- ESF section ---------------------------

def _get_esf_headers() -> List[str]:
    sec = dict(CONFIG).get("sections", {})
    headers = sec.get("esf_headers") or []
    if headers:
        return headers
    return [
        r"СЧ[ЕЁ]Т[-\s]*ФАКТУРА(\s*№|\s*N)?",
        r"\bЭСФ\b",
        r"Electronic\s*(Tax\s*)?Invoice",
        r"Ñ×[ÅE]Ò[-\s]*ÔÀÊÒÓÐÀ(\s*¹|\s*N)?"
    ]

_NEXT_HEADER_STOP = r"(?m)^\s*(Акт(\s+выполненных)?|Приложение|Сч[её]т(\s*№|\s*N)?\b|Invoice\s*No\.?)"

def _extract_esf_section(full_text: str) -> str:
    if not full_text:
        return full_text
    text = _fix_mojibake(full_text)
    headers = _get_esf_headers()
    starts = []
    for h in headers:
        for m in re.finditer(h, text, flags=re.IGNORECASE):
            starts.append(m.start())
    if not starts:
        return text
    start = min(starts)
    tail = text[start:]
    m = re.search(_NEXT_HEADER_STOP, tail, flags=re.IGNORECASE)
    return tail[:m.start()].strip() if m else tail.strip()

def _get_text(doc: Dict[str, Any]) -> str:
    raw = str(doc.get("raw_text", "") or "")
    fixed = _fix_mojibake(raw)
    if dict(CONFIG).get("sections", {}).get("prefer_esf_section", True):
        return _extract_esf_section(fixed)
    return fixed

def _get_text_with_fallback(doc: Dict[str, Any]) -> Tuple[str, str]:
    fixed_full = _fix_mojibake(str(doc.get("raw_text", "") or ""))
    if dict(CONFIG).get("sections", {}).get("prefer_esf_section", True):
        section = _extract_esf_section(fixed_full)
        return section, fixed_full
    return fixed_full, fixed_full

# --------------------------- BIN ---------------------------

_SUPPLIER_BIN_LABELS = [
    r"БИН\s*поставщик[а]",
    r"БИН[^\n\r]{0,40}поставщик[а]",
    r"BIN\s*(supplier|seller)",
    r"ИИН/БИН[^\n\r]{0,40}поставщик[а]",
    r"БИН\s*продавца", r"БИН\s*организации",
    r"Реквизиты[^\n\r]*БИН",
    r"ÁÈÍ[^\n\r]{0,40}ïîñòàâùèê[à]",
    r"ÈÈÍ/ÁÈÍ[^\n\r]{0,40}ïîñòàâùèê[à]",
    r"Ðåêâèçèòû[^\n\r]*ÁÈÍ"
]

_BUYER_BIN_LABELS = [
    r"БИН\s*покупател[ьяя]", r"БИН\s*получател[ьяя]",
    r"(БИН|ИИН|ИИН/БИН)[^\n\r]{0,40}(покупател[ьяя]|получател[ьяя]|заказчик[а])",
    r"BIN\s*(buyer|recipient)",
    r"Заказчик[:\s]*",
    r"ÁÈÍ[^\n\r]{0,40}(ïîêóïàòåë[ьяÿ]|ïîëó÷àòåë[ьяÿ])",
    r"ÈÈÍ/ÁÈÍ[^\n\r]{0,40}(ïîêóïàòåë[ьяÿ]|ïîëó÷àòåë[ьяÿ])",
    r"Çàêàç÷èê[:\s]*"
]

def _extract_bin_from_text(text: str, labels: List[str]) -> str:
    if not text:
        return ""
    for lab in labels:
        pat = rf"({lab})[^\d]{{0,80}}(?P<bin>\d[\d\ \-\'\.]{{3,}})"
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group("bin").strip()
    return ""

# --------------------------- DATE ---------------------------

_DATE_LABELS = [
    r"Дата\s*(выставления|выписки)\s*[:\-]",
    r"Äàòà\s*(âûñòàâëåíèÿ|âûïèñêè)\s*[:\-]"
]

_MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
}
_MONTHS_RU_RE = "|".join(_MONTHS_RU.keys())

_ESF_HEADER_DATE_PATTERNS = [
    r"СЧ[ЕЁ]Т[-\s]?ФАКТУРА[^\n\r]{0,80}от\s*(?P<date>(\d{2}[./-]\d{2}[./-]\d{4})|(\d{4}[./-]\d{2}[./-]\d{2}))",
    r"Ñ×[ÅE]Ò[-\s]?ÔÀÊÒÓÐÀ[^\n\r]{0,80}îò\s*(?P<date>(\d{2}[./-]\d{2}[./-]\d{4})|(\d{4}[./-]\d{2}[./-]\d{2}))"
]

def _extract_header_date(text: str) -> str:
    if not text:
        return ""
    for pat in _ESF_HEADER_DATE_PATTERNS:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m and m.group("date"):
            return m.group("date").strip()
    return ""

def _extract_date_from_text(text: str) -> str:
    if not text:
        return ""
    date_pat = r"(?P<date>(\d{2}[./-]\d{2}[./-]\d{4})|(\d{4}[./-]\d{2}[./-]\d{2}))"
    for lab in _DATE_LABELS:
        m = re.search(rf"(?P<label>{lab})\s*{date_pat}", text, flags=re.IGNORECASE)
        if m and m.group("date"):
            return m.group("date").strip()
    m2 = re.search(rf"\b(?P<dd>\d{{1,2}})\b\s+(?P<mon>{_MONTHS_RU_RE})\s+\b(?P<yyyy>\d{{4}})\b", text, flags=re.IGNORECASE)
    if m2:
        dd = int(m2.group("dd")); mm = _MONTHS_RU[m2.group("mon").lower()]; yyyy = int(m2.group("yyyy"))
        try:
            return date(year=yyyy, month=mm, day=dd).strftime("%d.%m.%Y")
        except ValueError:
            pass
    m3 = re.search(r"(\b\d{2}[./-]\d{2}[./-]\d{4}\b)|(\b\d{4}[./-]\d{2}[./-]\d{2}\b)", text)
    if m3:
        return m3.group(0).strip()
    return ""

def _parse_date_any(s: str) -> Optional[datetime]:
    return _parse_date_numeric(s)

# --------------------------- BIN checksum ---------------------------

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

# --------------------------- СУММЫ ---------------------------

def _sum_labels_from_config() -> List[str]:
    t = dict(CONFIG).get("totals", {})

    base_cfg = t.get("labels") or [
        "Итого",
        "Итого\\s*с\\s*НДС",
        "Всего",
        "Всего\\s*к\\s*оплате",
        "К\\s*оплате",
        "Всего\\s*стоимость\\s*реализации",
        "Total",
        "Grand\\s*Total"
    ]

    mojibake = [
        "Èòîãî",
        "Èòîãî\\s*ñ\\s*ÍÄÑ",
        "Âñåãî",
        "Âñåãî\\s*ê\\s*îïëàòå",
        "Âñåãî\\s*ïî\\s*ñ÷åòó",
        "Âñåãî\\s*ñòîèìîñòü\\s*ðåàëèçàöèè"
    ]

    return list(dict.fromkeys(base_cfg + mojibake))

def _sum_gap_from_config() -> int:
    t = dict(CONFIG).get("totals", {})
    gap = int(t.get("max_gap", 140))
    return max(20, min(gap, 300))

def _priority_sum_labels() -> List[str]:
    return [
        r"Всего\s*к\s*оплате",
        r"Итого\s*с\s*НДС",
        r"Всего\s*стоимость\s*реализации",
        r"Âñåãî\s*ê\s*îïëàòå",
        r"Èòîãî\s*ñ\s*ÍÄÑ",
        r"Âñåãî\s*ñòîèìîñòü\\s*ðåàëèçàöèè",
    ]

def _sum_patterns() -> List[re.Pattern]:
    labels_union = "(?:" + "|".join(_sum_labels_from_config()) + ")"
    gap = _sum_gap_from_config()
    core = rf"{labels_union}\s*[:\-]?\s*[^\d\n\r]{{0,{gap}}}([0-9\s\u00A0\u202F\u2019\u2018\'\,\.]+)"
    table = rf"([0-9\s\u00A0\u202F\u2019\u2018\'\,\.]+)[^\d\n\r]{{0,{gap}}}{labels_union}"
    return [re.compile(core, re.IGNORECASE), re.compile(table, re.IGNORECASE)]

def _looks_like_money(text_num: str) -> bool:
    t = (text_num or "").strip()
    if not t:
        return False
    if any(ch in t for ch in [",", ".", "’", "'"]):
        return True
    digits = len(_only_digits(t))
    return 3 <= digits <= 8

def _near_bin_iin(context: str) -> bool:
    ctx = (context or "").lower()
    return ("бин" in ctx) or ("ийн" in ctx) or ("iin" in ctx) or ("bin" in ctx)

def _find_total_candidates_with_ctx(text: str) -> List[Tuple[str, Tuple[int, int]]]:
    out: List[Tuple[str, Tuple[int, int]]] = []
    if not text:
        return out
    for pat in _sum_patterns():
        for m in pat.finditer(text):
            val = (m.group(1) or "").strip()
            if val:
                out.append((val, m.span(1)))
    return out

def _find_total_value(text: str) -> Optional[str]:
    if not text:
        return None

    # приоритетные метки — допускаем переносы
    for lab in _priority_sum_labels():
        pat = re.compile(rf"{lab}[^\d]{{0,220}}([0-9\s\u00A0\u202F\u2019\u2018\'\,\.]+)",
                         re.IGNORECASE | re.DOTALL)
        m = pat.search(text)
        if m:
            raw = (m.group(1) or "").strip()
            if _looks_like_money(raw) and _to_number(raw) is not None:
                s, e = m.span(1)
                l = max(0, s-40); r = min(len(text), e+40)
                if not _near_bin_iin(text[l:r]):
                    return raw

    # общий поиск
    cands = _find_total_candidates_with_ctx(text)
    scored: List[Tuple[int, float, str]] = []
    for raw, (s, e) in cands:
        if not _looks_like_money(raw):
            continue
        l = max(0, s-40); r = min(len(text), e+40)
        if _near_bin_iin(text[l:r]):
            continue
        num = _to_number(raw)
        if num is None:
            continue
        score = 0
        if any(ch in raw for ch in [",", ".", "’", "'"]):
            score += 2
        if len(_only_digits(raw)) >= 4:
            score += 1
        scored.append((score, num, raw))
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], x[1]))
    return scored[-1][2]

# --------------------------- ПРАВИЛА ---------------------------

def _rule_BIN001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("BIN001", {})
    v_raw = _first(doc, "supplier_BIN", "supplier_bin", "supplierBin",
                   "seller_BIN", "seller_bin", "sellerBin",
                   "Поставщик", "Продавец", "BIN продавца", "БИН поставщика")
    if not v_raw:
        sec_text, full_text = _get_text_with_fallback(doc)
        v_raw = _extract_bin_from_text(sec_text, _SUPPLIER_BIN_LABELS) or \
                _extract_bin_from_text(full_text, _SUPPLIER_BIN_LABELS)
    if not _is_bin(v_raw):
        return _make_item("BIN001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("BIN001", "OK", {"title": "БИН поставщика распознан"}, value=v_raw)

def _rule_BIN002(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("BIN002", {})
    v_raw = _first(doc, "recipient_BIN", "recipient_bin", "recipientBin",
                   "buyer_BIN", "buyer_bin", "buyerBin",
                   "customer_BIN", "customer_bin", "customerBin",
                   "Покупатель", "Получатель", "БИН покупателя", "BIN buyer")
    if not v_raw:
        sec_text, full_text = _get_text_with_fallback(doc)
        v_raw = _extract_bin_from_text(sec_text, _BUYER_BIN_LABELS) or \
                _extract_bin_from_text(full_text, _BUYER_BIN_LABELS)
    if not _is_bin(v_raw):
        return _make_item("BIN002", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("BIN002", "OK", {"title": "БИН покупателя распознан"}, value=v_raw)

def _rule_BIN007(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("BIN007", {})
    allow_equal = bool(CONFIG.get("bin_rules", {}).get("allow_equal_bins", False))
    sec_text, full_text = _get_text_with_fallback(doc)
    sup = _first(doc, "supplier_BIN", "supplier_bin", "seller_BIN", "seller_bin") or \
          _extract_bin_from_text(sec_text, _SUPPLIER_BIN_LABELS) or \
          _extract_bin_from_text(full_text, _SUPPLIER_BIN_LABELS)
    buy = _first(doc, "recipient_BIN", "recipient_bin", "buyer_BIN", "buyer_bin") or \
          _extract_bin_from_text(sec_text, _BUYER_BIN_LABELS) or \
          _extract_bin_from_text(full_text, _BUYER_BIN_LABELS)
    if not sup or not buy:
        return None
    if sup == buy:
        if allow_equal:
            return _make_item("BIN007", "OK", cfg.get("ok_user", {"title": "БИНы совпадают (разрешено)"}), value=f"{sup}/{buy}")
        return _make_item("BIN007", cfg.get("level", "WARN"), cfg.get("user", {}), value=f"{sup}/{buy}")
    return _make_item("BIN007", "OK", cfg.get("ok_user", {"title": "БИНы различаются"}), value=f"{sup}/{buy}")

def _rule_D000(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("D000", {})
    v_raw = _first(doc, "issue_date", "date_issue", "document_date", "documentDate",
                   "дата_выписки", "дата_составления", "дата", "Дата",
                   "Document date", "Дата выписки", "Дата составления")
    if not v_raw:
        sec_text, full_text = _get_text_with_fallback(doc)
        v_raw = _extract_header_date(sec_text) or _extract_date_from_text(sec_text) or \
                _extract_header_date(full_text) or _extract_date_from_text(full_text)
    dt = _parse_date_any(v_raw)
    if dt is None:
        return _make_item("D000", cfg.get("level", CONFIG.get("require_date_severity", "ERROR")), cfg.get("user", {}), value=v_raw)
    return _make_item("D000", "OK", {"title": "Дата распознана"}, value=v_raw)

def _rule_D001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("D001", {})
    v_raw = _first(doc, "issue_date", "date_issue", "document_date", "documentDate",
                   "дата_выписки", "дата_составления", "дата", "Дата")
    if not v_raw:
        sec_text, full_text = _get_text_with_fallback(doc)
        v_raw = _extract_header_date(sec_text) or _extract_date_from_text(sec_text) or \
                _extract_header_date(full_text) or _extract_date_from_text(full_text)
    dt = _parse_date_any(v_raw)
    if dt and dt.date() > date.today():
        return _make_item("D001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=v_raw)
    return _make_item("D001", "OK", {"title": "Дата не в будущем"}, value=v_raw)

def _is_suspicious_table_index(num: Optional[float]) -> bool:
    # [2025-11-17] если число целое и в диапазоне 1..12 — похоже на номер колонки
    if num is None:
        return False
    return abs(num - round(num)) < 1e-9 and 1 <= int(round(num)) <= 12

def _rule_TOT001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("TOT001", {})
    val = _first(doc, "total_amount", "total_sum", "total", "amount",
                 "Всего", "Итог", "Сумма документа", "Total",
                 "Итого с НДС", "TotalAmount", "AmountTotal", "Итого к оплате")
    primary_num = _to_number(val) if val != "" else None
    if _is_suspicious_table_index(primary_num):
        val = ""
    if val == "":
        sec_text, full_text = _get_text_with_fallback(doc)
        val = _find_total_value(sec_text) or _find_total_value(full_text) or ""
    if val == "":
        return _make_item("TOT001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=None)
    num = _to_number(val)
    if num is None or num <= 0 or _is_suspicious_table_index(num):
        return _make_item("TOT001", cfg.get("level", "ERROR"), cfg.get("user", {}), value=val)
    return _make_item("TOT001", "OK", {"title": "Итоговая сумма указана корректно"}, value=val)

def _rule_NEG001(doc: Dict[str, Any]) -> Dict[str, Any] | None:
    cfg = RULES.get("NEG001", {})
    val = _first(doc, "total_amount", "total_sum", "total", "amount",
                 "Всего", "Итог", "Сумма документа", "Total",
                 "Итого с НДС", "TotalAmount", "AmountTotal", "Итого к оплате")
    if not val:
        sec_text, full_text = _get_text_with_fallback(doc)
        val = _find_total_value(sec_text) or _find_total_value(full_text)
    if not val:
        return None
    num = _to_number(val)
    if num is None:
        return None
    if num < 0:
        return _make_item("NEG001", cfg.get("level", "WARN"), cfg.get("user", {}), value=val)
    return None

# --------------------------- BIN012 ---------------------------

def _rule_BIN012(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not dict(CONFIG).get("bin_rules", {}).get("bin_checksum_enabled", False):
        return []
    cfg = RULES.get("BIN012", {})
    out: List[Dict[str, Any]] = []
    sec_text, full_text = _get_text_with_fallback(doc)

    def _check(val: str, role: str) -> None:
        if not _is_bin(val):
            return
        if not _kz_mod11_checksum_valid(val):
            user = cfg.get("user", {}).copy()
            user["title"] = f"{user.get('title', 'Ошибка контрольной суммы')} ({role})"
            out.append(_make_item("BIN012", cfg.get("level", "ERROR"), user, value=val))
        else:
            out.append(_make_item("BIN012", "OK",
                                  {"title": f"Контрольная сумма БИН {role}: ОК"}, value=val))

    sup = _first(doc, "supplier_BIN", "supplier_bin", "supplierBin", "seller_BIN", "seller_bin", "sellerBin") or \
          _extract_bin_from_text(sec_text, _SUPPLIER_BIN_LABELS) or \
          _extract_bin_from_text(full_text, _SUPPLIER_BIN_LABELS)
    buy = _first(doc, "recipient_BIN", "recipient_bin", "recipientBin",
                 "buyer_BIN", "buyer_bin", "buyerBin",
                 "customer_BIN", "customer_bin", "customerBin") or \
          _extract_bin_from_text(sec_text, _BUYER_BIN_LABELS) or \
          _extract_bin_from_text(full_text, _BUYER_BIN_LABELS)

    _check(sup, "поставщика")
    _check(buy, "покупателя")
    return out

# --------------------------- движок ---------------------------

_RULE_FUNCS_SEQ = [
    _rule_BIN001, _rule_BIN002, _rule_BIN007, _rule_D000, _rule_D001, _rule_TOT001, _rule_NEG001
]

def run_all_rules(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    # [2025-11-18] refactor(mini): нормализуем вход, чтобы e2e-данные были единообразны
    doc = utils.normalize_keys(doc or {})

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
                "user": {
                    "title": "Внутренняя ошибка правила",
                    "description": f"{fn.__name__}: {e}",
                    "recommendation": "Сообщите разработчику."
                }
            })
    try:
        results.extend(_rule_BIN012(doc))
    except Exception as e:
        results.append({
            "code": "BIN012",
            "level": "ERROR",
            "user": {
                "title": "Внутренняя ошибка правила",
                "description": f"BIN012: {e}",
                "recommendation": "Сообщите разработчику."
            }
        })
    return results
