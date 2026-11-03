"""Navy dashboard widgets, drawn locally with Tk; no webview or external assets."""
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk


BG = "#1c203b"
SIDEBAR = "#202440"
CARD = "#272c4e"
CARD_ALT = "#2d3358"
BORDER = "#3b426b"
TEXT = "#f0f1fc"
MUTED = "#a0a8d0"
PURPLE = "#9380ff"
BLUE = "#7f9aff"
CORAL = "#ff919c"
GREEN = "#71d8c2"
INPUT = "#202542"


class ClipboardEntry(ttk.Entry):
    """Explicit paste actions, including Windows shortcuts on non-Latin layouts."""
    def __init__(self, parent, *, secret=False, **kwargs):
        super().__init__(parent, exportselection=False, **kwargs)
        self.secret = secret
        self.bind("<<Paste>>", self.paste)
        self.bind("<Shift-Insert>", self.paste)
        self.bind("<Control-KeyPress>", self._control_key)
        self.bind("<Button-3>", self._context_menu)
        self.bind("<Shift-F10>", self._context_menu)
        self.edit_menu = tk.Menu(self, tearoff=False, bg=CARD_ALT, fg=TEXT,
                                 activebackground=PURPLE, activeforeground=INPUT)
        self.edit_menu.add_command(label="Вставить", command=self.paste)
        self.edit_menu.add_command(label="Выделить всё", command=self.select_all)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Очистить", command=lambda: self.delete(0, "end"))

    def paste(self, event=None, *, replace_all=False):
        if self.instate(("disabled",)) or self.instate(("readonly",)):
            return "break"
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            messagebox.showwarning("Вставка", "В буфере обмена нет доступного текста. Скопируй значение ещё раз.",
                                   parent=self.winfo_toplevel())
            return "break"
        if not text:
            return "break"
        if replace_all:
            self.delete(0, "end")
        elif self.selection_present():
            self.delete("sel.first", "sel.last")
        self.insert("insert", text)
        self.focus_set()
        self.icursor("end")
        return "break"

    def select_all(self):
        self.selection_range(0, "end")
        self.icursor("end")
        return "break"

    def _control_key(self, event):
        # Virtual-key codes stay the same when V/A become Cyrillic м/ф.
        if event.keycode == 86 or event.keysym.lower() == "v":
            return self.paste()
        if event.keycode == 65 or event.keysym.lower() == "a":
            return self.select_all()
        # Never copy a masked bot token to the system clipboard by accident.
        if self.secret and (event.keycode in (67, 88) or event.keysym.lower() in ("c", "x")):
            return "break"
        return None

    def _context_menu(self, event):
        self.focus_set()
        try:
            self.edit_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.edit_menu.grab_release()
        return "break"


def setup_theme(root):
    root.configure(bg=BG)
    root.option_add("*Font", ("Segoe UI", 10))
    root.option_add("*Listbox.background", INPUT)
    root.option_add("*Listbox.foreground", TEXT)
    root.option_add("*Listbox.selectBackground", "#4a477b")
    root.option_add("*Listbox.selectForeground", TEXT)
    root.option_add("*TCombobox*Listbox.background", INPUT)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", "#4a477b")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background=CARD)
    style.configure("TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 10))
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("TButton", background=CARD_ALT, foreground=TEXT, bordercolor=BORDER,
                    lightcolor=CARD_ALT, darkcolor=CARD_ALT, borderwidth=0,
                    padding=(15, 10), font=("Segoe UI", 10))
    style.map("TButton", background=[("disabled", "#2a2e49"), ("active", "#41486f")],
              foreground=[("disabled", "#747c9d")])
    style.configure("Primary.TButton", background=PURPLE, foreground="#17182d", font=("Segoe UI", 10, "bold"))
    style.map("Primary.TButton", background=[("disabled", "#3e3b60"), ("active", "#ad9eff")],
              foreground=[("disabled", "#8e89a8")])
    style.configure("Danger.TButton", background="#593748", foreground="#ffc0c6")
    style.map("Danger.TButton", background=[("disabled", "#302c44"), ("active", "#744453")])
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, fieldbackground=INPUT, foreground=TEXT, background=CARD_ALT,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                        insertcolor=TEXT, arrowcolor=MUTED, padding=9)
        style.map(name, fieldbackground=[("readonly", INPUT), ("disabled", "#252942")],
                  foreground=[("disabled", "#747c9d"), ("readonly", TEXT)],
                  bordercolor=[("focus", PURPLE)])
    style.configure("Horizontal.TProgressbar", troughcolor=INPUT, background=PURPLE,
                    borderwidth=0, lightcolor=PURPLE, darkcolor=PURPLE)
    style.configure("Horizontal.TScale", background=CARD, troughcolor=INPUT, borderwidth=0)
    style.configure("TRadiobutton", background=CARD, foreground=TEXT, indicatorbackground=INPUT,
                    indicatorcolor=PURPLE, padding=5)
    style.map("TRadiobutton", background=[("active", CARD)], foreground=[("disabled", MUTED)])
    style.configure("Vertical.TScrollbar", background=CARD_ALT, troughcolor=INPUT,
                    borderwidth=0, arrowcolor=MUTED, lightcolor=CARD_ALT, darkcolor=CARD_ALT,
                    bordercolor=CARD_ALT)
    style.map("Vertical.TScrollbar", background=[("active", "#5b608a"), ("!active", CARD_ALT)])
    style.configure("TSeparator", background=BORDER)
    root.after(0, lambda: dark_titlebar(root))


