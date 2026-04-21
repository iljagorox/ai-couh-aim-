# -*- coding: utf-8 -*-
import json
import threading
import time
from datetime import datetime

class MemoryStore:
    def __init__(self, path="sentinel_memory.json", limit=200):
        self.path = path
        self.limit = limit
        self.data = {
            "facts": [],
            "task_history": [],
            "command_history": [],
            "aim_notes": [],
            "aim_qa": [],
            "insights": [],
            "dialog_history": [],
            "stats": {
                "aim_questions": 0,
                "aim_answers": 0,
                "aim_auto_advices": 0,
                "aim_sessions_started": 0,
                "aim_manual_notes": 0,
            },
        }
        self._lock = threading.Lock()
        self._dirty = False
        self._save_thread = None
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            with self._lock:
                for key in self.data:
                    if key in loaded:
                        self.data[key] = loaded[key]
                self.data.setdefault("aim_qa", [])
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_async(self):
        time.sleep(1.0)
        with self._lock:
            if not self._dirty:
                return
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
                self._dirty = False
            except Exception as e:
                print(f"[Memory] Ошибка сохранения: {e}")
            self._save_thread = None

    def save(self):
        with self._lock:
            self._dirty = True
            if self._save_thread is None or not self._save_thread.is_alive():
                self._save_thread = threading.Thread(target=self._save_async, daemon=True)
                self._save_thread.start()

    def _trim(self, key):
        items = self.data.get(key, [])
        if len(items) > self.limit:
            self.data[key] = items[-self.limit:]

    def _append(self, key, payload):
        payload["timestamp"] = datetime.now().isoformat(timespec="seconds")
        items = self.data.setdefault(key, [])
        if key in ("facts", "aim_notes", "insights", "dialog_history"):
            text_field = {
                "facts": "text",
                "aim_notes": "advice",
                "insights": "insight",
                "dialog_history": "content"
            }.get(key, "text")
            new_text = payload.get(text_field, "")
            for item in items:
                if item.get(text_field) == new_text:
                    item["timestamp"] = payload["timestamp"]
                    self.save()
                    return
        items.append(payload)
        self._trim(key)
        self.save()

    # ---------- Диалог ----------
    def add_dialog_message(self, role: str, content: str):
        self._append("dialog_history", {"role": role, "content": content})

    def get_recent_dialog(self, count: int = 10) -> list:
        items = self.data.get("dialog_history", [])
        return items[-count:] if items else []

    # ---------- Остальные методы без изменений ----------
    def remember_fact(self, text, source="system"):
        if not text or source in ("runtime",):
            return
        self._append("facts", {"text": text, "source": source})

    def remember_task(self, task, outcome, last_command=""):
        if not task:
            return
        self._append("task_history", {"task": task, "outcome": outcome, "last_command": last_command})

    def remember_command(self, task, command, executed, screen_desc=""):
        if not command:
            return
        self._append("command_history", {
            "task": task,
            "command": command,
            "executed": executed,
            "screen_desc": screen_desc[:500],
        })

    def remember_aim_note(self, screen_desc, advice):
        if not advice:
            return
        self._append("aim_notes", {"screen_desc": screen_desc[:500], "advice": advice, "kind": "auto_screen"})
        self.bump_stat("aim_auto_advices")

    def remember_aim_qa(self, question: str, answer: str, profile: str = ""):
        q = (question or "").strip()
        a = (answer or "").strip()
        if not q or not a:
            return
        payload = {"question": q[:2000], "answer": a[:4500], "profile": profile[:120]}
        items = self.data.setdefault("aim_qa", [])
        for it in items:
            if it.get("question", "").strip() == q:
                it["answer"] = payload["answer"]
                it["profile"] = payload["profile"]
                it["timestamp"] = datetime.now().isoformat(timespec="seconds")
                self.save()
                return
        payload["timestamp"] = datetime.now().isoformat(timespec="seconds")
        items.append(payload)
        self._trim("aim_qa")
        self.save()

    def remember_insight(self, text, source="aim", confidence=0.5):
        if not text:
            return
        self._append("insights", {"insight": text, "source": source, "confidence": confidence})

    def recent_summary(self, key, count=5):
        items = self.data.get(key, [])
        return items[-count:] if items else []

    def get_insights(self, count=10):
        items = self.data.get("insights", [])
        return [item.get("insight", "") for item in items[-count:][::-1]]

    def get_aim_qa_pairs(self, count=8):
        items = self.data.get("aim_qa", [])
        return items[-count:] if items else []

    def bump_stat(self, key, amount=1):
        stats = self.data.setdefault("stats", {})
        stats[key] = int(stats.get(key, 0)) + amount
        self.save()

    def get_aim_stats(self):
        stats = self.data.setdefault("stats", {})
        return {
            "aim_questions": int(stats.get("aim_questions", 0)),
            "aim_answers": int(stats.get("aim_answers", 0)),
            "aim_auto_advices": int(stats.get("aim_auto_advices", 0)),
            "aim_sessions_started": int(stats.get("aim_sessions_started", 0)),
            "aim_manual_notes": int(stats.get("aim_manual_notes", 0)),
        }

    def aim_rank_guess(self):
        stats = self.get_aim_stats()
        activity = stats["aim_auto_advices"] + stats["aim_answers"]*2 + stats["aim_questions"]*2 + stats["aim_sessions_started"]*3
        if activity < 6: return "Железо"
        if activity < 14: return "Бронза"
        if activity < 24: return "Серебро"
        if activity < 36: return "Золото"
        if activity < 48: return "Платина"
        return "Алмаз+"

    def compact(self, keep_last=50):
        for key in ("facts", "task_history", "command_history", "aim_notes", "aim_qa", "insights", "dialog_history"):
            items = self.data.get(key, [])
            self.data[key] = items[-keep_last:]
        self.save()

    def ui_aim_summary(self, lines_each=3):
        out = []
        for i in self.get_insights(count=lines_each):
            if i:
                out.append(f"🧠 {i[:160]}{'…' if len(i) > 160 else ''}")
        qa = self.get_aim_qa_pairs(1)
        if qa:
            q = qa[-1]
            out.append(f"❓ {q.get('question', '')[:100]}…")
            out.append(f"💬 {q.get('answer', '')[:120]}…")
        return out or ["Память коуча пуста."]