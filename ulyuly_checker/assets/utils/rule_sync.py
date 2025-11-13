# ============================================================
# rule_sync.py — ULYULYU Rule Tool v1.0
# 2025-11-12: синхронизация правил между rules_engine и checklist
# ============================================================

import json
import re
import os

RULES_PATH = "ulyuly_checker/core/rules/checklist_full_v2.7.json"
ENGINE_PATH = "ulyuly_checker/core/rules/rules_engine.py"

def sync_rules():
    if not os.path.exists(RULES_PATH) or not os.path.exists(ENGINE_PATH):
        print("❌ Файлы не найдены.")
        return

    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    checklist_codes = set(data.get("rules", {}).keys())

    with open(ENGINE_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    engine_codes = set(re.findall(r'"([A-Z]{2,5}\d{3})"', text))

    missing_in_json = engine_codes - checklist_codes
    missing_in_engine = checklist_codes - engine_codes

    print("🧩 Сравнение checklist ↔ rules_engine")
    print(f"→ В rules_engine, но нет в checklist: {', '.join(sorted(missing_in_json)) or '—'}")
    print(f"→ В checklist, но нет в rules_engine: {', '.join(sorted(missing_in_engine)) or '—'}")

if __name__ == "__main__":
    sync_rules()