def dark_titlebar(window):
    try:
        import ctypes
        value = ctypes.c_int(1)
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError):
        pass


def label(parent, text="", size=10, color=TEXT, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                    font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)


def panel(parent, title, subtitle=None):
    outer = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    heading = tk.Frame(outer, bg=CARD)
    heading.pack(fill="x", padx=20, pady=(16, 10))
    label(heading, title, 11, bold=True).pack(anchor="w")
    if subtitle:
        label(heading, subtitle, 9, MUTED, wraplength=700, justify="left").pack(anchor="w", pady=(4, 0))
    content = tk.Frame(outer, bg=CARD)
    content.pack(fill="both", expand=True, padx=20, pady=(0, 18))
    return outer, content


class Metric(tk.Frame):
    def __init__(self, parent, title, accent, footnote):
        super().__init__(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        self.accent = accent
        bar = tk.Frame(self, bg=accent, width=3)
        bar.pack(side="left", fill="y")
        inner = tk.Frame(self, bg=CARD)
        inner.pack(fill="both", expand=True, padx=18, pady=10)
        label(inner, title.upper(), 9, MUTED).pack(anchor="w")
        self.value = label(inner, "—", 25, accent)
        self.value.pack(anchor="w", pady=1)
        label(inner, footnote, 9, MUTED).pack(anchor="w")

    def set(self, text):
        self.value.config(text=text)


class LiveChart(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, bg=CARD, highlightthickness=0, height=195)
        self.history = deque(maxlen=600)
        self.threshold = 0.78
        self.bind("<Configure>", self.draw)

    def push(self, level, score):
        now = time.monotonic()
        self.history.append((now, max(0, min(1, level / 100)), max(0, min(1, score))))
        while self.history and self.history[0][0] < now - 30:
            self.history.popleft()
        self.draw()

    def draw(self, *_):
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        left, top, right, bottom = 34, 14, width - 12, height - 30
        if right <= left or bottom <= top:
            return
        for tick in (0, 0.5, 1):
            y = bottom - tick * (bottom - top)
            self.create_line(left, y, right, y, fill=BORDER, dash=(2, 5))
            self.create_text(left - 9, y, text=str(round(tick * 100)), anchor="e", fill=MUTED, font=("Segoe UI", 8))
        y = bottom - self.threshold * (bottom - top)
        self.create_line(left, y, right, y, fill="#78699e", dash=(5, 5))
        self.create_text(right, y - 9, text=f"порог {self.threshold:.0%}", anchor="e", fill="#baabe0", font=("Segoe UI", 8))
        self.create_text(left, height - 10, text="30 с истории", anchor="w", fill=MUTED, font=("Segoe UI", 8))
        self.create_text(right, height - 10, text="сейчас", anchor="e", fill=MUTED, font=("Segoe UI", 8))
        if not self.history:
            self.create_text((left + right) / 2, (top + bottom) / 2, text="Здесь появится живой сигнал",
                             fill=MUTED, font=("Segoe UI", 11))
            return
        for channel, color in ((0, BLUE), (1, CORAL)):
            points = []
            for sample in self.history:
                x = right - (self.history[-1][0] - sample[0]) / 30 * (right - left)
                points.extend((x, bottom - sample[channel + 1] * (bottom - top)))
            if len(points) >= 4:
                if channel == 0:
                    self.create_polygon(points[0], bottom, *points, points[-2], bottom,
                                        fill="#353f70", outline="")
                self.create_line(*points, fill=color, width=2, smooth=False)
            elif points:
                x, y = points
                self.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline="")


