# -*- coding: utf-8 -*-
"""
SENTINEL AI — Главное окно v17.1
Стек: customtkinter 5.x, Python 3.10+, Ollama, faster-whisper
"""
import json
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
import logging
logging.basicConfig(filename='logs/sentinel.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s')
import customtkinter as ctk

APP_VERSION = "17.1"

# ─── Палитра ──────────────────────────────────────────────────────────────────
P = {
    "bg":      "#0d1117",
    "card":    "#161b22",
    "border":  "#30363d",
    "blue":    "#58a6ff",
    "green":   "#3fb950",
    "yellow":  "#d29922",
    "red":     "#f85149",
    "text":    "#e6edf3",
    "sub":     "#8b949e",
}

# face state → (eye_color, ring_color, mouth_color)
_FACE = {
    "idle":     ("58a6ff", "1a3a5c", "58a6ff"),
    "thinking": ("d29922", "3d2b00", "d29922"),
    "active":   ("3fb950", "0d3320", "3fb950"),
    "sleep":    ("30363d", "161b22", "30363d"),
    "error":    ("f85149", "3d1110", "f85149"),
}

# face state → (высота_глаз, start_рта, extent_рта)
# idle=нейтральная улыбка, thinking=прищур+поджатые губы,
# active=широкие глаза+большая улыбка, sleep=щёлочки+почти плоский,
# error=нормальные глаза+хмурый рот (start=20 = верхняя часть дуги = хмурит)
_FACE_SHAPES = {
    "idle":     (7,  200, 140),
    "thinking": (4,  190,  70),
    "active":   (10, 195, 160),
    "sleep":    (2,  185,  18),
    "error":    (5,   20, 140),
}

# Цветовые схемы тем
_THEMES_P = {
    "Неон":     {"blue": "#58a6ff", "green": "#3fb950", "card": "#161b22", "bg": "#0d1117"},
    "Океан":    {"blue": "#79c0ff", "green": "#39c5bb", "card": "#0d2137", "bg": "#050e1a"},
    "Закат":    {"blue": "#ff7b72", "green": "#ffa657", "card": "#1e1410", "bg": "#120c08"},
    "Лес":      {"blue": "#56d364", "green": "#3fb950", "card": "#0d1f0d", "bg": "#060f06"},
    "Монохром": {"blue": "#aaaaaa", "green": "#888888", "card": "#2a2a2a", "bg": "#1a1a1a"},
}


