# 2025-11-07: ULYULYU Checker v1.9.8 — drag-and-drop, подсветка, мультизагрузка
# 2025-11-08: RU UI + скрываем технические коды в GUI (коды в логах)
# 2025-11-12: reason: reset-before-parse — жёсткий сброс состояния перед разбором нового файла,
#                             чтобы исключить «протекание» полей между документами.
# 2025-11-08: reason: импорт ядра — сузили перехват ошибок до ImportError и показываем причину,
#                             чтобы не включался «тихий» фолбэк при ошибках в rules_engine/validator.
# 2025-11-08: reason: ГРУППИРОВКА ВЫВОДА — сводный вывод по группам (BIN/DATE/SUM...),
#                             заголовок группы с главным сообщением и списком деталей ниже.
# 2025-11-08: reason: (NEW) user-mode compact — добавлен флаг CONFIG.show_group_details_in_user_mode,
#                             позволяющий скрывать детали в режиме "user".
# 2025-11-08: reason: (NEW) hot toggle — добавлено меню «Режим» с переключателем
#                             Инспектор/Пользователь и опцией «Показывать детали в user-режиме»
#                             без перезапуска приложения (мгновенный перерасчёт вывода).

import os
import json
import pathlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import re

# === попытка подключить DnD ===
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    root = TkinterDnD.Tk()
except Exception:
    DND_FILES = None
    class _Root(tk.Tk): pass
    root = _Root()

def _level_prefix(level: str) -> str:
    lvl = str(level or "").upper()
    if lvl in ("ERR", "ERROR"): return "ERROR"
    if lvl in ("WARN", "WARNING"): return "WARN"
    return "INFO"

# Русские подписи уровней
def _level_label_ru(tag: str) -> str:
    t = (tag or "").upper()
    if t == "ERROR": return "Ошибка"
    if t == "WARN":  return "Предупреждение"
    if t == "OK":    return "ОК"
    return "Информация"

# --- Импорт ядра ---
try:
    from core import pdf_reader, xlsx_reader
    from core.validator import validate_document, ValidationResult
except ImportError as e:  # 2025-11-08: сузили перехват до ImportError
    class ValidationResult:
        def __init__(self, code, level, message):
            self.code, self.level, self.message = code, level, message
    def validate_document(content, template=None):
        # 2025-11-08: меняем поведение фолбэка — показываем проблему импорта
        return [ValidationResult("FALLBACK", "ERROR",
                 f"Не удалось загрузить ядро валидации ({e.__class__.__name__}: {e}).")]

# ============================= CONFIG =============================
# 2025-11-08: reason: загружаем config.json в GUI — для карт групп (названия, порядок, префиксы)
def _project_root() -> str:
    return os.path.abspath(os.path.dirname(__file__))