class Radar(tk.Canvas):
    """Small decorative brand mark, not a fabricated audio reading."""
    def __init__(self, parent):
        super().__init__(parent, width=46, height=46, bg=SIDEBAR, highlightthickness=0)
        for radius, color in ((20, "#4c477b"), (13, "#635a9e"), (5, PURPLE)):
            self.create_oval(23 - radius, 23 - radius, 23 + radius, 23 + radius, outline=color, width=2)
        self.create_line(23, 23, 37, 10, fill=CORAL, width=2)
        self.create_oval(33, 11, 38, 16, fill=CORAL, outline="")


def sample_title(path):
    name = path.stem
    for key, title in (("krasnaya", "Красная удочка"), ("sinaya", "Синяя удочка"), ("zelenaya", "Зелёная удочка")):
        if name.startswith(f"positive_{key}_"):
            return f"{title}   /   образец {name.rsplit('_', 1)[-1]}"
    kind = "Не поклёвка" if name.startswith("negative_") else "Поклёвка"
    return f"{kind}   /   {path.name}"


def build_dashboard(app):
    setup_theme(app)
    app.detection_count = 0
    app.sample_summary = tk.StringVar(value="Образцы ещё не загружены")
    app.telegram_state = tk.StringVar(value="Не проверен")
    app.last_event = tk.StringVar(value="Поклёвок пока не было")
    app.page_title = tk.StringVar(value="Обзор")
    app.page_subtitle = tk.StringVar(value="Всё под контролем. Остаётся дождаться поклёвки.")

    shell = tk.Frame(app, bg=BG)
    shell.pack(fill="both", expand=True)
    sidebar = tk.Frame(shell, bg=SIDEBAR, width=220)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)
    brand = tk.Frame(sidebar, bg=SIDEBAR)
    brand.pack(fill="x", padx=22, pady=(30, 26))
    Radar(brand).pack(side="left", padx=(0, 9))
    brand_text = tk.Frame(brand, bg=SIDEBAR)
    brand_text.pack(side="left")
    label(brand_text, "BITE", 18, bold=True).pack(anchor="w")
    label(brand_text, "WATCH / РР4", 8, MUTED).pack(anchor="w")
    label(sidebar, "РАБОЧЕЕ ПРОСТРАНСТВО", 8, MUTED).pack(anchor="w", padx=24, pady=(8, 16))

    app.pages = {}
    app.nav_buttons = {}
    content = tk.Frame(shell, bg=BG)
    content.pack(side="left", fill="both", expand=True, padx=28, pady=(24, 18))
    header = tk.Frame(content, bg=BG)
    header.pack(fill="x", pady=(0, 20))
    titles = tk.Frame(header, bg=BG)
    titles.pack(side="left", fill="x", expand=True)
    label(titles, size=25, bold=True, textvariable=app.page_title).pack(anchor="w")
    label(titles, size=10, color=MUTED, textvariable=app.page_subtitle).pack(anchor="w", pady=(4, 0))
    pill = tk.Frame(header, bg=CARD_ALT, highlightbackground=BORDER, highlightthickness=1)
    pill.pack(side="right", padx=(16, 0))
    label(pill, "●", 10, GREEN).pack(side="left", padx=(12, 7), pady=10)
    label(pill, size=9, textvariable=app.status, wraplength=200).pack(side="left", padx=(0, 12), pady=10)

    footer = tk.Frame(content, bg=BG)
    footer.pack(side="bottom", fill="x", pady=(12, 0))
    label(footer, "ЛОКАЛЬНОЕ РАСПОЗНАВАНИЕ  /  WASAPI → TELEGRAM", 8, "#8790bb").pack(side="left")
    label(footer, "Твои записи остаются на ПК", 8, "#8790bb").pack(side="right")

    page_host = tk.Frame(content, bg=BG)
    page_host.pack(fill="both", expand=True)
    page_host.grid_rowconfigure(0, weight=1)
    page_host.grid_columnconfigure(0, weight=1)
    descriptions = {
        "overview": ("Обзор", "Всё под контролем. Остаётся дождаться поклёвки."),
        "telegram": ("Telegram", "Твой личный канал связи с водоёмом."),
        "samples": ("Библиотека звуков", "Чистые образцы — основа точного распознавания."),
        "settings": ("Аудио и настройки", "Выбери источник звука и настрой чувствительность."),
    }

    def show_page(key):
        app.pages[key].tkraise()
        app.page_title.set(descriptions[key][0])
        app.page_subtitle.set(descriptions[key][1])
        for name, button in app.nav_buttons.items():
            button.config(bg="#373658" if name == key else SIDEBAR,
                          fg=TEXT if name == key else MUTED)
        app.active_page = key

    app.show_page = show_page
    for key, icon, title in (("overview", "◈", "Обзор"), ("telegram", "↗", "Telegram"),
                             ("samples", "≋", "Образцы звуков"), ("settings", "⚙", "Настройки")):
        button = tk.Button(sidebar, text=f"{icon}    {title}", anchor="w", bg=SIDEBAR, fg=MUTED,
                           activebackground="#373658", activeforeground=TEXT, relief="flat", borderwidth=0,
                           font=("Segoe UI", 11), cursor="hand2", padx=18, pady=14,
                           command=lambda value=key: show_page(value))
        button.pack(fill="x", padx=12, pady=4)
        app.nav_buttons[key] = button
        page = tk.Frame(page_host, bg=BG)
        page.grid(row=0, column=0, sticky="nsew")
        app.pages[key] = page

    bottom = tk.Frame(sidebar, bg=SIDEBAR)
    bottom.pack(side="bottom", fill="x", padx=24, pady=24)
    label(bottom, "ТОЛЬКО АУДИО", 9, GREEN, bold=True).pack(anchor="w")
    label(bottom, "Без доступа к игре.\nБез игровых действий.", 9, MUTED, justify="left").pack(anchor="w", pady=(8, 22))
    label(bottom, "BITE WATCH  /  2.0", 8, "#7982b1").pack(anchor="w")

    # Overview: actual live metrics, chart, controls, and bounded event journal.
    overview = app.pages["overview"]
    overview.columnconfigure(0, weight=1, minsize=350)
    overview.columnconfigure(1, weight=0, minsize=292)
    overview.rowconfigure(1, weight=3, minsize=250)
    overview.rowconfigure(2, weight=2, minsize=195)
    metrics = tk.Frame(overview, bg=BG)
    metrics.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 18))
    for i in range(3):
        metrics.columnconfigure(i, weight=1, uniform="metric")
    app.level_metric = Metric(metrics, "Уровень звука", BLUE, "Относительная шкала, не дБ")
    app.score_metric = Metric(metrics, "Совпадение", CORAL, "Сходство с образцом, не вероятность")
    app.count_metric = Metric(metrics, "Срабатывания", PURPLE, "За время работы приложения")
    for i, widget in enumerate((app.level_metric, app.score_metric, app.count_metric)):
        widget.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0 if i == 2 else 8))
    app.level_metric.set("0%")
    app.score_metric.set("—")
    app.count_metric.set("0")
    chart_card, chart_body = panel(overview, "Пульс водоёма", "Живой сигнал · последние 30 секунд")
    chart_card.grid(row=1, column=0, sticky="nsew", padx=(0, 18), pady=(0, 18))
    legend = tk.Frame(chart_body, bg=CARD)
    legend.pack(fill="x", pady=(0, 5))
    label(legend, "●  Звук", 9, BLUE).pack(side="left", padx=(0, 18))
    label(legend, "●  Совпадение", 9, CORAL).pack(side="left")
    app.chart = LiveChart(chart_body)
    app.chart.pack(fill="both", expand=True)

    controls_card, controls = panel(overview, "На страже поклёвки")
    controls_card.grid(row=1, column=1, sticky="nsew", pady=(0, 18))
    app.start_button = ttk.Button(controls, text="▶  Запустить мониторинг", style="Primary.TButton", command=lambda: app.start(False))
    app.start_button.pack(fill="x", pady=4)
    app.dry_button = ttk.Button(controls, text="Проверка без Telegram", command=lambda: app.start(True))
    app.dry_button.pack(fill="x", pady=4)
    app.stop_button = ttk.Button(controls, text="■  Остановить", style="Danger.TButton", command=app.stop, state="disabled")
    app.stop_button.pack(fill="x", pady=4)
    label(controls, size=9, color=MUTED, textvariable=app.sample_summary, wraplength=245, justify="left").pack(anchor="w", pady=(12, 0))

    journal_card, journal = panel(overview, "Журнал событий")
    journal_card.grid(row=2, column=0, sticky="nsew", padx=(0, 18))
    app.log_box = tk.Text(journal, height=5, state="disabled", wrap="word", font=("Segoe UI", 9),
                          bg=CARD, fg=MUTED, relief="flat", highlightthickness=0, insertbackground=TEXT)
    scroll = ttk.Scrollbar(journal, command=app.log_box.yview)
    scroll.pack(side="right", fill="y")
    app.log_box.config(yscrollcommand=scroll.set)
    app.log_box.pack(side="left", fill="both", expand=True)
    app.log_box.tag_configure("bite", foreground=CORAL)
    app.log_box.tag_configure("success", foreground=GREEN)
    info_card, info = panel(overview, "Состояние системы")
    info_card.grid(row=2, column=1, sticky="nsew")
    label(info, "TELEGRAM", 8, MUTED).pack(anchor="w")
    label(info, size=10, textvariable=app.telegram_state, wraplength=240, justify="left").pack(anchor="w", pady=(3, 8))
    label(info, "ПОСЛЕДНЕЕ СОБЫТИЕ", 8, MUTED).pack(anchor="w")
    label(info, size=9, textvariable=app.last_event, wraplength=240, justify="left").pack(anchor="w", pady=(3, 6))
    label(info, size=8, color=MUTED, textvariable=app.score_text, wraplength=240, justify="left").pack(anchor="w")

    # Telegram page.
    telegram_card, telegram = panel(app.pages["telegram"], "Подключение бота", "Токен вводится только здесь и защищается Windows DPAPI при сохранении.")
    telegram_card.pack(fill="x")
    label(telegram, "ТОКЕН БОТА", 9, MUTED).pack(anchor="w", pady=(8, 7))
    token_row = tk.Frame(telegram, bg=CARD)
    token_row.pack(fill="x", pady=(0, 18))
    app.token_entry = ClipboardEntry(token_row, textvariable=app.token, show="•", secret=True)
    app.token_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    ttk.Button(token_row, text="Вставить", command=lambda: app.token_entry.paste(replace_all=True)).pack(side="right")
    label(telegram, "CHAT ID", 9, MUTED).pack(anchor="w", pady=(0, 7))
    chat_row = tk.Frame(telegram, bg=CARD)
    chat_row.pack(fill="x", pady=(0, 20))
    app.chat_entry = ClipboardEntry(chat_row, textvariable=app.chat)
    app.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    ttk.Button(chat_row, text="Вставить", command=lambda: app.chat_entry.paste(replace_all=True)).pack(side="right")
    actions = tk.Frame(telegram, bg=CARD)
    actions.pack(fill="x")
    ttk.Button(actions, text="↗  Тест сообщения", style="Primary.TButton", command=app.test_message).pack(side="left", padx=(0, 10))
    ttk.Button(actions, text="Сохранить настройки", command=app.save_settings).pack(side="left")
    label(telegram, color=GREEN, textvariable=app.telegram_state).pack(anchor="w", pady=(16, 0))
    tips_card, tips = panel(app.pages["telegram"], "Первое подключение")
    tips_card.pack(fill="x", pady=(18, 0))
    label(tips, "01   Создай бота через @BotFather и скопируй токен.\n\n"
                "02   Открой своего бота в Telegram и нажми Start.\n\n"
                "03   Укажи числовой chat ID, проверь сообщение и включи уведомления на телефоне.",
          10, MUTED, justify="left", wraplength=730).pack(anchor="w")
    label(tips, "Никому не передавай токен. При смене токена или чата повтори тест.",
          9, CORAL, wraplength=730, justify="left").pack(anchor="w", pady=(18, 0))

    # Sample library page: same files and selection semantics as the original UI.
    samples_card, samples = panel(app.pages["samples"], "Твоя звуковая коллекция", "Добавляй чистые поклёвки и похожие звуки, которые нужно игнорировать.")
    samples_card.pack(fill="both", expand=True)
    tools = tk.Frame(samples, bg=CARD)
    tools.pack(fill="x", pady=(6, 16))
    app.record_button = ttk.Button(tools, text="●  Записать", style="Primary.TButton", command=app.record)
    app.record_button.pack(side="left")
    ttk.Spinbox(tools, from_=2, to=20, width=3, textvariable=app.record_seconds).pack(side="left", padx=(10, 5))
    label(tools, "сек.", 9, MUTED).pack(side="left", padx=(0, 16))
    app.import_button = ttk.Button(tools, text="Импорт WAV", command=app.import_sample)
    app.import_button.pack(side="left", padx=(0, 8))
    ttk.Button(tools, text="Открыть папку", command=lambda: os_startfile(app.samples_dir)).pack(side="left")
    listing = tk.Frame(samples, bg=INPUT, highlightbackground=BORDER, highlightthickness=1)
    listing.pack(fill="both", expand=True)
    app.sample_list = tk.Listbox(listing, height=8, exportselection=False, relief="flat", highlightthickness=0,
                                font=("Segoe UI", 12), activestyle="none", selectborderwidth=0)
    sample_scroll = ttk.Scrollbar(listing, command=app.sample_list.yview)
    sample_scroll.pack(side="right", fill="y")
    app.sample_list.config(yscrollcommand=sample_scroll.set)
    app.sample_list.pack(side="left", fill="both", expand=True, padx=12, pady=12)
    sample_footer = tk.Frame(samples, bg=CARD)
    sample_footer.pack(fill="x", pady=(16, 0))
    label(sample_footer, size=9, color=MUTED, textvariable=app.sample_summary).pack(side="left")
    app.delete_button = ttk.Button(sample_footer, text="Удалить выбранный", style="Danger.TButton", command=app.delete_sample)
    app.delete_button.pack(side="right")
    label(samples, "В редакторе оставляй короткий фрагмент 0,5–2 с. Отрицательный пример не должен содержать поклёвку.",
          9, MUTED, wraplength=730, justify="left").pack(anchor="w", pady=(15, 0))

    # Settings page.
    audio_card, audio = panel(app.pages["settings"], "Источник звука", "WASAPI loopback захватывает все приложения на выбранном выходе. Микрофон не нужен.")
    audio_card.pack(fill="x")
    device_row = tk.Frame(audio, bg=CARD)
    device_row.pack(fill="x", pady=(8, 0))
    app.device_box = ttk.Combobox(device_row, state="readonly")
    app.device_box.pack(side="left", fill="x", expand=True, padx=(0, 12))
    app.refresh_button = ttk.Button(device_row, text="↻  Обновить", command=app.refresh_devices)
    app.refresh_button.pack(side="right")
    detection_card, detection = panel(app.pages["settings"], "Точность распознавания", "Изменения применяются при следующем запуске мониторинга.")
    detection_card.pack(fill="x", pady=(18, 0))
    row = tk.Frame(detection, bg=CARD)
    row.pack(fill="x", pady=(10, 16))
    left = tk.Frame(row, bg=CARD)
    left.pack(side="left", fill="x", expand=True)
    label(left, "ПОРОГ СОВПАДЕНИЯ", 9, MUTED).pack(anchor="w", pady=(0, 8))
    ttk.Spinbox(left, from_=0.5, to=0.98, increment=0.01, width=10, textvariable=app.threshold).pack(anchor="w")
    right = tk.Frame(row, bg=CARD)
    right.pack(side="left", fill="x", expand=True)
    label(right, "ПАУЗА МЕЖДУ УВЕДОМЛЕНИЯМИ, СЕК.", 9, MUTED).pack(anchor="w", pady=(0, 8))
    ttk.Spinbox(right, from_=5, to=600, width=10, textvariable=app.cooldown).pack(anchor="w")
    label(detection, "Начни с 0.78. Пропуски → немного снизь порог. Ложные сигналы → повысь порог и добавь отрицательные образцы.",
          10, MUTED, wraplength=720, justify="left").pack(anchor="w", pady=(0, 18))
    ttk.Button(detection, text="Сохранить настройки", style="Primary.TButton", command=app.save_settings).pack(anchor="w")
    note_card, note = panel(app.pages["settings"], "Важно знать")
    note_card.pack(fill="x", pady=(18, 0))
    label(note, "Держи приложение открытым, а компьютер — включённым. Звук игры должен выводиться на выбранное устройство. "
                "Проверь допустимость использования по правилам РР4.", 10, MUTED, wraplength=730, justify="left").pack(anchor="w")

    app.token.trace_add("write", lambda *_: app.telegram_state.set("Не проверен"))
    app.chat.trace_add("write", lambda *_: app.telegram_state.set("Не проверен"))
    show_page("overview")


def os_startfile(path):
    import os
    os.startfile(path)
