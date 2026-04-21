# -*- coding: utf-8 -*-
import json
import os
import re
import time
import hashlib
import subprocess
import threading
from datetime import datetime

import ollama
import psutil
import pyautogui
from PIL import Image

from system_info import SystemInfo

DEFAULT_VISION_PROMPT_RU = "Опиши экран кратко на русском: видимые окна, кнопки, текст, примерные координаты."

class Core:
    def __init__(self, config_path="config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = json.load(f)

        self._apply_resource_profile()

        self.vision_model = self.cfg["vision_model"]
        self.brain_model = self.cfg["brain_model"]
        self.auto_execute = self.cfg.get("auto_execute", False)
        self.vision_temperature = self.cfg.get("vision_temperature", 0.1)
        self.save_screenshots = self.cfg.get("save_screenshots", False)
        self.screen_w, self.screen_h = pyautogui.size()

        self.last_screenshot_hash = None
        self.last_description = None

        self.system_info = SystemInfo()
        print("[Core] SystemInfo загружена.")

        self._check_vision_model()
        threading.Thread(target=self._preload_model, daemon=True).start()

    def _apply_resource_profile(self):
        if not self.cfg.get("low_memory_mode"):
            return
        for key, val in (
            ("save_screenshots", False),
            ("vision_max_side", 640),
            ("ollama_num_ctx", 2048),
            ("ollama_num_predict", 512),
            ("ollama_num_predict_vision", 200),
            ("ollama_keep_alive", "-1"),
            ("agent_step_delay_sec", 0.5),
            ("planner_screen_desc_max_chars", 1200),
        ):
            self.cfg.setdefault(key, val)
        print("[Core] low_memory_mode активен.")

    def ollama_chat_options(self, temperature: float, **extra) -> dict:
        opts = {"temperature": float(temperature)}
        nctx = self.cfg.get("ollama_num_ctx")
        if nctx is not None:
            opts["num_ctx"] = int(nctx)
        npred = self.cfg.get("ollama_num_predict")
        if npred is not None:
            opts["num_predict"] = int(npred)
        opts.update(extra)
        return opts

    def _ollama_keep_alive_kw(self):
        return {"keep_alive": -1}

    def _preload_model(self):
        try:
            ollama.chat(model=self.vision_model, messages=[{"role": "user", "content": "ping"}], keep_alive=-1)
            print(f"[Core] Модель {self.vision_model} предзагружена")
        except Exception as e:
            print(f"[Core] Ошибка предзагрузки: {e}")

    def _check_vision_model(self):
        for attempt in range(3):
            try:
                models = ollama.list()
                names = [m.get('name', '') for m in models.get('models', [])]
                base = self.vision_model.split(':')[0].lower()
                if any(base in n.lower() for n in names):
                    print(f"[Core] Модель {self.vision_model} найдена.")
                    return
                print(f"[Core] Загрузка {self.vision_model}...")
                subprocess.run(["ollama", "pull", self.vision_model], check=True)
                time.sleep(2)
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"Не удалось загрузить {self.vision_model}")
                time.sleep(3)

    def capture_description(self, max_retries=2):
        if self.save_screenshots:
            os.makedirs("screenshots", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"screenshots/frame_{timestamp}.png"
        else:
            path = "frame.png"

        screenshot = pyautogui.screenshot()
        max_side = self.cfg.get("vision_max_side", 640)
        if max_side and int(max_side) > 0:
            shot = screenshot.convert("RGB")
            shot.thumbnail((int(max_side), int(max_side)), Image.Resampling.BILINEAR)
            shot.save(path, format="PNG", optimize=True, compress_level=1)
        else:
            screenshot.save(path)

        with open(path, "rb") as f:
            img_hash = hashlib.md5(f.read()).hexdigest()

        if img_hash == self.last_screenshot_hash and self.last_description:
            return self.last_description

        prompt = self.cfg.get("vision_prompt", DEFAULT_VISION_PROMPT_RU)
        opts = self.ollama_chat_options(self.vision_temperature)
        vpred = self.cfg.get("ollama_num_predict_vision")
        if vpred is not None:
            opts["num_predict"] = int(vpred)

        for attempt in range(max_retries):
            try:
                response = ollama.chat(
                    model=self.vision_model,
                    messages=[{"role": "user", "content": prompt, "images": [path]}],
                    options=opts,
                    **self._ollama_keep_alive_kw(),
                )
                desc = response["message"]["content"].strip()
                if desc and not desc.startswith("[Ошибка"):
                    self.last_screenshot_hash = img_hash
                    self.last_description = desc
                    return desc
            except Exception as e:
                if attempt == max_retries - 1:
                    return f"[Ошибка зрения: {e}]"
                time.sleep(0.5)
        return "[Ошибка зрения]"

    def analyze_screenshot(self, image_path: str) -> dict:
        """
        Анализирует существующий скриншот с помощью vision-модели.
        Возвращает словарь с элементами интерфейса.
        """
        if not os.path.exists(image_path):
            return {"error": "file not found", "elements": []}

        prompt = (
            "Ты — анализатор интерфейса. Найди на скриншоте все кликабельные элементы: "
            "кнопки, поля ввода, ссылки, вкладки. Для каждого укажи тип, текст и примерные координаты (x,y,width,height) "
            "в пикселях. Ответь строго в формате JSON: {\"elements\": [{\"type\": \"button\", \"text\": \"OK\", "
            "\"bbox\": [x,y,w,h]}]}. Если ничего нет, верни {\"elements\": []}. Только JSON, без лишнего текста."
        )

        try:
            response = ollama.chat(
                model=self.vision_model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [image_path]
                }],
                options=self.ollama_chat_options(self.vision_temperature),
                **self._ollama_keep_alive_kw()
            )
            content = response["message"]["content"].strip()
            # Извлекаем JSON из ответа (модель может добавить лишний текст)
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"elements": [], "raw": content}
        except Exception as e:
            return {"error": str(e), "elements": []}

    def invalidate_screen_cache(self):
        self.last_screenshot_hash = None
        self.last_description = None

    def get_system_context(self) -> str:
        return self.system_info.get_system_context_for_planner()