def _load_config() -> dict:
    candidates = [
        os.path.join(_project_root(), "config.json"),
        os.path.join(os.path.dirname(__file__), "config.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

CONFIG = _load_config()
GROUPS_CFG = CONFIG.get("groups", {})  # может быть пустым — тогда авто-группировка
MODE = (CONFIG.get("mode") or "user").lower()
SHOW_DETAILS_USER = bool(CONFIG.get("show_group_details_in_user_mode", False))

# Хранилище последнего результата для мгновенного перерендера при переключении режима
_last_results = None
_last_header = None

# ============================= GUI =============================
root.title("УЛЮЛЮ Checker — Inspector Edition (Drag-and-Drop)")
root.geometry("860x640")

style = ttk.Style(); style.theme_use("clam")
OK_COLOR, WARN_COLOR, ERR_COLOR, OPT_COLOR = "#1f7a1f", "#c47f00", "#c62828", "#6b6b6b"

main = ttk.Frame(root, padding=10); main.pack(fill="both", expand=True)
btns = ttk.Frame(main); btns.pack(fill="x", pady=(0,10))
status_var = tk.StringVar(value="Готов")
status_bar = ttk.Label(main, textvariable=status_var, anchor="w")
status_bar.pack(fill="x", pady=(6,8))

# Меню (горячее переключение режима)
menubar = tk.Menu(root)
menu_mode = tk.Menu(menubar, tearoff=0)
inspector_var = tk.BooleanVar(value=(MODE == "inspector"))
show_details_user_var = tk.BooleanVar(value=SHOW_DETAILS_USER)

def _rerender_if_possible():
    if _last_results is not None and _last_header is not None:
        _insert_results_grouped(_last_results, _last_header)

def _on_toggle_inspector():
    global MODE
    MODE = "inspector" if inspector_var.get() else "user"
    _rerender_if_possible()

def _on_toggle_show_details_user():
    global SHOW_DETAILS_USER
    SHOW_DETAILS_USER = bool(show_details_user_var.get())
    _rerender_if_possible()

menu_mode.add_checkbutton(
    label="Инспекторский режим",
    onvalue=True, offvalue=False,
    variable=inspector_var,
    command=_on_toggle_inspector
)
menu_mode.add_checkbutton(
    label="Показывать детали в user-режиме",
    onvalue=True, offvalue=False,
    variable=show_details_user_var,
    command=_on_toggle_show_details_user
)
menubar.add_cascade(label="Режим", menu=menu_mode)
root.config(menu=menubar)

# Поле вывода
output = tk.Text(main, wrap="word", height=26)
output.pack(fill="both", expand=True)
output.tag_configure("OK", foreground=OK_COLOR)
output.tag_configure("INFO", foreground=OK_COLOR)
output.tag_configure("WARN", foreground=WARN_COLOR)
output.tag_configure("ERROR", foreground=ERR_COLOR)
output.tag_configure("OPTIONAL", foreground=OPT_COLOR)
output.tag_configure("SUMMARY", font=("Arial",10,"bold"))
output.tag_configure("GROUP", font=("Arial",10,"bold"))
output.tag_configure("MUTED", foreground="#666666")
progress = ttk.Progressbar(main, mode="indeterminate")

# Кнопки
def _open_file():
    path = filedialog.askopenfilename(filetypes=[
        ("Документы", "*.pdf;*.xls;*.xlsx;*.json"),
        ("PDF", "*.pdf"), ("Excel", "*.xls;*.xlsx"), ("JSON", "*.json")
    ])
    if path:
        _start_check(path)

ttk.Button(btns, text="Открыть файл…", command=_open_file).pack(side="left")
ttk.Button(btns, text="Очистить", command=lambda: output.delete(1.0, tk.END)).pack(side="left", padx=6)

# ===============================================================
# Drag & Drop
# ===============================================================
def _handle_drop(event):
    files = root.tk.splitlist(event.data)
    for file in files:
        ext = pathlib.Path(file).suffix.lower()
        if ext in (".pdf", ".xls", ".xlsx", ".json"):
            _start_check(file)
        else:
            messagebox.showwarning("УЛЮЛЮ Checker", f"Формат не поддерживается: {ext}")

def _drag_enter(event):
    status_var.set("Отпустите файл, чтобы начать проверку…")

def _drag_leave(event):
    status_var.set("Готов")

# ===============================================================
# Проверка файла (фоновый поток)
# ===============================================================
def _start_check(file_path: str):
    output.delete(1.0, tk.END)
    status_var.set("Чтение файла…")
    progress.pack(fill="x", pady=6); progress.start()
    t = threading.Thread(target=_check_worker, args=(file_path,), daemon=True)
    t.start()

def _check_worker(file_path: str):
    global _last_results, _last_header
    try:
        data = _read_any(file_path)
        if isinstance(data, dict) and "error" in data:
            _ui_err(data["error"]); return
        tpl_data = {}
        try:
            base = pathlib.Path(file_path)
            cand = [base.with_suffix(".json"),
                    base.parent / "esf_template.json"]
            tpl_path = next((str(p) for p in cand if p.exists()), None)
            if tpl_path:
                with open(tpl_path, "r", encoding="utf-8") as f:
                    tpl_data = json.load(f)
        except Exception:
            tpl_data = {}
        res = validate_document(data, tpl_data)
        header = f"Файл: {os.path.basename(file_path)} | Размер: {human_size(os.path.getsize(file_path))}"
        _last_results, _last_header = res, header
        root.after(0, lambda: _insert_results_grouped(res, header))
    except Exception as e:
        _ui_err(f"Ошибка при обработке: {e}")
    finally:
        root.after(0, lambda: (progress.stop(), progress.pack_forget(), status_var.set("Готов")))

def _ui_err(msg: str):
    messagebox.showerror("УЛЮЛЮ Checker", msg)

def _read_any(path: str):
    content = {}
    ext = pathlib.Path(path).suffix.lower()
    if ext == ".pdf":
        parsed = pdf_reader.parse_pdf_content(path)
    elif ext in (".xls",".xlsx"):
        parsed = xlsx_reader.extract_data(path)
    elif ext==".json":
        with open(path, "r", encoding="utf-8") as f:
            parsed = json.load(f)
    else:
        return {"error":f"Неподдерживаемый формат {ext}"}
    if isinstance(parsed, dict):
        content.update(parsed)
    return content

# ===============================================================
# ГРУППИРОВАННЫЙ ВЫВОД
# ===============================================================
_SEVERITY_RANK = {"ERROR": 3, "WARN": 2, "WARNING": 2, "INFO": 1, "OK": 1}

def _code_prefix(code: str) -> str:
    if not code: return "OTHER"
    m = re.match(r"([A-Za-z]+)", str(code))
    return m.group(1).upper() if m else "OTHER"

def _map_group(code: str) -> str:
    # если в конфиге задана карта prefixes → группа
    for gk, gval in GROUPS_CFG.items():
        pfxs = gval.get("prefixes")
        if pfxs:
            for p in pfxs:
                if str(code).upper().startswith(str(p).upper()):
                    return gk
    # авто-правила по умолчанию
    p = _code_prefix(code)
    if p in ("TOT", "NEG"): return "SUM"
    if p == "D": return "DATE"
    return p

def _group_title(gk: str) -> str:
    g = GROUPS_CFG.get(gk, {})
    return g.get("title") or {
        "BIN": "Идентификаторы контрагентов",
        "DATE": "Даты документа",
        "SUM": "Суммы и итоги",
    }.get(gk, gk)

def _group_order_key(gk: str) -> tuple:
    g = GROUPS_CFG.get(gk, {})
    order = g.get("order")
    return (int(order), gk) if order is not None else (9999, gk)

def _best_item(items):
    # 1) по тяжести
    best = None
    for it in items:
        lvl = _SEVERITY_RANK.get(str(getattr(it, "level", "INFO")).upper(), 0)
        if best is None or lvl > _SEVERITY_RANK.get(str(getattr(best, "level", "INFO")).upper(), 0):
            best = it
    # 2) при равной тяжести — по group_priorities (если есть)
    if best is not None and "group_priorities" in CONFIG:
        gk = _map_group(getattr(best, "code", ""))
        order = CONFIG["group_priorities"].get(gk)
        if order:
            def _prio(it):
                code = str(getattr(it, "code", ""))
                try:
                    return order.index(code)
                except ValueError:
                    return 999
            items_sorted = sorted(items, key=lambda it: (_SEVERITY_RANK.get(str(getattr(it,"level","INFO")).upper(),0)*-1, _prio(it)))
            best = items_sorted[0]
    return best

def _insert_results_grouped(results, header: str):
    output.delete(1.0, tk.END)
    output.insert(tk.END, header+"\n"+"—"*90+"\n")

    # группируем
    groups = {}
    for r in results:
        gk = _map_group(getattr(r, "code", ""))
        groups.setdefault(gk, []).append(r)

    # общий вердикт
    any_err = any(str(getattr(r, "level","")).upper() in ("ERR","ERROR") for r in results)
    any_warn = any(str(getattr(r, "level","")).upper() in ("WARN","WARNING") for r in results)
    if any_err:
        bad_groups = [gk for gk, items in groups.items() if any(str(getattr(x,"level","")).upper() in ("ERR","ERROR") for x in items)]
        output.insert(tk.END, f"❌ Нужны исправления: {len(bad_groups)} категорий с ошибками ({', '.join(bad_groups)})\n", "SUMMARY")
    elif any_warn:
        output.insert(tk.END, "⚠ Есть предупреждения (не блокирует отправку).\n", "SUMMARY")
    else:
        output.insert(tk.END, "✅ Чики-пыки: критичных ошибок нет.\n", "SUMMARY")

    output.insert(tk.END,"—"*90+"\n",())

    # выводим группы по порядку
    for gk in sorted(groups.keys(), key=_group_order_key):
        items = groups[gk]
        title = _group_title(gk)
        # главный элемент
        main_item = _best_item(items) or items[0]
        lvl_raw = str(getattr(main_item, "level", "INFO")).upper()
        tag = "ERROR" if lvl_raw in ("ERR","ERROR") else ("WARN" if lvl_raw in ("WARN","WARNING") else "OK")
        icon = "✖" if tag=="ERROR" else ("⚠" if tag=="WARN" else "☑")
        ru = _level_label_ru(tag)
        output.insert(tk.END, f"{title}\n", "GROUP")
        output.insert(tk.END, f"{icon} {ru}: {getattr(main_item,'message','').strip()}\n", tag)

        # режимы отображения деталей
        show_details = True
        if MODE == "user" and not SHOW_DETAILS_USER:
            show_details = False

        if show_details:
            for it in items:
                if it is main_item:
                    continue
                lvl = str(getattr(it, "level","INFO")).upper()
                tag2 = "ERROR" if lvl in ("ERR","ERROR") else ("WARN" if lvl in ("WARN","WARNING") else "INFO")
                output.insert(tk.END, f"   • {getattr(it,'message','').strip()}\n", tag2)

        output.insert(tk.END, "—"*60+"\n", "MUTED")

    # сводка по количеству
    ok = sum(1 for r in results if str(getattr(r,"level","")).upper() not in ("ERR","ERROR","WARN","WARNING"))
    warn = sum(1 for r in results if str(getattr(r,"level","")).upper() in ("WARN","WARNING"))
    err = sum(1 for r in results if str(getattr(r,"level","")).upper() in ("ERR","ERROR"))
    output.insert(tk.END,f"✅ ОК: {ok}   ⚠ Предупреждения: {warn}   ❌ Ошибки: {err}\n","SUMMARY")

def human_size(n:int)->str:
    for unit in ("Б","КБ","МБ","ГБ"):
        if n<1024: return f"{n} {unit}"
        n//=1024
    return f"{n} ТБ"

# DnD зона + футер
frame_dnd = tk.LabelFrame(main,text="Перетащите сюда PDF / Excel / JSON",bg="#f0f0f0",height=100)
frame_dnd.pack(fill="x",pady=10)
frame_dnd.pack_propagate(False)
ttk.Label(main,text="© 2025 УЛЮЛЮ Systems",font=("Arial",8)).pack(side="bottom",pady=4)

if DND_FILES:
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<Drop>>', _handle_drop)
    root.dnd_bind('<<DragEnter>>', _drag_enter)
    root.dnd_bind('<<DragLeave>>', _drag_leave)

if __name__ == "__main__":
    root.mainloop()
