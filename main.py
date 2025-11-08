# 2025-11-07: ULYULYU Checker v1.9.8
# - добавлен drag-and-drop (tkinterdnd2)
# - визуальная подсветка при наведении
# - множественное перетаскивание файлов
# 2025-11-08: RU UI + скрываем технические коды в GUI
# Причина: показывать типы сообщений по-русски и не отображать технические коды/описания.
#          Коды и детали остаются в логах/отчётах.

import os
import json
import pathlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# === попытка подключить DnD ===
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    root = TkinterDnD.Tk()
    DND_AVAILABLE = True
except ImportError:
    root = tk.Tk()
    DND_AVAILABLE = False
    print("⚠ tkinterdnd2 не установлен — drag & drop недоступен.")

# [2025-11-07] — явные префиксы уровней
def _level_prefix(level: str) -> str:
    lvl = str(level or "").upper()
    if lvl in ("ERR", "ERROR"): return "ERROR"
    if lvl in ("WARN", "WARNING"): return "WARN"
    return "INFO"

# 2025-11-08: русские подписи уровней
def _level_label_ru(tag: str) -> str:
    t = (tag or "").upper()
    if t == "ERROR": return "Ошибка"
    if t == "WARN":  return "Предупреждение"
    if t == "OK":    return "ОК"
    # INFO и прочие
    return "Информация"

# --- Импорт ядра ---
try:
    from core import pdf_reader, xlsx_reader
    from core.validator import validate_document, ValidationResult
except Exception:
    class ValidationResult:
        def __init__(self, code, level, message):
            self.code, self.level, self.message = code, level, message
    def validate_document(content, template):  # fallback
        return [ValidationResult("FALLBACK", "INFO", "✅ Фолбэк-валидация: без ошибок")]

# ============================= GUI =============================
root.title("УЛЮЛЮ Checker — Inspector Edition (Drag-and-Drop)")
root.geometry("860x600")

style = ttk.Style(); style.theme_use("clam")
OK_COLOR, WARN_COLOR, ERR_COLOR, OPT_COLOR = "#1f7a1f", "#c47f00", "#c62828", "#6b6b6b"

main = ttk.Frame(root, padding=10); main.pack(fill="both", expand=True)
btns = ttk.Frame(main); btns.pack(fill="x", pady=(0,10))
status_var = tk.StringVar(value="Готов")
status_bar = ttk.Label(main, textvariable=status_var, anchor="w")
status_bar.pack(fill="x", pady=(6,8))

output = tk.Text(main, wrap="word", height=26)
output.pack(fill="both", expand=True)
output.tag_configure("OK", foreground=OK_COLOR)
output.tag_configure("INFO", foreground=OK_COLOR)
output.tag_configure("WARN", foreground=WARN_COLOR)
output.tag_configure("ERROR", foreground=ERR_COLOR)
output.tag_configure("OPTIONAL", foreground=OPT_COLOR)
output.tag_configure("SUMMARY", font=("Arial",10,"bold"))
progress = ttk.Progressbar(main, mode="indeterminate")

# ===============================================================
# 📦 Drag & Drop логика
# ===============================================================
def _handle_drop(event):
    files = root.tk.splitlist(event.data)
    for file in files:
        ext = pathlib.Path(file).suffix.lower()
        if ext in (".pdf", ".xls", ".xlsx", ".json"):
            _start_check(file)
        else:
            messagebox.showwarning("УЛЮЛЮ Checker", f"Формат не поддерживается: {file}")
    frame_dnd.config(bg="#f0f0f0")

def _drag_enter(event):
    frame_dnd.config(bg="#d0e9ff"); return event.action
def _drag_leave(event):
    frame_dnd.config(bg="#f0f0f0"); return event.action

