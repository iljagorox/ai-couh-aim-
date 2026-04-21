# -*- coding: utf-8 -*-
from collections import deque
import re
import time
import subprocess

import ollama
import pyautogui

from immutable_truths import get_agent_truths_text

VALID_PREFIXES = (
    "MOVE:", "CLICK:", "DBLCLICK:", "RIGHTCLICK:", "TYPE:",
    "HOTKEY:", "SCROLL:", "SEARCH:", "OPEN:", "WAIT:", "DONE",
    "READ_FILE:", "LIST_DIR:", "WRITE_FILE:"
)


class Planner:
    def __init__(self, core, brain_model=None, planner_history_limit=6, planner_max_steps=20,
                 planner_temperature=0.34, allow_web_search=True, memory_store=None,
                 allow_browser_exploration=True, browser_planner_max_steps=40, offline_mode=True,
                 enable_reasoning=True):
        self.core = core
        self.model = brain_model or core.brain_model
        self.screen_w, self.screen_h = pyautogui.size()
        self.history = deque(maxlen=planner_history_limit)
        self.max_steps = planner_max_steps
        self.browser_planner_max_steps = browser_planner_max_steps
        self.temperature = planner_temperature
        self.allow_web_search = allow_web_search
        self.allow_browser_exploration = allow_browser_exploration
        self.offline_mode = offline_mode
        self.memory_store = memory_store
        self.step_count = 0
        self.runtime_profile = "desktop"

        self.macro_plan = []
        self.current_macro_step = 0
        self.failed_actions = set()
        self.consecutive_failures = 0
        self.last_screen_desc = ""
        self.dialog_mode = False

        self.task_phase = "init"
        self.last_commands = deque(maxlen=4)
        self.search_count_in_phase = 0
        self.current_task = ""

        cfg = getattr(core, "cfg", None) or {}
        self.enable_reasoning = cfg.get("enable_reasoning", enable_reasoning)
        self.reasoning_only_when_stuck = cfg.get("reasoning_only_when_stuck", False)
        self.last_reasoning = ""

        self._check_model()

    def _ollama_chat(self, messages, temperature=0.2, **option_overrides):
        opts = self.core.ollama_chat_options(float(temperature), **option_overrides)
        kw = self.core._ollama_keep_alive_kw()
        return ollama.chat(model=self.model, messages=messages, options=opts, **kw)

    def _check_model(self):
        for attempt in range(3):
            try:
                models = ollama.list()
                names = [m.get('name', '') for m in models.get('models', [])]
                base = self.model.split(':')[0].lower()
                if any(base in n.lower() for n in names):
                    print(f"[Planner] Модель {self.model} найдена.")
                    return
                print(f"[Planner] Загрузка {self.model}...")
                subprocess.run(["ollama", "pull", self.model], check=True)
                time.sleep(2)
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"Не удалось загрузить {self.model}")
                time.sleep(3)

    def set_runtime_profile(self, profile_name):
        self.runtime_profile = profile_name.lower()
        self.reset()

    def reset(self):
        self.history.clear()
        self.step_count = 0
        self.macro_plan = []
        self.current_macro_step = 0
        self.failed_actions.clear()
        self.consecutive_failures = 0
        self.last_screen_desc = ""
        self.dialog_mode = False
        self.last_reasoning = ""
        self.task_phase = "init"
        self.last_commands.clear()
        self.search_count_in_phase = 0
        self.current_task = ""
        for attr in ("last_file_read", "last_dir_listing"):
            if hasattr(self.core, attr):
                delattr(self.core, attr)

    def is_question_or_dialog(self, text: str) -> bool:
        text_lower = text.lower().strip()
        action_verbs = (
            'открой', 'запусти', 'напиши', 'создай', 'удали', 'скопируй',
            'перемести', 'нажми', 'кликни', 'введи', 'скачай', 'перейди',
            'закрой', 'сохрани', 'отправь', 'выбери', 'прокрути', 'найди',
            'покажи', 'включи', 'выключи', 'сделай', 'выполни',
        )
        if any(verb in text_lower for verb in action_verbs):
            return False
        if '?' in text_lower:
            return True
        question_starters = (
            'как ', 'почему', 'что ', 'где ', 'когда ', 'кто ', 'зачем',
            'расскажи', 'объясни', 'сколько', 'привет', 'здравствуй'
        )
        for starter in question_starters:
            if text_lower.startswith(starter):
                return True
        if len(text_lower.split()) < 4:
            return True
        return False

    def answer_dialog(self, user_input: str) -> str:
        if self.memory_store:
            self.memory_store.add_dialog_message("user", user_input)
        dialog_history = self.memory_store.get_recent_dialog(10) if self.memory_store else []
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in dialog_history)
        lang = (self.core.cfg.get("preferred_language") or "ru").lower()
        ru_rule = " Всегда отвечай на русском языке." if lang == "ru" else ""
        system = (
            "Ты — дружелюбный ИИ-ассистент SENTINEL. Отвечай полезно и с чувством юмора. "
            "Не выполняй никаких действий на компьютере, только общайся." + ru_rule
        )
        user_prompt = f"История диалога:\n{history_text}\n\nПользователь: {user_input}\nАссистент:"
        try:
            resp = self._ollama_chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
                temperature=0.5,
            )
            answer = resp["message"]["content"].strip()
            if self.memory_store:
                self.memory_store.add_dialog_message("assistant", answer)
            return answer
        except Exception as e:
            return f"Ошибка: {e}"

    def create_macro_plan(self, task: str) -> list:
        ctx = self.core.get_system_context()
        missing = getattr(self.core, 'get_missing_programs', lambda: [])()
        missing_str = f"\nОтсутствующие программы: {', '.join(missing)}" if missing else ""
        prompt = f"""Ты — планировщик. Составь план из 3-6 шагов для задачи: "{task}".
Информация о системе: {ctx}{missing_str}
Верни только нумерованный список на русском языке."""
        try:
            extra = {"num_predict": self.core.cfg.get("ollama_num_predict_plan", 480)}
            resp = self._ollama_chat([{"role": "user", "content": prompt}], temperature=0.1, **extra)
            content = resp['message']['content']
            steps = re.findall(r'^\d+\.\s*(.+)$', content, re.MULTILINE)
            if not steps:
                steps = [line.strip() for line in content.split('\n') if line.strip() and line[0].isdigit()]
                steps = [re.sub(r'^\d+\.\s*', '', s) for s in steps]
            if not steps:
                steps = [task.strip()]
            self.macro_plan = steps
            self.current_macro_step = 0
            print(f"[Planner] Макроплан: {self.macro_plan}")
            return steps
        except Exception as e:
            print(f"[Planner] Ошибка макроплана: {e}")
            self.macro_plan = [task.strip()]
            return self.macro_plan

    def plan(self, task: str, screen_desc: str) -> str:
        self.current_task = task
        if self.is_question_or_dialog(task) or self.dialog_mode:
            self.dialog_mode = True
            return f"DIALOG:{task}"
        self.step_count += 1
        limit = self.browser_planner_max_steps if self.runtime_profile == "browser" else self.max_steps
        if self.step_count > limit:
            return "DONE"
        if not self.macro_plan and self.runtime_profile == "browser":
            self.create_macro_plan(task)
        if screen_desc == self.last_screen_desc:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0
        self.last_screen_desc = screen_desc

        if self.consecutive_failures >= 2:
            return self._handle_stuck()

        system = self._build_fast_prompt(task)
        user = f"Экран: {screen_desc[:1200]}\nИстория: {self._short_history()}\nСледующая команда:"
        try:
            extra = {"num_predict": self.core.cfg.get("ollama_num_predict_command", 40)}
            resp = self._ollama_chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.0, **extra
            )
            raw = resp["message"]["content"]
            cmd = self._normalize_command(raw)
            print(f"[Planner] Команда: {cmd}")
            return cmd
        except Exception as e:
            return f"ERROR:{e}"

    def _build_fast_prompt(self, task: str) -> str:
        truths = get_agent_truths_text()
        return f"""Ты управляешь компьютером. Разрешение {self.screen_w}x{self.screen_h}.
Задача: {task}
Доступные команды: MOVE:X:Y, CLICK:X:Y, TYPE:текст, HOTKEY:win+r, SEARCH:запрос, OPEN:программа, WAIT:N, DONE.
Отвечай только одной командой без пояснений.
{truths}"""

    def _short_history(self) -> str:
        return "\n".join(list(self.history)[-3:]) or "пусто"

    def _normalize_command(self, raw: str) -> str:
        lines = raw.strip().split('\n')
        for line in lines:
            line = line.strip()
            upper = line.upper()
            for prefix in VALID_PREFIXES:
                if upper.startswith(prefix):
                    if prefix in ("MOVE:", "CLICK:", "DBLCLICK:", "RIGHTCLICK:"):
                        nums = re.findall(r"-?\d+", line)
                        if len(nums) >= 2:
                            return f"{prefix}{nums[0]}:{nums[1]}"
                    elif prefix == "WRITE_FILE:":
                        if "::" in line:
                            return line
                    elif prefix in ("READ_FILE:", "LIST_DIR:"):
                        if ":" in line:
                            return line
                    else:
                        return line
        return f"MOVE:{self.screen_w//2}:{self.screen_h//2}"

    def _handle_stuck(self) -> str:
        print("[Planner] 🔄 Застревание! Включаю SmartPilot.")
        if hasattr(self.core, 'executor') and self.core.executor:
            if not self.core.executor.smart_pilot.enabled:
                self.core.executor.smart_pilot.activate()
            return "SMART_EXPLORE"
        if self.consecutive_failures == 3:
            return "HOTKEY:esc"
        return f"CLICK:{self.screen_w//2}:{self.screen_h//2}"

    def remember_result(self, command: str, executed: bool):
        status = "ok" if executed else "fail"
        self.history.append(f"{command} -> {status}")
        if not executed:
            self.failed_actions.add(command)
            if command.startswith("OPEN:"):
                prog = command[5:].strip()
                if hasattr(self.core, 'add_missing_program'):
                    self.core.add_missing_program(prog)
        else:
            self.consecutive_failures = 0
            if command not in ("WAIT:1", "WAIT:2", "DONE") and self.current_macro_step < len(self.macro_plan):
                self.current_macro_step += 1