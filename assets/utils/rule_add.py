# ============================================================
# rule_add.py — ULYULYU Rule Tool v1.0
# 2025-11-12: добавление нового правила в checklist_full_v2.7.json
# ============================================================

import json
import argparse
import datetime
import shutil
import os

RULES_PATH = "ulyuly_checker/core/rules/checklist_full_v2.7.json"
LOG_PATH = "ulyuly_checker/core/rules/rules_log.txt"

def add_rule(code, level, title, description, details, suggestion, recommendation):
    if not os.path.exists(RULES_PATH):
        print("❌ checklist_full_v2.7.json не найден.")
        return

    # резервная копия
    backup = RULES_PATH.replace(".json", f"_backup_{datetime.date.today()}.json")
    shutil.copy(RULES_PATH, backup)

    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rules = data.get("rules", {})
    if code in rules:
        print(f"⚠️ Правило {code} уже существует.")
        return

    rules[code] = {
        "level": level.upper(),
        "system": {
            "message": description,
            "details": details,
            "suggestion": suggestion
        },
        "user": {
            "title": title,
            "description": description,
            "recommendation": recommendation
        }
    }

    data["rules"] = rules

    with open(RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open(LOG_PATH, "a", encoding="utf-8") as log:
        log.write(f"[{datetime.datetime.now()}] ADD {code}\n")

    print(f"✅ Правило {code} добавлено успешно.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Добавление нового правила в checklist")
    parser.add_argument("--code", required=True, help="Код правила (например, BIN003)")
    parser.add_argument("--level", required=True, help="Уровень (ERROR/WARN/INFO)")
    parser.add_argument("--title", required=True, help="Заголовок для пользователя")
    parser.add_argument("--description", required=True, help="Описание ошибки")
    parser.add_argument("--details", default="", help="Технические детали")
    parser.add_argument("--suggestion", default="", help="Совет на уровне system")
    parser.add_argument("--recommendation", default="", help="Рекомендация пользователю")
    args = parser.parse_args()

    add_rule(
        args.code, args.level, args.title,
        args.description, args.details,
        args.suggestion, args.recommendation
    )