# ===============================================================
# 🔧 вспомогательные функции
# ===============================================================
def human_size(n): return f"{n/1024/1024:.1f} MB" if n>1024**2 else f"{n/1024:.1f} KB"
def set_status(p,t): status_var.set(f"{os.path.basename(p)} — {t}")
def clear_output(): output.delete(1.0, tk.END); status_var.set("Готов")

def analyze_document(path):
    ext = pathlib.Path(path).suffix.lower()
    if ext==".pdf": return pdf_reader.parse_pdf_content(path)
    if ext in (".xls",".xlsx"): return xlsx_reader.extract_data(path)
    if ext==".json": return json.load(open(path,"r",encoding="utf-8"))
    return {"error":f"Неподдерживаемый формат {ext}"}

# 2025-11-08: обновлённый вывод — без технического кода; русские уровни
def _insert_results(results, header):
    output.delete(1.0, tk.END)
    output.insert(tk.END, header+"\n"+"—"*90+"\n")
    ok=w=err=0
    for r in results:
        lvl_raw = getattr(r,"level","INFO").upper()
        # выбор цветового тега и русской метки уровня
        if lvl_raw in ("ERROR","ERR"):
            tag="ERROR"; icon="✖"; err+=1
        elif lvl_raw in ("WARN","WARNING"):
            tag="WARN"; icon="⚠"; w+=1
        else:
            tag="OK"; icon="☑"; ok+=1  # INFO считаем «ОК/Информация»
        ru = _level_label_ru(tag)
        msg  = getattr(r,"message","").strip()
        # В GUI НЕ показываем технические коды — только человеко-понятный текст
        output.insert(tk.END,f"{icon} {ru}: {msg}\n",tag)
    output.insert(tk.END,"—"*90+"\n",())
    output.insert(tk.END,f"✅ ОК: {ok}   ⚠ Предупреждения: {w}   ❌ Ошибки: {err}\n","SUMMARY")

def _start_check(file_path):
    set_status(file_path,"чтение…")
    progress.pack(fill="x"); progress.start(12)
    output.delete(1.0, tk.END)
    def worker():
        try:
            data = analyze_document(file_path)
            if "error" in data:
                res = [ValidationResult("SYS-FILE","ERROR",data["error"])]
            else:
                tpl = os.path.join(os.path.dirname(__file__),"assets","templates","esf_template.json")
                tpl_data = json.load(open(tpl,"r",encoding="utf-8")) if os.path.exists(tpl) else {}
                res = validate_document(data, tpl_data)
            header = f"Файл: {os.path.basename(file_path)} | Размер: {human_size(os.path.getsize(file_path))}"
            root.after(0, lambda: (_insert_results(res,header), set_status(file_path,"готов")))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("УЛЮЛЮ Checker", f"Ошибка: {e}"))
        finally:
            root.after(0, lambda: (progress.stop(), progress.pack_forget()))
    threading.Thread(target=worker, daemon=True).start()

def open_file():
    f=filedialog.askopenfilename(title="Открыть документ",
        filetypes=[("Документы","*.pdf *.xls *.xlsx *.json"),("Все файлы","*.*")])
    if f: _start_check(f)

# ===============================================================
# 🖼️ GUI элементы
# ===============================================================
ttk.Button(btns,text="Открыть документ",command=open_file,width=25).pack(side="left",padx=6)
ttk.Button(btns,text="Очистить",command=clear_output,width=25).pack(side="left",padx=6)

frame_dnd = tk.LabelFrame(main,text="Перетащите сюда PDF / Excel / JSON",bg="#f0f0f0",height=100)
frame_dnd.pack(fill="x",pady=10)
frame_dnd.pack_propagate(False)
ttk.Label(main,text="© 2025 УЛЮЛЮ Systems",font=("Arial",8)).pack(side="bottom",pady=4)

if DND_AVAILABLE:
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<Drop>>', _handle_drop)
    root.dnd_bind('<<DragEnter>>', _drag_enter)
    root.dnd_bind('<<DragLeave>>', _drag_leave)

if __name__ == "__main__":
    root.mainloop()
