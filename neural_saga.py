# -*- coding: utf-8 -*-
from __future__ import annotations
import json, os, re, threading, queue, time, random, math
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import customtkinter as ctk
import tkinter as tk
import ollama
from PIL import Image, ImageTk
from saga_world import SagaWorld, FpsRenderer, SagaPhysics, SagaRenderer, Entity, Layer, TILE_FLOOR, TILE_WALL, TILE_ROAD, TILE_GRASS, TILE_WATER, TILE_DOOR
from saga_engine import SagaEngine
from saga_renderer import SceneRenderer
from saga_data import SAGA_SETTINGS, MOOD_STYLE, DEFAULT_CHOICES, SCENE_LABELS

SAGA_SETTINGS: dict
MOOD_STYLE: dict
DEFAULT_CHOICES: list
SCENE_LABELS: dict


class SagaPlayWindow(ctk.CTkToplevel):
    def __init__(self, master, core, memory_store=None, skin="cyber", log_fn=None):
        super().__init__(master)
        self.core = core
        self.memory_store = memory_store
        self.log = log_fn or print
        self.skin = skin
        self.engine = SagaEngine(core, memory_store)
        self._work_q: queue.Queue = queue.Queue()
        self._busy = False
        setting = SAGA_SETTINGS.get(skin, SAGA_SETTINGS["cyber"])
        self.title(f"Сага: {setting['name']}")
        self.attributes("-fullscreen", True)
        self.configure(fg_color=setting["palette"]["bg"])
        self._palette = setting["palette"]
        self._choice_buttons: List[ctk.CTkButton] = []
        self._game_running = True
        self._game_tick = 0.0
        self._player_angle = 0.0
        self._keys: set = set()
        self.scene_renderer = SceneRenderer()
        self.fps_renderer = None
        self._render_tk = None
        self._build_ui()
        self.after(100, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))
        self.bind("<F11>", lambda e: self.attributes("-fullscreen", not self.attributes("-fullscreen")))
        self.bind("<KeyPress>", self._on_saga_key_press)
        self.bind("<KeyRelease>", self._on_saga_key_release)
        existing = self.engine.list_worlds()
        if existing:
            self._show_world_picker(existing)
        else:
            self._start_new_world()

    def _show_world_picker(self, worlds):
        self._loading_frame = ctk.CTkFrame(self, fg_color=self._palette["card"], width=480, height=320)
        self._loading_frame.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(self._loading_frame, text="\U0001f3e0  ЗАГРУЗИТЬ МИР",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=self._palette["accent"]).pack(pady=(16, 8))
        for seed, turns in worlds[:6]:
            ctk.CTkButton(
                self._loading_frame, text=f"Мир {seed} — {turns} ходов",
                height=36, fg_color="transparent", hover_color=self._palette["accent"],
                text_color=self._palette["text"], border_color=self._palette["accent"],
                border_width=2, corner_radius=0,
                command=lambda s=seed: self._load_existing_world(s)
            ).pack(fill="x", padx=30, pady=3)
        ctk.CTkButton(
            self._loading_frame, text="+ НОВЫЙ МИР",
            height=36, fg_color=self._palette["accent"],
            text_color="#000", corner_radius=0,
            command=self._start_new_world
        ).pack(pady=(14, 8))

    def _load_existing_world(self, seed):
        try:
            self._loading_frame.destroy()
        except Exception:
            pass
        ok = self.engine.load_world(seed)
        if ok:
            self.fps_renderer = FpsRenderer(self.engine.world)
            self.fps_renderer.view_w = 480
            self.fps_renderer.view_h = 140
            self._restore_history()
            self._update_status()
            self._set_choices(list(DEFAULT_CHOICES))
            self._start_background_timer()
            self.after(10, self._start_game_loop)
        else:
            self._start_new_world()

    def _start_new_world(self):
        try:
            self._loading_frame.destroy()
        except Exception:
            pass
        self.engine.new_game(self.skin)
        self.fps_renderer = FpsRenderer(self.engine.world)
        self.fps_renderer.view_w = 480
        self.fps_renderer.view_h = 140
        setting = SAGA_SETTINGS.get(self.skin, SAGA_SETTINGS["cyber"])
        seed_str = str(self.engine.world.seed)
        self._loading_frame = ctk.CTkFrame(self, fg_color=setting["palette"]["card"], width=460, height=200)
        self._loading_frame.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(self._loading_frame, text="\U0001f30d  ГЕНЕРАЦИЯ МИРА",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=setting["palette"]["accent"]).pack(pady=(16, 2))
        seed_display = seed_str[:3] + ' ' + seed_str[3:]
        ctk.CTkLabel(self._loading_frame, text=f"seed: {seed_display}",
                     font=ctk.CTkFont(family="Cascadia Mono", size=14),
                     text_color=setting["palette"]["neon_cyan"]).pack(pady=(0, 8))
        self._loading_eta = ctk.CTkLabel(self._loading_frame, text="Оценка: ~30 секунд",
                                          font=ctk.CTkFont(size=12),
                                          text_color=setting["palette"]["sub"])
        self._loading_eta.pack(pady=(0, 6))
        self._progress = ctk.CTkProgressBar(self._loading_frame, width=380, height=14,
                                             corner_radius=0,
                                             fg_color=setting["palette"]["dark"],
                                             progress_color=setting["palette"]["accent"])
        self._progress.pack(pady=(0, 4))
        self._progress.set(0.0)
        ctk.CTkLabel(self._loading_frame, text="ИИ создаёт вселенную...",
                     font=ctk.CTkFont(size=10),
                     text_color=setting["palette"]["sub"]).pack()
        self._loading_start = time.time()
        self.after(200, self._init_world_async)

    def _on_saga_key_press(self, event):
        if event.widget == self.entry:
            return
        k = event.char.lower()
        if k in ('w', 'a', 's', 'd', 'q', 'e'):
            self._keys.add(k)
        if k == '\r' and self._busy:
            self._send_custom()

    def _on_saga_key_release(self, event):
        k = event.char.lower()
        if k in ('w', 'a', 's', 'd', 'q', 'e'):
            self._keys.discard(k)

    def _build_ui(self):
        p = self._palette
        hud = ctk.CTkFrame(self, fg_color=p["card"], height=36)
        hud.pack(fill="x", padx=12, pady=(10, 3))
        self._hud_left = ctk.CTkFrame(hud, fg_color="transparent")
        self._hud_left.pack(side="left", fill="y")
        self._hp_lbl = ctk.CTkLabel(self._hud_left, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self._hp_lbl.pack(side="left", padx=6)
        self._lvl_lbl = ctk.CTkLabel(self._hud_left, text="", font=ctk.CTkFont(size=11, weight="bold"),
                                      text_color=p["accent"])
        self._lvl_lbl.pack(side="left", padx=4)
        self._xp_bar = ctk.CTkProgressBar(self._hud_left, width=60, height=10, corner_radius=0,
                                           fg_color=p["dark"], progress_color=p["neon_cyan"])
        self._xp_bar.pack(side="left", padx=4)
        self._st_lbl = ctk.CTkLabel(hud, text="", font=ctk.CTkFont(size=10), text_color=p["sub"])
        self._st_lbl.pack(side="left", padx=2)
        self._hud_right = ctk.CTkFrame(hud, fg_color="transparent")
        self._hud_right.pack(side="right", fill="y")
        self._mood_lbl = ctk.CTkLabel(self._hud_right, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self._mood_lbl.pack(side="right", padx=6)
        self._inv_lbl = ctk.CTkLabel(self._hud_right, text="", font=ctk.CTkFont(size=10), text_color=p["sub"])
        self._inv_lbl.pack(side="right", padx=6)
        self._ent_lbl = ctk.CTkLabel(self._hud_right, text="", font=ctk.CTkFont(size=10), text_color=p["sub"])
        self._ent_lbl.pack(side="right", padx=6)
        self._pos_lbl = ctk.CTkLabel(self._hud_right, text="", font=ctk.CTkFont(size=10), text_color=p["sub"])
        self._pos_lbl.pack(side="right", padx=6)
        self._compass_lbl = ctk.CTkLabel(self._hud_right, text="", font=ctk.CTkFont(size=10), text_color=p["sub"])
        self._compass_lbl.pack(side="right", padx=4)
        self._map_canvas = tk.Canvas(self._hud_right, bg="#050510", highlightthickness=0, width=80, height=28)
        self._map_canvas.pack(side="right", padx=4)
        self._visual_cache = ""
        self._art_frame = ctk.CTkFrame(self, fg_color="#080808",
                                        border_color=p["accent"], border_width=2)
        self._art_frame.pack(fill="x", padx=12, pady=(0, 3))
        self._art_canvas = tk.Canvas(
            self._art_frame, bg="#080808", highlightthickness=0, height=320)
        self._art_canvas.pack(fill="x")
        self._art_canvas.bind("<Configure>", self._on_canvas_resize)
        self.story = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Consolas", size=14),
            fg_color="#080808", text_color=p["text"], wrap="word",
            border_color=p["accent"], border_width=2,
            state="disabled", takefocus=0)
        self.story.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.story.bind("<Button-1>", lambda e: "break")
        self.story.bind("<Button-2>", lambda e: "break")
        self.story.bind("<Button-3>", lambda e: "break")
        self._choice_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._choice_frame.pack(fill="x", padx=12, pady=(0, 6))
        inp = ctk.CTkFrame(self, fg_color="transparent")
        inp.pack(fill="x", padx=12, pady=(0, 6))
        self.entry = ctk.CTkEntry(
            inp, placeholder_text="Твоё действие...",
            height=40, font=ctk.CTkFont(size=14),
            fg_color="#111111", border_color=p["accent"], border_width=2)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda _: self._send_custom())
        ctk.CTkButton(inp, text="\u25b6", width=56, height=40, corner_radius=0,
                      fg_color=p["accent"], hover_color="#ff2a4a",
                      command=self._send_custom).pack(side="left")
        ctk.CTkButton(self, text="НОВАЯ ИГРА", width=140, height=32, corner_radius=0,
                      fg_color="transparent", hover_color=p["accent"],
                      text_color=p["accent"], border_color=p["accent"], border_width=2,
                      command=self._new_game).pack(pady=(0, 10))

    def _start_game_loop(self):
        if not self._game_running:
            return
        self._game_loop()

    def _game_loop(self):
        if not self._game_running:
            return
        dt = 0.05
        self._game_tick += dt
        player = self.engine.world.get_player()
        if player:
            agi = player.agility
            speed = max(0.5, player.speed * 1.5 + agi * 0.3)
            turn_spd = 2.0 + agi * 0.1
            dx, dy = 0.0, 0.0
            if 'w' in self._keys:
                dx += math.cos(self._player_angle) * speed * dt
                dy += math.sin(self._player_angle) * speed * dt
            if 's' in self._keys:
                dx -= math.cos(self._player_angle) * speed * dt
                dy -= math.sin(self._player_angle) * speed * dt
            if 'a' in self._keys:
                self._player_angle -= turn_spd * dt
            if 'd' in self._keys:
                self._player_angle += turn_spd * dt
            if 'q' in self._keys:
                dx += math.cos(self._player_angle - math.pi/2) * speed * dt
                dy += math.sin(self._player_angle - math.pi/2) * speed * dt
            if 'e' in self._keys:
                dx += math.cos(self._player_angle + math.pi/2) * speed * dt
                dy += math.sin(self._player_angle + math.pi/2) * speed * dt
            if dx != 0 or dy != 0:
                nx, ny = player.x + dx, player.y + dy
                if not self.engine.world.is_solid(nx, ny):
                    player.x, player.y = nx, ny
                elif not self.engine.world.is_solid(nx, player.y):
                    player.x = nx
                elif not self.engine.world.is_solid(player.x, ny):
                    player.y = ny
            self.engine.physics.tick(dt)
            for eid, xp_amt in self.engine.physics.pending_xp:
                if eid == (player.eid if player else -1):
                    self.engine.state.add_xp(xp_amt)
                    self._show_level_up(self.engine.state.level)
            self.engine.physics.pending_xp.clear()
            self._render_fps_frame()
            self._update_fps_hud()
        self.after(50, self._game_loop)

    def _on_canvas_resize(self, event=None):
        pass  # размер подхватится в следующем _render_fps_frame

    def _render_fps_frame(self):
        cw = max(320, self._art_canvas.winfo_width())
        ch = max(180, self._art_canvas.winfo_height())
        desired_ch = max(180, cw * 9 // 32)
        if abs(ch - desired_ch) > 2:
            self._art_canvas.configure(height=desired_ch)
            ch = desired_ch
        if cw < 10 or ch < 10:
            return
        img = self.scene_renderer.render(self._visual_cache, out_w=cw, out_h=ch)
        if img:
            self._render_tk = ImageTk.PhotoImage(img)
            self._art_canvas.delete("all")
            self._art_canvas.create_image(0, 0, anchor="nw", image=self._render_tk)

    def _show_level_up(self, lvl: int):
        try:
            self.story.configure(state="normal")
            self.story.insert("end", f"\n  \u2728 УРОВЕНЬ {lvl}! \u2728\n", ("levelup",))
            self.story.tag_config("levelup", foreground=self._palette["accent"],
                                  font=ctk.CTkFont(size=16, weight="bold"))
            self.story.see("end")
            self.story.configure(state="disabled")
        except Exception:
            pass

    def _update_fps_hud(self):
        player = self.engine.world.get_player()
        st = self.engine.state
        w = self.engine.world
        hp_bars = "\u2764\ufe0f" * st.hp + "\U0001f7a4" * (st.max_hp - st.hp)
        self._hp_lbl.configure(text=f"HP {st.hp}/{st.max_hp} {hp_bars}")
        self._lvl_lbl.configure(text=f"Lv.{st.level}")
        xp_pct = st.xp / max(st.next_level_xp, 1)
        self._xp_bar.set(xp_pct)
        stxt = f"\u2694{st.stats.get('strength',5)} \U0001f3c3{st.stats.get('agility',5)} \U0001f441{st.stats.get('perception',5)} \U0001f9e0{st.stats.get('intelligence',5)} \U0001f399{st.stats.get('charisma',5)}"
        self._st_lbl.configure(text=stxt)
        if player:
            deg = int(math.degrees(self._player_angle) % 360)
            self._pos_lbl.configure(text=f"x:{player.x:.0f} y:{player.y:.0f}")
            dirs = ['\u2191','\u2197','\u2192','\u2198','\u2193','\u2199','\u2190','\u2196']
            compass_idx = int((deg + 22.5) // 45) % 8
            weather_icons = {'clear': '\u2600', 'rain': '\U0001f327', 'fog': '\U0001f32b', 'drizzle': '\U0001f4a7', 'overcast': '\u2601'}
            wi = weather_icons.get(w.weather, '?')
            day_icon = '\U0001f31b' if w.daylight < 0.3 else '\U0001f311' if w.daylight < 0.5 else '\u2600'
            self._compass_lbl.configure(text=f"{dirs[compass_idx]} {deg}\u00b0 {wi}{day_icon}")
            self._render_minimap(player)
        alive = sum(1 for e in w.entities.values()
                    if e.alive and e.eid != (player.eid if player else -1))
        self._ent_lbl.configure(text=f"\U0001f464 {alive} seed:{w.seed}")
        ms = MOOD_STYLE.get(st.mood, MOOD_STYLE["neutral"])
        self._mood_lbl.configure(text=f"{ms['emoji']} {ms['dream']}")
        inv_text = ', '.join(st.inventory[-4:]) if st.inventory else ""
        self._inv_lbl.configure(text=inv_text)

    def _render_minimap(self, player):
        w = self.engine.world
        mw, mh = 20, 8
        px, py = int(player.x), int(player.y)
        tw = 4
        self._map_canvas.delete("all")
        for dy in range(-mh // 2, mh // 2 + 1):
            for dx in range(-mw // 2, mw // 2 + 1):
                tx, ty = px + dx, py + dy
                x0 = (dx + mw // 2) * tw
                y0 = (dy + mh // 2) * tw
                if dx == 0 and dy == 0:
                    self._map_canvas.create_rectangle(x0, y0, x0 + tw, y0 + tw, fill="#00ccff", outline="")
                elif 0 <= tx < w.width and 0 <= ty < w.height:
                    tile = w.grid[ty][tx]
                    is_npc = any(e.alive and e.kind != 'player' and int(e.x) == tx and int(e.y) == ty for e in w.entities.values())
                    if is_npc:
                        fill = "#ffaa44"
                    elif tile == 0:
                        fill = "#334"
                    elif tile == 1:
                        fill = "#111"
                    elif tile == 2:
                        fill = "#443322"
                    elif tile == 3:
                        fill = "#284a2a"
                    elif tile == 6:
                        fill = "#ddaa44"
                    else:
                        fill = "#222"
                    self._map_canvas.create_rectangle(x0, y0, x0 + tw, y0 + tw, fill=fill, outline="")
                else:
                    self._map_canvas.create_rectangle(x0, y0, x0 + tw, y0 + tw, fill="#000", outline="")

    def _restore_history(self):
        for msg in self.engine.state.transcript:
            role = msg.get("role", "")
            if role in ("player", "user"):
                self._append_player(msg.get("text", ""))
            elif role in ("gm", "assistant"):
                self._append_gm(msg.get("text", ""), msg.get("mood", "neutral"))
        self._update_status()

    def _on_close(self):
        self._game_running = False
        self.destroy()

    def _init_world_async(self):
        def progress_tick():
            if not self._game_running or not hasattr(self, '_progress'):
                return
            elapsed = time.time() - self._loading_start
            p = min(0.93, elapsed / 25.0)
            try:
                self._progress.set(p)
                remaining = max(1, int(25 - elapsed))
                self._loading_eta.configure(text=f"~{remaining} \u0441\u0435\u043a...")
            except Exception:
                pass
            if p < 0.93:
                self.after(400, progress_tick)
        def work():
            ok = self.engine._ai_generate_world()
            self.after(0, lambda: self._on_world_ready(ok))
        progress_tick()
        threading.Thread(target=work, daemon=True).start()

    def _on_world_ready(self, ok):
        try:
            self._loading_frame.destroy()
        except Exception:
            pass
        if not ok:
            self._append_gm("Мир загружен из шаблона.", "neutral")
        self._start_prologue()
        self.after(10, self._start_game_loop)

    def _start_prologue(self):
        setting = SAGA_SETTINGS.get(self.skin, SAGA_SETTINGS["cyber"])
        prologue = (
            f"Добро пожаловать в «{setting['name']}».\n\n"
            f"{setting['vibe']}.\n\n"
            f"Всё начинается здесь... Что делаешь?"
        )
        self._append_gm(prologue, "neutral")
        self._set_choices(list(DEFAULT_CHOICES))
        self._start_background_timer()
        threading.Thread(target=self._worker, args=("\u043d\u0430\u0447\u0430\u043b\u043e \u0438\u0433\u0440\u044b",), daemon=True).start()

    def _start_background_timer(self):
        def tick():
            if not self._game_running:
                return
            events = self.engine._background_evolve()
            self.after(0, lambda: self._show_background_events(events))
            self.after(25000, tick)
        self.after(25000, tick)

    def _show_background_events(self, events):
        if not events:
            return
        try:
            self.story.configure(state="normal")
            for e in events:
                self.story.insert("end", f"  \u00b7 {e}\n", ("bg_event",))
            self.story.tag_config("bg_event", foreground=self._palette["sub"], spacing1=2, spacing3=2,
                                  font=ctk.CTkFont(size=12, slant="italic"))
            self.story.see("end")
            self.story.configure(state="disabled")
        except Exception:
            pass

    def _update_status(self):
        self._update_fps_hud()

    def _append_player(self, text: str):
        self.story.configure(state="normal")
        self.story.insert("end", f"\nВы > {text}\n", ("player",))
        self.story.tag_config("player", foreground=self._palette["accent"])
        self.story.see("end")
        self.story.configure(state="disabled")

    def _append_gm(self, text: str, mood: str = "neutral"):
        p = self._palette
        from saga_engine import _scene_label
        label = _scene_label(self.engine.state.setting_key, text)
        style = MOOD_STYLE.get(mood, MOOD_STYLE["neutral"])
        color = style["color"] if style["color"] != "text" else p["text"]
        self.story.configure(state="normal")
        self.story.insert("end", label, ("label",))
        self.story.tag_config("label", foreground=p["sub"])
        self.story.insert("end", f"{style['inline']}  {text}\n\n", (f"mood_{mood}",))
        self.story.tag_config(f"mood_{mood}", foreground=color, spacing1=4, spacing3=10, lmargin1=10, lmargin2=10)
        self.story.see("end")
        self.story.configure(state="disabled")

    def _set_choices(self, choices: List[str]):
        self._last_choices = choices
        for btn in self._choice_buttons:
            btn.destroy()
        self._choice_buttons.clear()
        for i, choice in enumerate(choices):
            btn = ctk.CTkButton(
                self._choice_frame, text=f"  [{i+1}]  {choice}", height=34,
                fg_color="transparent", hover_color=self._palette["accent"],
                text_color=self._palette["text"], border_color=self._palette["accent"],
                border_width=2, corner_radius=0, font=ctk.CTkFont(size=13),
                command=lambda c=choice: self._send_choice(c))
            btn.pack(fill="x", pady=3)
            self._choice_buttons.append(btn)

    BLOCKED = ['ядерк', 'ядерн', 'бомб', 'взрывчатк', 'бессмерт', 'всемогущ',
                'всесил', 'бог', 'читер', 'баг', 'взлом', 'админ',
                'телепорт', 'миллион', 'триллион', 'бесконечн', 'атомн',
                'оружи масс']

    def _is_safe_input(self, text: str) -> bool:
        lower = text.lower()
        for p in self.BLOCKED:
            if p in lower:
                return False
        return len(text) <= 200

    def _send_choice(self, text: str):
        if self._busy:
            return
        if text == "Начать заново":
            self._new_game()
            return
        if not self._is_safe_input(text):
            self._append_gm("Мир не реагирует на такие слова. Попробуй иначе.", "neutral")
            self._set_choices(self._last_choices if hasattr(self, '_last_choices') else list(DEFAULT_CHOICES))
            return
        self._busy = True
        self._set_choices([])
        self.entry.configure(state="disabled")
        self._append_player(text)
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def _send_custom(self):
        if self._busy:
            return
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._send_choice(text)

    def _worker(self, text):
        try:
            nar, mood, visual, choices, ended = self.engine.step(text)
            self._work_q.put(("ok", nar, mood, visual, choices, ended))
        except Exception as e:
            self._work_q.put(("err", str(e)))

    def _poll_queue(self):
        try:
            while True:
                item = self._work_q.get_nowait()
                self._busy = False
                self.entry.configure(state="normal")
                if item[0] == "err":
                    self._append_gm(f"Ошибка: {item[1]}", "tense")
                    self._set_choices(list(DEFAULT_CHOICES))
                else:
                    _, nar, mood, visual, choices, ended = item
                    self._visual_cache = visual
                    self._append_gm(nar, mood)
                    self._update_status()
                    if ended:
                        self._set_choices(["Начать заново"])
                        self._append_gm("Сага завершена. Нажми «Новая игра» для перезапуска.", "calm")
                    else:
                        self._set_choices(choices)
        except queue.Empty:
            pass
        self.after(200, self._poll_queue)

    def _new_game(self):
        self._game_running = False
        self.after(100, self._do_new_game)

    def _do_new_game(self):
        self.scene_renderer = SceneRenderer()
        self._player_angle = 0.0
        self._keys.clear()
        self._game_tick = 0.0
        self.story.configure(state="normal")
        self.story.delete("1.0", "end")
        self.story.configure(state="disabled")
        self._art_canvas.delete("all")
        self._render_tk = None
        self._game_running = True
        self._start_new_world()
