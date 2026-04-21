# -*- coding: utf-8 -*-
import json
import hashlib
import random
import time
from difflib import SequenceMatcher
import ollama
import psutil
import win32gui
import win32process

# Graceful imports для опциональных модулей
try:
    from game_knowledge import infer_game_profile, profile_context
    _GAME_KNOWLEDGE_OK = True
except ImportError:
    _GAME_KNOWLEDGE_OK = False
    def infer_game_profile(proc, desc, profile): return profile or "Auto Detect"
    def profile_context(p): return f"Игровой профиль: {p}"

try:
    from file_manager import FileManager
    _FILE_MANAGER_OK = True
except ImportError:
    _FILE_MANAGER_OK = False
    class FileManager: pass

try:
    from immutable_truths import get_coach_truths_text
except ImportError:
    def get_coach_truths_text(): return ""


# Общие советы для снайпера TF2 — используются как fallback без LLM
_TF2_SNIPER_TIPS = [
    "Стреляй в голову — один выстрел решает",
    "Не стой на одном месте — меняй позицию после каждого выстрела",
    "Предугадывай движение — веди прицел перед целью",
    "При промахе сразу уходи — тебя засекли",
    "Следи за Шпионом — проверяй спину каждые 5 секунд",
    "Прицельный выстрел стоит ожидания — не спеши",
    "Держи заряд прицела — стреляй на 100%",
    "Используй укрытие — высовывайся только для выстрела",
]


