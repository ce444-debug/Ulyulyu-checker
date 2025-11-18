# pdf_reader.py — ULYULYU CHECKER
# Версия: v2.2 (Pattern Reference Integrated Edition)
# Автор: frukt22
# Дата: 2025-11-09
# [2025-11-18] refactor(mini): после извлечения — normalize_keys() из core.utils;
#                поведение поиска БИН/дат/итогов не изменял.

import re
import os
import unicodedata
from typing import Dict, Any
from PyPDF2 import PdfReader

from . import utils  # [2025-11-18] канон полей и ISO-даты

# ------------------------------------------------------------
# 🧩 Основная функция
# ------------------------------------------------------------
def parse_pdf_content(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        try:
            text += page.extract_text() + "\n"
        except Exception:
            continue

    # ------------------------------------------------------------
    # 🧹 Нормализация текста
    # ------------------------------------------------------------
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00A0", " ")  # неразрывный пробел
    text = text.replace("•", ".").replace("\uf0b7", ".")  # bullet
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\n+", "\n", text).strip()

    # ------------------------------------------------------------
    # 🔍 БИН — поставщик и покупатель
    # ------------------------------------------------------------
    supplier_bin = ""
    buyer_bin = ""

    BIN_SUP_PATTERNS = [
        r"БИН[^\n]{0,10}поставщик[^\d]{0,10}([0-9]{11,12})",
        r"БИН[^\n]{0,5}\(?поставщика\)?[^\d]{0,10}([0-9]{11,12})",
        r"БИНПоставщик[^\d]{0,10}([0-9]{11,12})",
        r"БИН[^0-9]{0,5}[№:–-]?\s*([0-9]{11,12})",  # БИН № ...
        r"ИНН\s*/\s*БИН[:\s]*([0-9]{11,12})",
        r"РНН/БИН[^\d]{0,10}([0-9]{11,12})",
    ]
    BIN_BUY_PATTERNS = [
        r"БИН[^\n]{0,10}покупател[^\d]{0,10}([0-9]{11,12})",
        r"БИН[^\n]{0,5}\(?покупателя\)?[^\d]{0,10}([0-9]{11,12})",
        r"БИНПокупател[^\d]{0,10}([0-9]{11,12})",
    ]

    for pat in BIN_SUP_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            supplier_bin = m.group(1)
            break

    for pat in BIN_BUY_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            buyer_bin = m.group(1)
            break

    if not supplier_bin or not buyer_bin:
        # fallback — просто взять первые два БИНа подряд
        all_bins = re.findall(r"БИН[^\d]{0,5}([0-9]{11,12})", text, re.IGNORECASE)
        if len(all_bins) >= 1 and not supplier_bin:
            supplier_bin = all_bins[0]
        if len(all_bins) >= 2 and not buyer_bin:
            buyer_bin = all_bins[1]

    # ------------------------------------------------------------
    # 📅 Дата — любые форматы (DD.MM.YYYY, YYYY-MM-DD, “от …”)
    # ------------------------------------------------------------
    date_issue = ""
    DATE_PATTERNS = [
        r"Дата\s*(?:выписки|выставления|формирования)?\s*[:\-–]?\s*([0-9]{1,2}\s*[./-]\s*[0-9]{1,2}\s*[./-]\s*[0-9]{2,4})",
        r"Дата\s*(?:выписки|выставления)?\s*[:\-–]?\s*([0-9]{4}\s*[./-]\s*[0-9]{1,2}\s*[./-]\s*[0-9]{1,2})",
        r"от\s*([0-9]{4}\s*[./-]\s*[0-9]{1,2}\s*[./-]\s*[0-9]{1,2})",
        r"от\s*([0-9]{1,2}\s*[./-]\s*[0-9]{1,2}\s*[./-]\s*[0-9]{2,4})",
        r"Выписан[^\d]{0,5}([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
    ]
    for pat in DATE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            date_issue = m.group(1)
            date_issue = re.sub(r"\s*[./-]\s*", ".", date_issue)
            break

    # ------------------------------------------------------------
    # 💰 Итоговая сумма
    # ------------------------------------------------------------
    total_amount = ""
    SUM_PATTERNS = [
        r"(?:Всего\s*с\s*НДС|Итого\s*с\s*НДС)\s*[:\-–]?\s*([\d\s.,]+)(?:\s*[A-ZА-Яa-zа-я₸]{0,5})?",
        r"(?:Итого\s*к\s*оплате)\s*[:\-–]?\s*([\d\s.,]+)(?:\s*[A-ZА-Яa-zа-я₸]{0,5})?",
        r"(?:Общая\s*сумма)\s*[:\-–]?\s*([\d\s.,]+)",
        r"Всего\s*[:\-–]?\s*([\d\s.,]+)(?:\s*[A-ZА-Яa-zа-я₸]{0,5})?$",
    ]
    matches = []
    for pat in SUM_PATTERNS:
        matches += re.findall(pat, text, re.IGNORECASE)
    if matches:
        total_amount = matches[-1]
        total_amount = (total_amount.replace(" ", "").replace("\u00A0", "").replace(",", ".").strip())

    # ------------------------------------------------------------
    # 📦 Результат
    # ------------------------------------------------------------
    raw = {
        "supplier_BIN": supplier_bin,
        "recipient_BIN": buyer_bin,
        "date_issue": date_issue,
        "total_amount": total_amount,
        "raw_text": text,
    }
    # [2025-11-18] refactor(mini): канон ключей + ISO-дата
    return utils.normalize_keys(raw)

# ------------------------------------------------------------
# CLI-запуск (отладка)
# ------------------------------------------------------------
if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Использование: python pdf_reader.py <путь_к_PDF>")
    else:
        data = parse_pdf_content(sys.argv[1])
        print(json.dumps(data, ensure_ascii=False, indent=2))
