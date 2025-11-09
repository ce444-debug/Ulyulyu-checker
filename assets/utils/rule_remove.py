# ============================================================
# rule_remove.py — ULYULYU Rule Tool v1.0
# 2025-11-12: удаление правила из checklist_full_v2.7.json
# ============================================================

import json
import argparse
import datetime
import shutil
import os

RULES_PATH = "ulyuly_checker/core/rules/checklist_full_v2.7.json"
LOG_PATH = "ulyuly_checker/core/rules/rules_log.txt"

def remove_rule(code):
    if not os.path.exists(RULES_PATH):
        print("❌ checklist_full_v2.7.json не найден.")
        return

    backup = RULES_PATH.replace(".json", f"_backup_{datetime.date.today()}.json")
    shutil.copy(RULES_PATH, backup)

    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rules = data.get("rules", {})
    if code not in rules:
        print(f"⚠️ Правило {code} не найдено.")
        return

    del rules[code]
    data["rules"] = rules

    with open(RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open(LOG_PATH, "a", encoding="utf-8") as log:
        log.write(f"[{datetime.datetime.now()}] REMOVE {code}\n")

    print(f"🗑️ Правило {code} удалено успешно.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Удаление правила из checklist")
    parser.add_argument("--code", required=True, help="Код правила (например, D001)")
    args = parser.parse_args()
    remove_rule(args.code)