class AimCoach:
    def __init__(self, core, planner, log_callback=None, history_file="aim_history.json", memory_store=None):
        self.core = core
        self.planner = planner
        self.log_callback = log_callback
        self.history_file = history_file
        self.memory_store = memory_store
        self.is_active = False
        self.game_profile = "Auto Detect"
        self.data = {"sessions": [], "advice_stats": {}}
        if _FILE_MANAGER_OK:
            self.file_manager = FileManager()
        self.last_stats_check = 0.0
        self.cache = {}             # хеш описания → совет
        self._no_game_count = 0    # счётчик "сцена не подходит" подряд
        self._no_game_threshold = 5  # после стольких промахов даём общий совет
        self.load()

    def set_game_profile(self, profile_name):
        self.game_profile = profile_name or "Auto Detect"

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def load(self):
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception:
            pass

    def save(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def start_session(self):
        self.is_active = True
        self._no_game_count = 0
        if self.memory_store:
            self.memory_store.bump_stat("aim_sessions_started")
        self._log("Аим-коуч запущен")

    def stop_session(self):
        self.is_active = False
        self.save()

    def _similarity(self, a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _get_active_window_process_name(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['pid'] == pid:
                    return proc.info['name'].lower()
        except Exception:
            pass
        return ""

    def _is_game_active(self, screen_description=""):
        proc_name = self._get_active_window_process_name()

        # Расширенный список процессов игр (включая TF2)
        game_processes = {
            # Шутеры и аим-трекеры
            'cs2.exe', 'csgo.exe', 'valorant.exe', 'r5apex.exe', 'cod.exe',
            'overwatch.exe', 'overwatch_retail.exe',
            'aimlab.exe', 'aimlabapp.exe',
            'kovaak.exe', "kovaak's fps aim trainer.exe",
            'quaver.exe', 'osu!.exe',
            # Team Fortress 2 / Source Engine
            'hl2.exe',          # TF2 (и другие Source игры)
            'tf_win64.exe',     # TF2 64-bit
            'tf.exe',           # TF2 старый запуск
            # Другие шутеры
            'paladins.exe', 'battlebit.exe', 'splitgate.exe',
            'xdefiant.exe', 'diabotical.exe', 'quake.exe',
        }
        if proc_name in game_processes:
            return True

        # Проверка по ключевым словам в описании экрана
        # Включаем русские слова (модель описывает на русском)
        desc = screen_description.lower()
        keywords = [
            # Английские (на случай частичного описания)
            'crosshair', 'health', 'ammo', 'minimap', 'weapon', 'aim', 'scope',
            'kill', 'respawn', 'sniper', 'headshot',
            # Русские (основные для gemma3 модели)
            'прицел', 'оружие', 'здоровье', 'патрон', 'перезарядка',
            'снайпер', 'прицеливани', 'выстрел', 'стрельб',
            # TF2 специфичные
            'форт', 'крепость', 'команд', 'захват', 'медик', 'шпион',
            'intel', 'fortress', 'ubercharge',
            # Общие игровые
            'убийств', 'очков', 'раунд', 'миникарт', 'заряд',
        ]
        # Порог снижен с 3 до 2 — достаточно двух признаков
        match_count = sum(1 for kw in keywords if kw in desc)
        return match_count >= 2

    def _get_model(self) -> str:
        """Получает имя модели с fallback."""
        model = getattr(self.planner, 'model', None)
        if not model:
            model = getattr(self.planner, 'brain_model', None)
        if not model:
            model = getattr(self.core, 'brain_model', 'gemma3:4b-it-qat')
        return model

    def _coach_chat(self, messages, temperature, **opts):
        options = self.core.ollama_chat_options(temperature, **opts)
        options.setdefault("num_predict", self.core.cfg.get("ollama_num_predict_aim", 200))
        return ollama.chat(model=self._get_model(), messages=messages, options=options, keep_alive=-1)

    def _generic_advice(self) -> str:
        """
        Генерирует общий совет когда игра не определена, но коуч активен.
        Сначала пробует LLM, при ошибке возвращает статичный совет.
        """
        self._log("💡 Режим общих советов (игра не определена)")
        profile_hint = f"Профиль: {self.game_profile}." if self.game_profile != "Auto Detect" else "Игра: TF2 снайпер."
        system = (
            "Ты тренер по аиму. Дай ОДИН практичный совет снайперу (максимум 12 слов). "
            "Без вступлений, только сам совет."
        )
        user = f"{profile_hint} Дай совет по прицеливанию."
        try:
            resp = self._coach_chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                0.4
            )
            advice = resp["message"]["content"].strip()
            # Обрезаем если слишком длинно
            if len(advice) > 120:
                advice = advice[:120].rsplit(' ', 1)[0] + "…"
            return advice
        except Exception:
            return random.choice(_TF2_SNIPER_TIPS)

    def ask_question(self, question):
        question = question.strip()
        if not question:
            return "Вопрос пустой."
        if self.memory_store:
            self.memory_store.bump_stat("aim_questions")
        # Кэш по вопросу
        for sess in self.data.get("sessions", []):
            if sess.get("type") == "qa" and self._similarity(sess.get("screen", ""), question) > 0.75:
                self._log("↻ Ответ из истории")
                return sess.get("advice", "")
        truths = get_coach_truths_text()
        system = f"Ты тренер по аиму. Отвечай кратко, по делу.\n{truths}"
        user = f"Вопрос: {question}"
        try:
            resp = self._coach_chat([{"role": "system", "content": system}, {"role": "user", "content": user}], 0.2)
            ans = resp["message"]["content"].strip()
            self.data.setdefault("sessions", []).append({"screen": question, "advice": ans, "type": "qa"})
            self.data["sessions"] = self.data["sessions"][-100:]
            self.save()
            if self.memory_store:
                self.memory_store.remember_aim_qa(question, ans, self.game_profile)
                self.memory_store.bump_stat("aim_answers")
            return ans
        except Exception as e:
            return f"Ошибка: {e}"

    def observe_and_advise(self):
        self._log("🔍 Анализ сцены...")
        desc = self.core.capture_description()
        if desc.startswith("[Ошибка"):
            return "Ошибка зрения"

        if not self._is_game_active(desc):
            self._no_game_count += 1
            # После нескольких неудач — даём общий совет если коуч активен
            if self.is_active and self._no_game_count >= self._no_game_threshold:
                self._no_game_count = 0
                advice = self._generic_advice()
                if self.memory_store:
                    self.memory_store.remember_aim_note(desc, advice)
                    self.memory_store.bump_stat("aim_auto_advices")
                return advice
            return "Сцена не подходит для совета"

        # Сцена игровая — сбрасываем счётчик
        self._no_game_count = 0

        # Кэш по хешу первых 600 символов описания
        h = hashlib.md5(desc[:600].encode()).hexdigest()
        if h in self.cache:
            self._log("💡 Совет из кэша")
            return self.cache[h]

        resolved = infer_game_profile("", desc, self.game_profile)
        truths = get_coach_truths_text()
        system = (
            f"Ты тренер по аиму. Дай ОДИН короткий совет (до 12 слов). "
            f"Только сам совет, без вступлений.\n{truths}"
        )
        user = f"{profile_context(resolved)}\nЭкран: {desc[:1000]}"
        try:
            resp = self._coach_chat([{"role": "system", "content": system}, {"role": "user", "content": user}], 0.15)
            advice = resp["message"]["content"].strip()
            if "сцена не подходит" in advice.lower():
                return "Сцена не подходит для совета"
            # Обрезаем длинные ответы
            if len(advice) > 150:
                advice = advice[:150].rsplit(' ', 1)[0] + "…"
            self.cache[h] = advice
            # Ограничиваем кэш
            if len(self.cache) > 60:
                oldest = list(self.cache.keys())[0]
                del self.cache[oldest]
            self.data.setdefault("sessions", []).append({"screen": desc[:300], "advice": advice, "type": "auto"})
            self.data["sessions"] = self.data["sessions"][-50:]
            self.save()
            if self.memory_store:
                self.memory_store.remember_aim_note(desc, advice)
                self.memory_store.bump_stat("aim_auto_advices")
            self._log(f"💡 {advice}")
            return advice
        except Exception as e:
            return f"Ошибка: {e}"
