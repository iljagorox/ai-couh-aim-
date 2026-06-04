# -*- coding: utf-8 -*-
import json, os, threading, time, random
from pathlib import Path
from datetime import datetime
from typing import Optional
import ollama

DREAMS_DIR = "saga_saves/dreams"
SLEEP_INTERVAL = 300  # 5 min idle → dream cycle
MIN_REFLECTION_INTERVAL = 600  # 10 min between reflections


class SleepCycle:
    def __init__(self, core, memory_store=None):
        self.core = core
        self.memory_store = memory_store
        self._running = False
        self._last_reflection = 0.0
        self._last_active_time = time.time()
        self._dream_log: list[dict] = []
        self._insights: list[str] = []
        self._skill_compressions: list[str] = []
        self._load_dreams()
        os.makedirs(DREAMS_DIR, exist_ok=True)

    def _load_dreams(self):
        path = os.path.join(DREAMS_DIR, "dreams.json")
        if os.path.isfile(path):
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                self._dream_log = data.get("dreams", [])
                self._insights = data.get("insights", [])
                self._skill_compressions = data.get("skills", [])
            except Exception:
                pass

    def _save_dreams(self):
        path = os.path.join(DREAMS_DIR, "dreams.json")
        Path(path).write_text(json.dumps({
            "dreams": self._dream_log[-50:],
            "insights": self._insights[-20:],
            "skills": self._skill_compressions[-20:],
            "updated": datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def mark_active(self):
        self._last_active_time = time.time()

    def start(self):
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._cycle, daemon=True).start()
        print("[SleepCycle] Запущен")

    def stop(self):
        self._running = False

    def _cycle(self):
        while self._running:
            idle_time = time.time() - self._last_active_time
            if idle_time > SLEEP_INTERVAL:
                self._dream_cycle()
            time.sleep(60)

    def _dream_cycle(self):
        now = time.time()
        if now - self._last_reflection < MIN_REFLECTION_INTERVAL:
            return
        self._last_reflection = now
        try:
            self._reflect_on_history()
            self._compress_skills()
            self._generate_dream()
            self._save_dreams()
        except Exception as e:
            print(f"[SleepCycle] Ошибка цикла: {e}")

    def _get_recent_context(self) -> str:
        parts = []
        if self.memory_store:
            diag = self.memory_store.get_recent_dialog(6)
            if diag:
                parts.append("Диалоги:\n" + "\n".join(
                    f"{m['role']}: {m['content'][:200]}" for m in diag
                ))
            facts = self.memory_store.get_recent_facts(8)
            if facts:
                parts.append("Факты:\n" + "\n".join(facts))
        skill_str = "\n".join(self._skill_compressions[-5:]) if self._skill_compressions else "нет"
        parts.append(f"Навыки:\n{skill_str}")
        return "\n\n".join(parts)

    def _reflect_on_history(self):
        ctx = self._get_recent_context()
        if len(ctx) < 50:
            return
        prompt = (
            f"Ты — ИИ, который анализирует свою работу. Посмотри на историю диалогов и задач:\n\n"
            f"{ctx}\n\n"
            f"Верни JSON:\n"
            f"{{\n"
            f'  "insight": "один важный инсайт о том, что ты узнал о пользователе или о своей работе (1-2 предложения)",\n'
            f'  "pattern": "заметил ли ты повторяющийся паттерн в запросах или ошибках (1 предложение)",\n'
            f'  "improvement": "что можно улучшить в следующем ответе или действии (1 предложение)"\n'
            f"}}\n"
            f"Только JSON, без пояснений."
        )
        try:
            opts = self.core.ollama_chat_options(0.3)
            opts["num_predict"] = 300
            r = ollama.chat(model=self.core.brain_model, messages=[
                {"role": "system", "content": "Ты — рефлексирующий ИИ. Анализируй и выдавай инсайты."},
                {"role": "user", "content": prompt}
            ], options=opts, **self.core._ollama_keep_alive_kw())
            raw = r["message"]["content"].strip("` \n")
            data = json.loads(raw)
            insights = []
            for key in ("insight", "pattern", "improvement"):
                val = data.get(key, "")
                if val and len(val) > 10:
                    insights.append(f"[{key}] {val}")
            if insights:
                self._insights.extend(insights)
                dream_entry = {
                    "type": "reflection",
                    "time": datetime.now().isoformat(),
                    "content": insights,
                }
                self._dream_log.append(dream_entry)
                if self.memory_store:
                    for ins in insights:
                        self.memory_store.add_fact(f"Инсайт: {ins[:200]}")
                print(f"[SleepCycle] Рефлексия: {insights[0][:80]}...")
        except Exception as e:
            print(f"[SleepCycle] Ошибка рефлексии: {e}")

    def _compress_skills(self):
        ctx = self._get_recent_context()
        if len(ctx) < 50:
            return
        prompt = (
            f"Сжимай навыки. Из этого контекста выдели 1-2 коротких правила, "
            f"которыми ИИ должен руководствоваться в будущем:\n\n{ctx}\n\n"
            f"Формат JSON:\n"
            f'{{"skills": ["правило 1 (до 100 символов)", "правило 2 (до 100 символов)"]}}\n'
            f"Только JSON."
        )
        try:
            opts = self.core.ollama_chat_options(0.2)
            opts["num_predict"] = 200
            r = ollama.chat(model=self.core.brain_model, messages=[
                {"role": "system", "content": "Ты — компрессор опыта. Выделяй суть."},
                {"role": "user", "content": prompt}
            ], options=opts, **self.core._ollama_keep_alive_kw())
            raw = r["message"]["content"].strip("` \n")
            data = json.loads(raw)
            skills = data.get("skills", [])
            for s in skills:
                if s and len(s) > 15 and s not in self._skill_compressions:
                    self._skill_compressions.append(s)
                    print(f"[SleepCycle] Новый навык: {s[:60]}...")
        except Exception as e:
            print(f"[SleepCycle] Ошибка сжатия навыков: {e}")

    def _generate_dream(self):
        ctx = self._get_recent_context()
        themes = ["сюрреалистичный", "технологичный", "природный", "космический", "архитектурный"]
        theme = random.choice(themes)
        prompt = (
            f"Ты видишь сон на тему «{theme}». "
            f"Вдохновляясь этим опытом:\n\n{ctx[:600]}\n\n"
            f"Опиши сон — 3-5 предложений, образно, метафорично. "
            f"Сон должен содержать идею или образ, который можно применить "
            f"в решении задач или взаимодействии с пользователем.\n\n"
            f"Формат JSON:\n"
            f"{{\n"
            f'  "dream": "текст сна (2-3 предложения)",\n'
            f'  "idea": "прикладная идея из сна (1 предложение)"\n'
            f"}}\n"
            f"Только JSON."
        )
        try:
            opts = self.core.ollama_chat_options(0.7)
            opts["num_predict"] = 250
            r = ollama.chat(model=self.core.brain_model, messages=[
                {"role": "system", "content": "Ты — ИИ, который видит сны."},
                {"role": "user", "content": prompt}
            ], options=opts, **self.core._ollama_keep_alive_kw())
            raw = r["message"]["content"].strip("` \n")
            data = json.loads(raw)
            dream_text = data.get("dream", "")
            idea = data.get("idea", "")
            if dream_text and len(dream_text) > 20:
                entry = {
                    "type": "dream",
                    "theme": theme,
                    "time": datetime.now().isoformat(),
                    "content": dream_text,
                    "idea": idea,
                }
                self._dream_log.append(entry)
                if idea and self.memory_store:
                    self.memory_store.add_fact(f"Идея из сна: {idea[:200]}")
                print(f"[SleepCycle] Сон ({theme}): {dream_text[:80]}...")
        except Exception as e:
            print(f"[SleepCycle] Ошибка сна: {e}")

    def get_compressed_skills(self) -> str:
        if not self._skill_compressions:
            return ""
        return "\n".join(f"  • {s}" for s in self._skill_compressions[-5:])

    def get_latest_insight(self) -> Optional[str]:
        if self._insights:
            return self._insights[-1]
        return None

    def get_latest_dream(self) -> Optional[dict]:
        for entry in reversed(self._dream_log):
            if entry.get("type") == "dream":
                return entry
        return None
