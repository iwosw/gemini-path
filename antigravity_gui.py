"""Small Windows UI for the optional Antigravity client-gate experiment."""

from pathlib import Path
import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

import antigravity_patch as patcher
import browser_route


STATE_DIR = patcher.state_dir()
BG = "#101521"
PANEL = "#1b2433"
FIELD = "#222e40"
TEXT = "#eff5ff"
MUTED = "#a5b4ca"
CYAN = "#67dce5"
GREEN = "#80e0af"
AMBER = "#f5c27b"
RED = "#ff8f92"


def display_state(state, has_record):
    """Presentation and allowed actions; restore is available for old records."""
    if state == "other":
        return "Патч относится к другому файлу", AMBER, False, False
    if state == "missing":
        return "Antigravity не найден", MUTED, False, False
    if state == "unsupported":
        return "Версия не поддерживается", RED, False, has_record
    if has_record and state == "stock":
        return "После обновления — проверь откат", AMBER, False, True
    if state == "stock":
        return "Исходный файл · готов к патчу", GREEN, True, False
    if has_record:
        return "Патч установлен · откат доступен", CYAN, False, True
    return "Файл изменён вне GeminiPath", RED, False, False


def state_for_target(target, state_dir):
    record = state_dir / "antigravity.json"
    if record.exists():
        try:
            saved = json.loads(record.read_text(encoding="utf-8"))
            if os.path.normcase(saved["target"]) != os.path.normcase(str(target.resolve())):
                return "other", False
        except (ValueError, OSError, KeyError):
            return "unsupported", True
    has_record = record.exists()
    if not target.is_file():
        return "missing", has_record
    try:
        state, _ = patcher.inspect(target.read_bytes())
    except (ValueError, OSError):
        state = "unsupported"
    return state, has_record


class PatcherWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("GeminiPath · Antigravity")
        if getattr(sys, "frozen", False):
            icon = Path(sys.executable).with_name("GeminiPath.ico")
            if icon.is_file():
                try:
                    self.root.iconbitmap(str(icon))
                except tk.TclError:
                    pass
        self.root.geometry("770x730")
        self.root.minsize(680, 660)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.target = patcher.default_target()
        self.events = queue.Queue()
        self.busy = False
        self.can_patch = False
        self.can_restore = False
        self._build()
        self.root.after(90, self.poll)
        self.run("scan")

    def _label(self, parent, text, size=11, color=TEXT, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"),
                        anchor="w", **kwargs)

    def _button(self, parent, text, action, color, foreground=BG):
        return tk.Button(parent, text=text, command=action, bg=color, fg=foreground,
                         activebackground=color, activeforeground=foreground,
                         relief="flat", bd=0, cursor="hand2", padx=18, pady=10,
                         font=("Segoe UI", 11, "bold"), disabledforeground=MUTED)

    def _build(self):
        body = tk.Frame(self.root, bg=BG, padx=32, pady=25)
        body.pack(fill="both", expand=True)
        self._label(body, "GEMINIPATH    /    ЛОКАЛЬНЫЙ РЕЖИМ", 10, CYAN, True).pack(fill="x")
        self._label(body, "Antigravity Patcher", 24, TEXT, True).pack(fill="x", pady=(6, 0))
        self._label(body, "Проверка, резервная копия и откат — без командной строки.",
                    11, MUTED).pack(fill="x", pady=(2, 20))

        panel = tk.Frame(body, bg=PANEL, padx=22, pady=19)
        panel.pack(fill="x")
        self._label(panel, "СОСТОЯНИЕ ПРИЛОЖЕНИЯ", 9, MUTED, True).pack(fill="x")
        self.status = self._label(panel, "Проверяем файл…", 16, AMBER, True)
        self.status.pack(fill="x", pady=(8, 13))
        self._label(panel, "ИСПОЛНЯЕМЫЙ ФАЙЛ", 9, MUTED, True).pack(fill="x")
        path_row = tk.Frame(panel, bg=PANEL)
        path_row.pack(fill="x", pady=(5, 0))
        self.path_label = tk.Label(path_row, text=str(self.target), bg=FIELD, fg=TEXT,
                                   anchor="w", padx=9, pady=8, font=("Segoe UI", 9))
        self.path_label.pack(side="left", fill="x", expand=True)
        self.browse_button = self._button(path_row, "Выбрать…", self.browse, FIELD, TEXT)
        self.browse_button.pack(side="right", padx=(8, 0))

        controls = tk.Frame(body, bg=BG)
        controls.pack(fill="x", pady=(18, 10))
        self.scan_button = self._button(controls, "Проверить", lambda: self.run("scan"), FIELD, TEXT)
        self.scan_button.pack(side="left", padx=(0, 8))
        self.patch_button = self._button(controls, "Применить патч", lambda: self.run("patch"), CYAN)
        self.patch_button.pack(side="left", padx=(0, 8))
        self.restore_button = self._button(controls, "Откатить", lambda: self.run("restore"), AMBER)
        self.restore_button.pack(side="left")

        website = tk.Frame(body, bg=PANEL, padx=20, pady=15)
        website.pack(fill="x", pady=(1, 12))
        self._label(website, "САЙТ GEMINI · БЕЗ ПЛАТНОГО VPN", 10, CYAN, True).pack(fill="x")
        self._label(website, "Отдельный профиль Chrome/Edge · бесплатный SNI-шлюз · Google TLS",
                    10, MUTED).pack(fill="x", pady=(3, 10))
        self.website_button = self._button(
            website, "Открыть Gemini в браузере", lambda: self.run("browser"), FIELD, TEXT)
        self.website_button.pack(anchor="w")

        self.progress = ttk.Progressbar(body, mode="indeterminate")
        self.progress.pack(fill="x", pady=(2, 13))
        self._label(body, "ПОЛЕЗНО ЗНАТЬ", 9, MUTED, True).pack(fill="x")
        self._label(body, "Перед патчем полностью закрой Antigravity. Если Google отклонит запрос\n"
                    "на сервере, изменение клиента этого не исправит.",
                    10, MUTED, justify="left").pack(fill="x", pady=(5, 13))
        self._label(body, "СОБЫТИЯ", 9, MUTED, True).pack(fill="x")
        self.log = tk.Text(body, height=6, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                           relief="flat", bd=0, wrap="word", padx=12, pady=11,
                           font=("Consolas", 10), state="disabled", takefocus=0)
        self.log.pack(fill="both", expand=True, pady=(6, 0))
        self._log("Доступные действия определяются по файлу и резервной копии.")
        self._set_busy(False)

    def _log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, value):
        self.busy = value
        self.scan_button.configure(state="disabled" if value else "normal")
        self.patch_button.configure(state="normal" if self.can_patch and not value else "disabled")
        self.restore_button.configure(state="normal" if self.can_restore and not value else "disabled")
        self.browse_button.configure(state="disabled" if value else "normal")
        self.website_button.configure(state="disabled" if value else "normal")
        if value:
            self.progress.start(12)
        else:
            self.progress.stop()

    def browse(self):
        name = filedialog.askopenfilename(title="Выбери language_server.exe",
                                          filetypes=[("Antigravity language server", "language_server.exe")])
        if name:
            self.target = Path(name)
            self.path_label.configure(text=str(self.target))
            self.run("scan")

    def run(self, operation):
        if self.busy:
            return
        self.status.configure(text="Проверяем маршрут…" if operation == "browser" else "Выполняется: " + operation + "…", fg=AMBER)
        self._set_busy(True)
        target = self.target

        def work():
            try:
                if operation == "browser":
                    message = browser_route.open_site()
                elif operation == "patch":
                    result = patcher.patch_file(target, STATE_DIR)
                    message = "Патч готов. Резервная копия: " + result["backup"]
                elif operation == "restore":
                    outcome = patcher.restore_file(target, STATE_DIR)
                    message = {
                        "restored": "Исходный файл восстановлен.",
                        "already restored": "Исходный файл уже на месте.",
                        "the app updated itself; current stock executable kept unchanged":
                            "Antigravity обновился; новая версия сохранена без изменений.",
                    }.get(outcome, outcome)
                else:
                    message = "Файл проверен, изменений нет."
                success = True
            except Exception as error:
                success = False
                message = str(error)
            state, has_record = state_for_target(target, STATE_DIR)
            self.events.put((success, message, state, has_record))

        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                success, message, state, has_record = self.events.get_nowait()
                if not success:
                    self._log("Ошибка: " + message)
                else:
                    self._log(message)
                title, color, self.can_patch, self.can_restore = display_state(state, has_record)
                self.status.configure(text=title, fg=color)
                self._set_busy(False)
        except queue.Empty:
            pass
        self.root.after(90, self.poll)

    def close(self):
        if self.busy:
            self._log("Дождись окончания операции перед закрытием окна.")
            return
        self.root.destroy()


def main():
    root = tk.Tk()
    PatcherWindow(root)
    root.mainloop()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        patcher.default_target()
        patcher.state_dir()
        tk.Tcl()
    else:
        main()
