# -*- coding: utf-8 -*-
import json
import re
import threading
import queue
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable
import customtkinter as ctk
import ollama

SAGA_SETTINGS = {
    "cyber": "Неоновый мегаполис 2089",
    "fantasy": "Тёмное фэнтези",
}
DEFAULT_CHOICES = ["Идти дальше", "Осмотреться", "Ждать"]

@dataclass
class SagaState:
    setting_key: str = "cyber"
    turn: int = 0
    hp: int = 5
    inventory: List[str] = field(default_factory=list)
    transcript: List[dict] = field(default_factory=list)
    last_choices: List[str] = field(default_factory=list)
    ended: bool = False

    def to_dict(self):
        return {
            "setting_key": self.setting_key,
            "turn": self.turn,
            "hp": self.hp,
            "inventory": self.inventory,
            "transcript": self.transcript,
            "last_choices": self.last_choices,
            "ended": self.ended,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            setting_key=d.get("setting_key", "cyber"),
            turn=d.get("turn", 0),
            hp=d.get("hp", 5),
            inventory=d.get("inventory", []),
            transcript=d.get("transcript", []),
            last_choices=d.get("last_choices", []),
            ended=d.get("ended", False),
        )

class SagaEngine:
    def __init__(self, core, memory_store=None, save_path="saga_save.json"):
        self.core = core
        self.memory_store = memory_store
        self.save_path = save_path
        self.state = SagaState()
        self.model = core.brain_model
        self.load()

    def load(self):
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                self.state = SagaState.from_dict(json.load(f))
        except Exception:
            pass

    def save(self):
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)

    def new_game(self, setting_key: str):
        self.state = SagaState(setting_key=setting_key)
        self.save()

    def step(self, player_line: str):
        player_line = player_line.strip() or "…"
        self.state.transcript.append({"role": "player", "text": player_line})
        setting_name = SAGA_SETTINGS.get(self.state.setting_key, '')
        system = (
            f"Ты мастер саги. Сеттинг: {setting_name}. HP={self.state.hp}. "
            f"Пиши СТРОГО 2-3 предложения нарратива, затем 3 варианта действий. "
            f"Формат: нарратив\nВАРИАНТЫ:\n1. ...\n2. ...\n3. ..."
        )
        user = f"Хроника:\n{self._transcript_block()}\nХод игрока: {player_line}"
        raw = self._ollama([{"role": "system", "content": system}, {"role": "user", "content": user}], 0.65)
        narrative, choices = self._parse(raw)
        # Ограничиваем длину нарратива
        if len(narrative) > 480:
            narrative = narrative[:480].rsplit('.', 1)[0] + '.'
        self.state.transcript.append({"role": "gm", "text": narrative})
        self.state.last_choices = choices
        self.state.turn += 1
        self.save()
        return narrative, choices, self.state.ended

    def _ollama(self, msgs, temp):
        opts = self.core.ollama_chat_options(temp)
        opts["num_predict"] = 180  # было 400 — снижено для краткости
        r = ollama.chat(model=self.model, messages=msgs, options=opts, keep_alive=-1)
        return r["message"]["content"]

    def _transcript_block(self):
        lines = []
        # Сокращено с 10 до 6 последних сообщений
        for msg in self.state.transcript[-6:]:
            role = "Игрок" if msg.get("role") == "player" else "Мастер"
            text = msg.get('text', '')
            # Усекаем длинные записи в истории
            if len(text) > 200:
                text = text[:200] + "…"
            lines.append(f"{role}: {text}")
        return "\n".join(lines) or "(начало истории)"

    def _parse(self, raw: str):
        text = raw.strip()
        parts = re.split(r"(?i)ВАРИАНТЫ\s*:", text, maxsplit=1)
        narrative = parts[0].strip()
        choices = []
        if len(parts) > 1:
            for line in parts[1].strip().splitlines():
                m = re.match(r"^\s*\d+[\.\)]\s*(.+)$", line)
                if m:
                    c = m.group(1).strip()
                    # Ограничиваем длину варианта
                    if len(c) > 60:
                        c = c[:60] + "…"
                    choices.append(c)
        while len(choices) < 3:
            choices.append(DEFAULT_CHOICES[len(choices)])
        return narrative, choices[:3]

class SagaPlayWindow(ctk.CTkToplevel):
    def __init__(self, master, core, memory_store=None, skin=None, log_fn=None):
        super().__init__(master)
        self.core = core
        self.memory = memory_store
        self.log = log_fn or print
        self.engine = SagaEngine(core, memory_store)
        self._work_q = queue.Queue()
        self._busy = False

        self.title("Сага")
        self.geometry("700x600")
        self._build_ui()
        self.after(100, self._poll_queue)

    def _build_ui(self):
        self.story = ctk.CTkTextbox(self, wrap="word")
        self.story.pack(fill="both", expand=True, padx=10, pady=10)
        self.entry = ctk.CTkEntry(self, placeholder_text="Ваш ход...")
        self.entry.pack(fill="x", padx=10, pady=5)
        self.entry.bind("<Return>", lambda e: self._send())
        ctk.CTkButton(self, text="Отправить", command=self._send).pack(pady=5)
        ctk.CTkButton(self, text="Новая игра", command=self._new_game).pack(pady=5)

    def _send(self):
        if self._busy:
            return
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._busy = True
        self._story_append(f"\n> {text}\n")
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def _worker(self, text):
        try:
            nar, ch, end = self.engine.step(text)
            self._work_q.put(("ok", nar, ch, end))
        except Exception as e:
            self._work_q.put(("err", str(e)))

    def _poll_queue(self):
        try:
            while True:
                item = self._work_q.get_nowait()
                self._busy = False
                if item[0] == "err":
                    self._story_append(f"\n[Ошибка: {item[1]}]\n")
                elif item[0] == "ok":
                    _, nar, ch, end = item
                    self._story_append(nar + "\n")
                    if ch:
                        self._story_append("\n".join(f"{i+1}. {c}" for i, c in enumerate(ch)) + "\n")
        except queue.Empty:
            pass
        self.after(200, self._poll_queue)

    def _story_append(self, s):
        self.story.insert("end", s)
        self.story.see("end")

    def _new_game(self):
        self.engine.new_game("cyber")
        self.story.delete("1.0", "end")
        self._story_append("Новая сага началась!\n")