# ─── AnimatedFace ─────────────────────────────────────────────────────────────
class AnimatedFace(tk.Canvas):
    """Морда агента с выражениями для каждого состояния."""

    def __init__(self, parent, size: int = 190, **kw):
        bg = kw.pop("bg", P["card"])
        super().__init__(parent, width=size, height=size,
                         bg=bg, highlightthickness=0, **kw)
        self.size = size
        self.state = "idle"
        self._tick = 0
        self._blink_open = True
        self._after_id = None
        self._i: dict = {}
        self._build()
        self._loop()

    def _build(self):
        s = self.size
        cx = cy = s // 2
        r = s // 2 - 10
        ey = cy - r // 4
        self._i["glow"] = self.create_oval(
            cx-r-5, cy-r-5, cx+r+5, cy+r+5,
            outline="#0d2040", width=7, fill=""
        )
        self._i["ring"] = self.create_oval(
            cx-r, cy-r, cx+r, cy+r,
            outline="#1a3a5c", width=2, fill=""
        )
        ew, eh = 14, 7
        for k, ex in [("el", cx - r//3), ("er", cx + r//3)]:
            self._i[k] = self.create_oval(
                ex-ew//2, ey-eh//2, ex+ew//2, ey+eh//2,
                fill="#58a6ff", outline=""
            )
        self._i["m"] = self.create_arc(
            cx - r//3, cy + r//8,
            cx + r//3, cy + r//2,
            start=200, extent=140,
            style="arc", outline="#58a6ff", width=2
        )

    def set_state(self, state: str):
        if state not in _FACE or state == self.state:
            return
        self.state = state
        eye_c, ring_c, mouth_c = (f"#{x}" for x in _FACE[state])
        self.itemconfig(self._i["ring"],  outline=ring_c)
        self.itemconfig(self._i["glow"],  outline=ring_c)
        self.itemconfig(self._i["el"],    fill=eye_c)
        self.itemconfig(self._i["er"],    fill=eye_c)
        self.itemconfig(self._i["m"],     outline=mouth_c)
        # ── меняем геометрию по состоянию
        s = self.size; cx = cy = s // 2; r = s // 2 - 10
        ex_l = cx - r // 3; ex_r = cx + r // 3
        ey = cy - r // 4; ew = 14
        eye_h, m_start, m_ext = _FACE_SHAPES.get(state, _FACE_SHAPES["idle"])
        half = max(1, eye_h // 2)
        self.coords(self._i["el"], ex_l - ew//2, ey - half, ex_l + ew//2, ey + half)
        self.coords(self._i["er"], ex_r - ew//2, ey - half, ex_r + ew//2, ey + half)
        self.itemconfig(self._i["m"], start=m_start, extent=m_ext)

    def _loop(self):
        self._tick += 1

        # моргание — в спящем режиме медленнее
        blink_period = 120 if self.state == "sleep" else 60
        tb = self._tick % blink_period
        if tb == 0:
            self._blink_open = False
            self.itemconfig(self._i["el"], fill=P["card"])
            self.itemconfig(self._i["er"], fill=P["card"])
        elif tb == 3:
            self._blink_open = True
            eye = f"#{_FACE.get(self.state, _FACE['idle'])[0]}"
            self.itemconfig(self._i["el"], fill=eye)
            self.itemconfig(self._i["er"], fill=eye)

        # пульсация кольца по состоянию
        if self.state == "thinking":
            pulse = "#d29922" if (self._tick // 10) % 2 else "#8b6514"
            self.itemconfig(self._i["ring"], outline=pulse)
        elif self.state == "active":
            pulse = "#3fb950" if (self._tick // 8) % 2 else "#1a6b2a"
            self.itemconfig(self._i["ring"], outline=pulse)

        ms = 50 if self.state in ("thinking", "active") else (180 if self.state == "sleep" else 100)
        self._after_id = self.after(ms, self._loop)

    def stop(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None


# ─── AimOverlay ───────────────────────────────────────────────────────────────
class AimOverlay(tk.Toplevel):
    """Прозрачный оверлей поверх игры: подсказки + мини-статистика."""

    _POS = "aim_overlay_pos.json"

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.9)
        self.configure(bg="#0a0a0a")
        self.geometry("430x95")
        self._dx = self._dy = 0
        self.bind("<Button-1>",   lambda e: setattr(self, '_dx', e.x) or setattr(self, '_dy', e.y))
        self.bind("<B1-Motion>",  self._drag)
        self.bind("<Double-1>",   lambda _: self.withdraw())

        fr = tk.Frame(self, bg="#0a0a0a", padx=10, pady=6)
        fr.pack(fill="both", expand=True)

        self._prof = tk.Label(fr, text="🎯 Аим-коуч", bg="#0a0a0a",
                              fg="#58a6ff", font=("Segoe UI", 9, "bold"), anchor="w")
        self._prof.pack(fill="x")
        self._tip = tk.Label(fr, text="Ожидание...", bg="#0a0a0a",
                             fg="#e6edf3", font=("Segoe UI", 14, "bold"),
                             wraplength=410, justify="left", anchor="w")
        self._tip.pack(fill="x", pady=(2, 0))
        self._stat = tk.Label(fr, text="", bg="#0a0a0a",
                              fg="#8b949e", font=("Segoe UI", 8), anchor="w")
        self._stat.pack(fill="x")

        self._load_pos()

    def update_advice(self, advice: str, profile: str = "", stats: str = ""):
        self._tip.configure(text=advice or "—")
        if profile:
            self._prof.configure(text=f"🎯 {profile}")
        if stats:
            self._stat.configure(text=stats)
        self.deiconify()

    def _drag(self, e):
        x, y = self.winfo_x() + e.x - self._dx, self.winfo_y() + e.y - self._dy
        self.geometry(f"+{x}+{y}")
        self._save_pos()

    def _load_pos(self):
        try:
            p = json.loads(Path(self._POS).read_text())
            self.geometry(f"+{p['x']}+{p['y']}")
        except Exception:
            self.geometry("+50+50")

    def _save_pos(self):
        try:
            Path(self._POS).write_text(
                json.dumps({"x": self.winfo_x(), "y": self.winfo_y()})
            )
        except Exception:
            pass


# ─── SentinelGUI ─────────────────────────────────────────────────────────────
class SentinelGUI(ctk.CTk):

    _THEMES = ["Неон", "Океан", "Закат", "Лес", "Монохром"]

    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title(f"Сентинел ИИ  v{APP_VERSION}")
        self.geometry("1280x780")
        self.minsize(920, 620)
        self.configure(fg_color=P["bg"])

        # State
        self._log_q: queue.Queue = queue.Queue()
        self._running    = threading.Event()
        self._aim_active = threading.Event()
        self._sleep_mode = False

        # Module refs (lazy-loaded)
        self._core = self._planner = self._executor = None
        self._aim_coach = self._memory = self._custodian = None
        self._translator_win = None
        self._aim_overlay: AimOverlay | None = None

        self._build_ui()
        self._start_log_drain()
        self.after(200, self._load_async)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Module loading ─────────────────────────────────────────────────────────

    def _load_async(self):
        threading.Thread(target=self._load_modules, daemon=True).start()

    def _load_modules(self):
        self._log("⚙️ Загружаю модули...")
        self._face.set_state("thinking")
        self._set_status("Загрузка...", "yellow")
        try:
            from core      import Core
            from planner   import Planner
            from executor  import Executor
            from aim_coach import AimCoach
            from memory    import MemoryStore

            self._memory   = MemoryStore()
            self._core     = Core()
            self._planner  = Planner(
                core                    = self._core,
                brain_model             = self._core.brain_model,
                planner_history_limit   = self._core.cfg.get("planner_history_limit", 4),
                planner_max_steps       = self._core.cfg.get("planner_max_steps", 16),
                planner_temperature     = self._core.cfg.get("planner_temperature", 0.4),
                allow_web_search        = self._core.cfg.get("allow_web_search", False),
                memory_store            = self._memory,
                offline_mode            = self._core.cfg.get("offline_mode", True),
            )
            self._executor = Executor(
                core          = self._core,
                auto          = self._core.auto_execute,
                search_engine = self._core.cfg.get("use_search_engine", ""),
                offline_mode  = self._core.cfg.get("offline_mode", True),
            )
            self._core.executor = self._executor
            # прокидываем planner в core для SmartPilot
            self._core.planner = self._planner
            self._aim_coach = AimCoach(
                core         = self._core,
                planner      = self._planner,
                log_callback = self._log,
                memory_store = self._memory,
            )
            self._start_custodian()
            self._log("✅ Все модули загружены.")
            self._face.set_state("idle")
            self._set_status("Готов", "green")
            self.after(0, self._unlock_controls)
        except Exception as exc:
            self._log(f"❌ Ошибка загрузки: {exc}")
            self._face.set_state("error")
            self._set_status("Ошибка", "red")

    def _start_custodian(self):
        try:
            from night_custodian import NightCustodian
            self._custodian = NightCustodian(
                memory_store = self._memory,
                core         = self._core,
                log_callback = self._log,
            )
            self._custodian.start()
        except Exception as e:
            self._log(f"⚠ Смотритель: {e}")

    def _unlock_controls(self):
        for w in (self._start_btn, self._aim_btn,
                  self._input_entry, self._send_btn, self._aim_q_entry):
            w.configure(state="normal")

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── header
        hdr = ctk.CTkFrame(self, fg_color=P["card"], height=52, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="СЕНТИНЕЛ ИИ",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=P["blue"]).pack(side="left", padx=18, pady=8)
        ctk.CTkLabel(hdr, text="Автономный помощник, коуч и безопасный локальный исследователь интерфейсов",
                     font=ctk.CTkFont(size=11),
                     text_color=P["sub"]).pack(side="left", pady=8)

        ctk.CTkButton(hdr, text="На весь экран", width=120, height=30,
                      fg_color=P["border"], hover_color="#444c56",
                      command=self._toggle_fullscreen).pack(side="right", padx=6, pady=10)
        self._status_lbl = ctk.CTkLabel(hdr, text="● Загрузка",
                                         text_color=P["yellow"],
                                         font=ctk.CTkFont(size=12, weight="bold"))
        self._status_lbl.pack(side="right", padx=10)

        # ── body (left + right)
        body = tk.Frame(self, bg=P["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_right(body)

    # ── Left panel ─────────────────────────────────────────────────────────────

    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, fg_color=P["card"], width=236, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="Живой агент",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=P["sub"]).pack(pady=(14, 4), padx=14, anchor="w")

        # face
        fwrap = ctk.CTkFrame(left, fg_color=P["card"])
        fwrap.pack(pady=4)
        self._face = AnimatedFace(fwrap, size=190, bg=P["card"])
        self._face.pack()

        self._face_title = ctk.CTkLabel(left, text="СЕНТИНЕЛ  /  ОЖИДАНИЕ",
                                         font=ctk.CTkFont(size=11, weight="bold"),
                                         text_color=P["blue"])
        self._face_title.pack(pady=(4, 1))
        self._face_sub = ctk.CTkLabel(left, text="Готов к задаче",
                                       font=ctk.CTkFont(size=10), text_color=P["sub"])
        self._face_sub.pack(pady=(0, 8))

        ctk.CTkFrame(left, height=1, fg_color=P["border"]).pack(fill="x", padx=14, pady=4)

        # scrollable controls area
        ctrl = ctk.CTkScrollableFrame(left, fg_color=P["card"], scrollbar_button_color=P["border"])
        ctrl.pack(fill="both", expand=True, padx=12, pady=4)

        ctk.CTkLabel(ctrl, text="Управление",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=P["text"]).pack(anchor="w", pady=(4, 4))

        self._start_btn = ctk.CTkButton(
            ctrl, text="Запустить автономный режим",
            height=36, fg_color="#2563eb", hover_color="#1d4ed8",
            command=self._toggle_agent, state="disabled"
        )
        self._start_btn.pack(fill="x", pady=2)

        self._lbl("Режим:", ctrl)
        self._mode_cb = ctk.CTkComboBox(ctrl, values=["Рабочий стол", "Браузер"],
                                         height=30, command=self._on_mode)
        self._mode_cb.set("Рабочий стол")
        self._mode_cb.pack(fill="x", pady=2)

        ctk.CTkFrame(ctrl, height=1, fg_color=P["border"]).pack(fill="x", pady=6)

        self._aim_btn = ctk.CTkButton(
            ctrl, text="Включить аим-коуч",
            height=34, fg_color=P["border"], hover_color="#444c56",
            command=self._toggle_aim, state="disabled"
        )
        self._aim_btn.pack(fill="x", pady=2)

        self._lbl("Игровой профиль:", ctrl)
        self._game_cb = ctk.CTkComboBox(
            ctrl, values=["Auto Detect", "CS2", "Valorant", "Aim Lab", "KovaaK", "TF2"],
            height=30, command=lambda v: self._aim_coach and self._aim_coach.set_game_profile(v)
        )
        self._game_cb.set("Auto Detect")
        self._game_cb.pack(fill="x", pady=2)

        ctk.CTkFrame(ctrl, height=1, fg_color=P["border"]).pack(fill="x", pady=6)

        self._lbl("Тема:", ctrl)
        self._theme_cb = ctk.CTkComboBox(ctrl, values=self._THEMES,
                                          height=30, command=self._on_theme)
        self._theme_cb.set("Неон")
        self._theme_cb.pack(fill="x", pady=2)

        ctk.CTkFrame(ctrl, height=1, fg_color=P["border"]).pack(fill="x", pady=6)

        ctk.CTkButton(ctrl, text="💤 Спящий режим", height=28,
                      fg_color=P["border"], hover_color="#444c56",
                      font=ctk.CTkFont(size=11),
                      command=self._toggle_sleep).pack(fill="x", pady=2)

        ctk.CTkButton(ctrl, text="🗜 Сжать память", height=28,
                      fg_color=P["border"], hover_color="#444c56",
                      font=ctk.CTkFont(size=11),
                      command=self._compact_memory).pack(fill="x", pady=2)

    def _lbl(self, text: str, parent):
        ctk.CTkLabel(parent, text=text, text_color=P["sub"],
                     font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(4, 0))

    # ── Right panel ────────────────────────────────────────────────────────────

    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color=P["bg"], corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # title + quick buttons
        top = ctk.CTkFrame(right, fg_color=P["bg"])
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        ctk.CTkLabel(top, text="Пульт управления",
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=P["text"]).pack(side="left")

        for txt, cmd in [
            ("🛡 Автопилот",    self._safe_autopilot),
            ("🎮 Профили",      lambda: self._tabs.set("🎯 Аим-коуч")),
            ("🧠 Память",       self._goto_memory),
            ("📡 Офлайн",       self._toggle_offline),
        ]:
            ctk.CTkButton(top, text=txt, width=110, height=28,
                          fg_color="transparent", border_color=P["border"],
                          border_width=1, hover_color=P["border"],
                          text_color=P["blue"], command=cmd).pack(side="left", padx=3)

        # tabview
        self._tabs = ctk.CTkTabview(
            right, fg_color=P["card"],
            segmented_button_fg_color=P["bg"],
            segmented_button_selected_color="#2563eb",
            segmented_button_unselected_color=P["border"],
        )
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 8))

        for t in ["💬 Агент", "🎯 Аим-коуч", "🌐 Перевод", "🧠 Память"]:
            self._tabs.add(t)

        self._tab_agent()
        self._tab_aim()
        self._tab_translator()
        self._tab_memory()

        # bottom input
        inp = ctk.CTkFrame(right, fg_color=P["card"], corner_radius=8)
        inp.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))

        self._input_entry = ctk.CTkEntry(
            inp,
            placeholder_text="Введите задачу. Например: открой локальное окно или исследуй браузер без интернета",
            height=44, font=ctk.CTkFont(size=13),
            fg_color=P["bg"], border_color=P["border"], state="disabled"
        )
        self._input_entry.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=8)
        self._input_entry.bind("<Return>", lambda _: self._send_task())

        self._send_btn = ctk.CTkButton(
            inp, text="Старт", width=90, height=44,
            fg_color="#2563eb", hover_color="#1d4ed8",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._send_task, state="disabled"
        )
        self._send_btn.pack(side="right", padx=(0, 10), pady=8)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _tab_agent(self):
        tab = self._tabs.tab("💬 Агент")
        self._log_text = ctk.CTkTextbox(
            tab, font=ctk.CTkFont(family="Cascadia Code", size=12),
            fg_color=P["bg"], wrap="word", text_color=P["text"]
        )
        self._log_text.pack(fill="both", expand=True, padx=8, pady=8)
        self._log_text.configure(state="disabled")

    def _tab_aim(self):
        tab = self._tabs.tab("🎯 Аим-коуч")

        # stats row
        sr = ctk.CTkFrame(tab, fg_color=P["bg"])
        sr.pack(fill="x", padx=8, pady=(8, 4))
        self._aim_slbls: dict[str, ctk.CTkLabel] = {}
        for key, label in [("sessions", "Сессий"), ("advices", "Советов"),
                            ("questions", "Вопросов"), ("rank", "Ранг")]:
            card = ctk.CTkFrame(sr, fg_color=P["card"], corner_radius=8)
            card.pack(side="left", expand=True, fill="x", padx=3)
            ctk.CTkLabel(card, text=label, text_color=P["sub"],
                         font=ctk.CTkFont(size=10)).pack(pady=(6, 0))
            lbl = ctk.CTkLabel(card, text="—", text_color=P["blue"],
                                font=ctk.CTkFont(size=16, weight="bold"))
            lbl.pack(pady=(0, 6))
            self._aim_slbls[key] = lbl

        # last advice
        ctk.CTkLabel(tab, text="Последний совет:",
                     text_color=P["sub"], font=ctk.CTkFont(size=11)
                     ).pack(anchor="w", padx=8, pady=(8, 2))
        self._last_advice = ctk.CTkLabel(
            tab, text="Нет данных", text_color=P["text"],
            font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=600, justify="left"
        )
        self._last_advice.pack(anchor="w", padx=8)

        # ask question
        ask = ctk.CTkFrame(tab, fg_color=P["bg"])
        ask.pack(fill="x", padx=8, pady=8)
        self._aim_q_entry = ctk.CTkEntry(ask, placeholder_text="Задай вопрос коучу...",
                                          height=36, fg_color=P["bg"], state="disabled")
        self._aim_q_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._aim_q_entry.bind("<Return>", lambda _: self._ask_aim())
        ctk.CTkButton(ask, text="Спросить", width=100, height=36,
                      fg_color="#2563eb", command=self._ask_aim).pack(side="right")

        ctk.CTkLabel(tab, text="История Q&A:",
                     text_color=P["sub"], font=ctk.CTkFont(size=11)).pack(anchor="w", padx=8)
        self._aim_hist = ctk.CTkTextbox(
            tab, font=ctk.CTkFont(size=11), fg_color=P["bg"],
            text_color=P["text"]
        )
        self._aim_hist.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._aim_hist.configure(state="disabled")

    def _tab_translator(self):
        tab = self._tabs.tab("🌐 Перевод")

        ctk.CTkLabel(
            tab,
            text="Голосовой переводчик поверх экрана\nWhisper + Ollama — всё локально, без интернета",
            text_color=P["sub"], font=ctk.CTkFont(size=12), justify="center"
        ).pack(pady=(30, 14))

        ctk.CTkButton(tab, text="🎤  Открыть переводчик", height=46, width=270,
                      fg_color="#2563eb", hover_color="#1d4ed8",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._open_translator).pack()

        # settings card
        sc = ctk.CTkFrame(tab, fg_color=P["card"], corner_radius=8)
        sc.pack(padx=50, pady=20, fill="x")
        ctk.CTkLabel(sc, text="Быстрые настройки",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=P["text"]).pack(pady=(10, 6))

        row = ctk.CTkFrame(sc, fg_color=P["card"])
        row.pack(pady=6, padx=20, fill="x")
        self._lbl("Модель Whisper:", row)
        self._w_model = ctk.CTkComboBox(row, values=["tiny", "base", "small", "medium"],
                                         width=110, command=self._on_whisper_model)
        self._w_model.set("tiny")
        self._w_model.pack(side="left", padx=(0, 12))

        self._lbl("Устройство:", row)
        self._w_dev = ctk.CTkComboBox(row, values=["cuda", "cpu"],
                                       width=90, command=self._on_whisper_dev)
        self._w_dev.set("cuda")
        self._w_dev.pack(side="left")

        ctk.CTkLabel(sc, text="💡 tiny + cuda — лучшая скорость на RTX 2060 Super",
                     text_color=P["green"], font=ctk.CTkFont(size=11)).pack(pady=(4, 10))

        ctk.CTkLabel(tab, text="Последние переводы:",
                     text_color=P["sub"], font=ctk.CTkFont(size=11)
                     ).pack(anchor="w", padx=20, pady=(6, 2))
        self._trans_log = ctk.CTkTextbox(
            tab, font=ctk.CTkFont(size=12), fg_color=P["bg"],
            text_color=P["text"]
        )
        self._trans_log.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        self._trans_log.configure(state="disabled")

    def _tab_memory(self):
        tab = self._tabs.tab("🧠 Память")

        br = ctk.CTkFrame(tab, fg_color=P["bg"])
        br.pack(fill="x", padx=8, pady=8)
        ctk.CTkButton(br, text="🔄 Обновить", width=110, height=30,
                      command=self._refresh_memory).pack(side="left", padx=4)
        ctk.CTkButton(br, text="🗜 Сжать", width=90, height=30,
                      fg_color=P["border"], command=self._compact_memory).pack(side="left", padx=4)

        self._mem_text = ctk.CTkTextbox(
            tab, font=ctk.CTkFont(size=12),
            fg_color=P["bg"], text_color=P["text"]
        )
        self._mem_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._mem_text.configure(state="disabled")

    # ── Agent ──────────────────────────────────────────────────────────────────

    def _toggle_agent(self):
        if self._running.is_set():
            self._running.clear()
            self._start_btn.configure(text="Запустить автономный режим",
                                       fg_color="#2563eb")
            self._face.set_state("idle")
            self._set_status("Остановлен", "sub")
        else:
            task = self._input_entry.get().strip()
            if not task:
                self._log("⚠ Введите задачу!")
                return
            self._running.set()
            self._start_btn.configure(text="⏹ Остановить", fg_color=P["red"])
            self._face.set_state("thinking")
            self._set_status("Работает", "green")
            threading.Thread(target=self._agent_loop, args=(task,), daemon=True).start()

    def _send_task(self):
        task = self._input_entry.get().strip()
        if not task or not self._planner:
            return
        if self._planner.is_question_or_dialog(task):
            self._log(f"👤 {task}")
            threading.Thread(target=self._dialog_worker, args=(task,), daemon=True).start()
        else:
            self._toggle_agent()

    def _dialog_worker(self, task: str):
        self._face.set_state("thinking")
        ans = self._planner.answer_dialog(task)
        self._log(f"🤖 {ans}")
        self._face.set_state("idle")

    def _agent_loop(self, task: str):
        if not all([self._planner, self._executor, self._core]):
            return
        self._planner.reset()
        self._executor.no_change_steps = 0
        self._executor.smart_pilot.reset()
        # передаём задачу в core чтобы SmartPilot знал контекст
        self._core.last_task = task
        self._log(f"▶ Задача: {task}")

        cfg   = self._core.cfg
        delay = cfg.get("agent_step_delay_sec", 0.3)
        steps = cfg.get("planner_max_steps", 16)

        for _step in range(steps):
            if not self._running.is_set():
                self._log("⏹ Агент остановлен")
                break

            # ── антизависание: если экран не меняется 3 шага подряд
            if self._executor.no_change_steps >= 3:
                self._log(f"🔍 Нет прогресса ({self._executor.no_change_steps} шага) — исследую экран")
                self._set_face_state("thinking")
                self._executor.smart_pilot.reset()
                self._executor.smart_pilot.activate()
                self._executor.execute("SMART_EXPLORE")
                # no_change_steps уже сброшен внутри _smart_explore
                self._core.invalidate_screen_cache()
                time.sleep(0.5)
                continue

            desc = self._core.capture_description()
            cmd  = self._planner.plan(task, desc)
            self._log(f"→ {cmd}")

            if cmd.startswith("DIALOG:"):
                ans = self._planner.answer_dialog(cmd[7:])
                self._log(f"🤖 {ans}")
                break
            if cmd == "DONE":
                self._log("✅ Готово")
                break

            ok = self._executor.execute(cmd)
            # обновляем морду: активен при успехе, думает при неудаче
            self._set_face_state("active" if ok else "thinking")

            self._planner.remember_result(cmd, ok)
            if self._memory:
                self._memory.remember_command(task, cmd, ok, desc[:300])
            time.sleep(delay)

        self._running.clear()
        self.after(0, lambda: (
            self._start_btn.configure(text="Запустить автономный режим", fg_color="#2563eb"),
            self._face.set_state("idle"),
            self._face_title.configure(text="СЕНТИНЕЛ  /  ОЖИДАНИЕ"),
            self._face_sub.configure(text="Готов к задаче"),
            self._set_status("Готов", "green"),
        ))

    # ── Aim coach ─────────────────────────────────────────────────────────────

    def _toggle_aim(self):
        if not self._aim_coach:
            return
        if self._aim_active.is_set():
            self._aim_active.clear()
            self._aim_coach.stop_session()
            self._aim_btn.configure(text="Включить аим-коуч", fg_color=P["border"])
            if self._aim_overlay:
                self._aim_overlay.withdraw()
            self._log("🎯 Аим-коуч выключен")
        else:
            self._aim_active.set()
            self._aim_coach.start_session()
            self._aim_btn.configure(text="⏹ Выключить аим-коуч", fg_color="#059669")
            if not self._aim_overlay:
                self._aim_overlay = AimOverlay(self)
            self._aim_overlay.deiconify()
            self._log("🎯 Аим-коуч включён (двойной клик по оверлею — скрыть)")
            threading.Thread(target=self._aim_loop, daemon=True).start()

    def _aim_loop(self):
        poll = self._core.cfg.get("aim_coach_poll_sec", 2.5) if self._core else 2.5
        while self._aim_active.is_set():
            try:
                advice  = self._aim_coach.observe_and_advise()
                profile = self._aim_coach.game_profile
                stats   = ""
                if self._memory:
                    s    = self._memory.get_aim_stats()
                    rank = self._memory.aim_rank_guess()
                    stats = (f"Сессий: {s['aim_sessions_started']}  "
                             f"Советов: {s['aim_auto_advices']}  "
                             f"Ранг: {rank}")
                if self._aim_overlay:
                    self.after(0, lambda a=advice, p=profile, st=stats:
                               self._aim_overlay.update_advice(a, p, st))
                self.after(0, lambda a=advice: self._last_advice.configure(text=a))
                self.after(0, self._refresh_aim_stats)
            except Exception as e:
                self._log(f"⚠ Аим: {e}")
            time.sleep(poll)

    def _ask_aim(self):
        if not self._aim_coach:
            return
        q = self._aim_q_entry.get().strip()
        if not q:
            return
        self._aim_q_entry.delete(0, "end")
        threading.Thread(target=self._aim_q_worker, args=(q,), daemon=True).start()

    def _aim_q_worker(self, q: str):
        ans = self._aim_coach.ask_question(q)
        self.after(0, lambda: self._add_aim_hist(q, ans))
        self.after(0, self._refresh_aim_stats)

    def _add_aim_hist(self, q: str, a: str):
        self._aim_hist.configure(state="normal")
        self._aim_hist.insert("end", f"❓ {q}\n💬 {a}\n\n")
        self._aim_hist.see("end")
        self._aim_hist.configure(state="disabled")

    def _refresh_aim_stats(self):
        if not self._memory:
            return
        s    = self._memory.get_aim_stats()
        rank = self._memory.aim_rank_guess()
        self._aim_slbls["sessions"].configure(text=str(s.get("aim_sessions_started", 0)))
        self._aim_slbls["advices"].configure(text=str(s.get("aim_auto_advices", 0)))
        self._aim_slbls["questions"].configure(text=str(s.get("aim_questions", 0)))
        self._aim_slbls["rank"].configure(text=rank)

    # ── Translator ────────────────────────────────────────────────────────────

    def _open_translator(self):
        if self._translator_win and self._translator_win.winfo_exists():
            self._translator_win.focus()
            return
        if not self._core:
            self._log("❌ Ядро не загружено")
            return
        self._core.cfg["whisper_model_size"] = self._w_model.get()
        self._core.cfg["whisper_device"]     = self._w_dev.get()
        try:
            from voice_translator import VoiceTranslatorOverlay
            self._translator_win = VoiceTranslatorOverlay(
                self, self._core,
                log_callback=self._log_translator
            )
        except Exception as e:
            self._log(f"❌ Переводчик: {e}")

    def _log_translator(self, msg: str):
        self._log(msg)
        self.after(0, lambda: (
            self._trans_log.configure(state="normal"),
            self._trans_log.insert("end", f"{msg}\n"),
            self._trans_log.see("end"),
            self._trans_log.configure(state="disabled"),
        ))

    # ── Memory ────────────────────────────────────────────────────────────────

    def _refresh_memory(self):
        if not self._memory:
            return
        self._mem_text.configure(state="normal")
        self._mem_text.delete("1.0", "end")
        for line in self._memory.ui_aim_summary(lines_each=5):
            self._mem_text.insert("end", line + "\n")
        tasks = self._memory.recent_summary("task_history", 5)
        if tasks:
            self._mem_text.insert("end", "\n── Последние задачи ──\n")
            for t in reversed(tasks):
                self._mem_text.insert(
                    "end", f"• {t.get('task','')[:80]} → {t.get('outcome','')}\n"
                )
        self._mem_text.configure(state="disabled")

    def _compact_memory(self):
        if self._memory:
            self._memory.compact(keep_last=50)
            self._log("🗜 Память сжата")
            self._refresh_memory()

    # ── Quick actions ─────────────────────────────────────────────────────────

    def _toggle_sleep(self):
        self._sleep_mode = not self._sleep_mode
        if self._sleep_mode:
            self._face.set_state("sleep")
            self._set_status("Сон", "sub")
            if self._memory:
                self._memory.compact()
            self._log("💤 Спящий режим")
        else:
            self._face.set_state("idle")
            self._set_status("Готов", "green")
            self._log("⚡ Выход из сна")

    def _toggle_fullscreen(self):
        on = self.attributes("-fullscreen")
        self.attributes("-fullscreen", not on)

    def _safe_autopilot(self):
        if self._core:
            self._core.cfg["offline_mode"] = True
        self._log("🛡 Безопасный автопилот — интернет отключён")

    def _toggle_offline(self):
        if not self._core:
            return
        val = not self._core.cfg.get("offline_mode", True)
        self._core.cfg["offline_mode"] = val
        self._log(f"📡 Офлайн: {'ВКЛ' if val else 'ВЫКЛ'}")

    def _goto_memory(self):
        self._tabs.set("🧠 Память")
        self._refresh_memory()

    def _on_mode(self, val: str):
        if self._planner:
            self._planner.set_runtime_profile("browser" if "Браузер" in val else "desktop")

    def _on_theme(self, val: str):
        modes = {
            "Неон":     ("dark", "blue"),
            "Океан":    ("dark", "blue"),
            "Закат":    ("dark", "dark-blue"),
            "Лес":      ("dark", "green"),
            "Монохром": ("dark", "blue"),
        }
        m, c = modes.get(val, ("dark", "blue"))
        ctk.set_appearance_mode(m)
        ctk.set_default_color_theme(c)          # ← ИСПРАВЛЕНО: раньше эта строка отсутствовала
        P.update(_THEMES_P.get(val, {}))         # ← обновляем палитру
        # принудительно сбросить морду для применения новых цветов
        prev = self._face.state
        self._face.state = ""
        self._face.set_state(prev)
        self.configure(fg_color=P["bg"])
        self._log(f"🎨 Тема: {val}")

    def _on_whisper_model(self, val: str):
        if self._core:
            self._core.cfg["whisper_model_size"] = val

    def _on_whisper_dev(self, val: str):
        if self._core:
            self._core.cfg["whisper_device"] = val

    # ── Log & status ──────────────────────────────────────────────────────────

    def _log(self, msg: str):
        self._log_q.put(msg)

    def _start_log_drain(self):
        self._drain()

    def _drain(self):
        try:
            for _ in range(8):
                msg = self._log_q.get_nowait()
                self._log_text.configure(state="normal")
                self._log_text.insert("end", f"{msg}\n")
                self._log_text.see("end")
                self._log_text.configure(state="disabled")
        except (queue.Empty, AttributeError):
            pass
        self.after(60, self._drain)

    def _set_status(self, text: str, color: str):
        c = {"green": P["green"], "yellow": P["yellow"],
             "red": P["red"], "sub": P["sub"]}.get(color, P["sub"])
        self.after(0, lambda: self._status_lbl.configure(
            text=f"● {text}", text_color=c
        ))

    def _set_face_state(self, state: str):
        labels = {
            "idle":     ("СЕНТИНЕЛ  /  ОЖИДАНИЕ", "Готов к задаче"),
            "thinking": ("СЕНТИНЕЛ  /  ДУМАЕТ",   "Обрабатываю..."),
            "active":   ("СЕНТИНЕЛ  /  АКТИВЕН",  "Выполняю задачу"),
            "sleep":    ("СЕНТИНЕЛ  /  СОН",      "Режим экономии"),
            "error":    ("СЕНТИНЕЛ  /  ОШИБКА",   "Требуется внимание"),
        }
        t, s = labels.get(state, ("СЕНТИНЕЛ", ""))
        self.after(0, lambda: (
            self._face.set_state(state),
            self._face_title.configure(text=t),
            self._face_sub.configure(text=s),
        ))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _on_close(self):
        self._running.clear()
        self._aim_active.clear()
        if self._custodian:
            self._custodian.stop()
        for w in [self._aim_overlay, self._translator_win]:
            if w:
                try:
                    w.destroy()
                except Exception:
                    pass
        self._face.stop()
        self.destroy()
