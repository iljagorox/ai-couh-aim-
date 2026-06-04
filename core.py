# -*- coding: utf-8 -*-
import json
import os
import time
import subprocess
import threading
import hashlib
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import ollama
import pyautogui
from PIL import Image, ImageStat
import win32gui

from system_info import SystemInfo

try:
    from screen_sensor import ScreenSensor
except Exception:
    ScreenSensor = None


@dataclass
class ScreenContext:
    description: str
    ui_tree: str
    active_window: dict
    screenshot_hash: str
    confidence: float
    capture_error: str = ""

    def as_prompt_text(self) -> str:
        win = self.active_window or {}
        title = win.get("title", "")
        rect = win.get("rect", "")
        err = f"\nCAPTURE_ERROR: {self.capture_error}" if self.capture_error else ""
        return (
            f"SCREEN_CONTEXT confidence={self.confidence:.2f}\n"
            f"ACTIVE_WINDOW: {title} rect={rect}\n"
            f"SCREEN_HASH: {self.screenshot_hash or 'unknown'}{err}\n\n"
            f"VISION:\n{self.description}\n\nUI TREE:\n{self.ui_tree}"
        )


class Core:
    def __init__(self, config_path="config.json", skip_model_check=False):
        self.config_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = json.load(f)

        self._apply_resource_profile()

        self.brain_model = (self.cfg.get("brain_model") or "").strip()
        self.vision_model = ""
        self.auto_execute = self.cfg.get("auto_execute", False)
        self.save_screenshots = self.cfg.get("save_screenshots", False)
        self.screen_w, self.screen_h = pyautogui.size()

        self.last_description = None
        self.last_screenshot_hash = None
        self._last_visual_memory_time = 0.0
        self._last_screen_sensor_call = 0.0
        self.screen_sensor = None
        self.last_task = ""
        self.executor = None
        self.planner = None
        self.memory = None

        self.frame_buffer = deque(maxlen=self.cfg.get("sleep_frame_buffer_size", 60))
        self._sleep_analyzer_thread = None
        self._sleep_stop = threading.Event()

        self.system_info = SystemInfo()
        try:
            print("[Core] SystemInfo загружена.")
        except Exception:
            pass

        self.brain_available = False
        if skip_model_check:
            print("[Core] Repair mode: model check skipped.")
        else:
            self._check_models()
            self.brain_available = True
        self._init_screen_sensor()
        self._start_sleep_analyzer()
        try:
            print("[Core] Game mode: экран видит DXcam/OpenCV, Ollama-vision отключён.")
        except Exception:
            pass

    def _apply_resource_profile(self):
        if not self.cfg.get("low_memory_mode", True):
            return
        overrides = {
            "save_screenshots": False,
            "vision_enabled": False,
            "preload_brain_model": False,
            "preload_vision_model": False,
            "ollama_keep_alive": "0",
            "ollama_num_ctx": 1536,
            "ollama_num_predict": 384,
            "ollama_num_predict_command": 80,
            "agent_step_delay_sec": 0.45,
            "planner_screen_desc_max_chars": 1400,
            "screen_detector_device": "cpu",
            "screen_analysis_max_side": 640,
            "sleep_frame_buffer_size": 40,
        }
        for key, val in overrides.items():
            self.cfg[key] = val
        try:
            print("[Core] low_memory_mode активен: VRAM оставлена игре.")
        except Exception:
            pass

    def _init_screen_sensor(self):
        if not self.cfg.get("screen_sensor_enabled", True):
            try:
                print("[Core] Screen sensor disabled in config.json.")
            except Exception:
                pass
            return
        if ScreenSensor is None:
            try:
                print("[Core] screen_sensor.py недоступен. Установи dxcam/opencv-python.")
            except Exception:
                pass
            return
        try:
            self.screen_sensor = ScreenSensor(self.cfg, log_callback=lambda m: print(f"[ScreenSensor] {m}"))
            backend = getattr(self.screen_sensor, 'backend', 'unknown')
            try:
                print(f"[Core] Screen sensor backend: {backend}")
            except Exception:
                pass
        except Exception as e:
            self.screen_sensor = None
            try:
                print(f"[Core] Screen sensor init error: {e}")
            except Exception:
                pass

    def _start_sleep_analyzer(self):
        if not self.cfg.get("auto_sleep_enabled", True):
            return
        self._sleep_analyzer_thread = threading.Thread(target=self._sleep_loop, daemon=True)
        self._sleep_analyzer_thread.start()

    def _sleep_loop(self):
        interval = self.cfg.get("auto_sleep_interval_sec", 60.0)
        last_run = 0.0
        while not self._sleep_stop.is_set():
            time.sleep(10)
            now = time.time()
            if now - last_run >= interval:
                last_run = now
                self._auto_sleep_analysis()

    def _auto_sleep_analysis(self):
        if not self.frame_buffer or len(self.frame_buffer) < 10:
            return
        try:
            print("[Sleep] Анализ накопленных кадров...")
        except Exception:
            pass
        try:
            all_enemies = []
            for state in list(self.frame_buffer)[-20:]:
                if hasattr(state, 'enemies'):
                    all_enemies.extend(state.enemies)
            if all_enemies:
                avg_w = sum(e[2] for e in all_enemies) / len(all_enemies)
                avg_h = sum(e[3] for e in all_enemies) / len(all_enemies)
                insight = f"Обнаружено {len(all_enemies)} движущихся объектов. Средний размер врага: {avg_w:.0f}x{avg_h:.0f}."
            else:
                insight = "Движущиеся объекты не обнаружены. Возможно, экран статичен или игра неактивна."

            if self.memory:
                self.memory.remember_insight(insight, source="sleep_analyzer", confidence=0.6)
                self.memory.remember_fact(insight, source="auto_sleep")
            try:
                print(f"[Sleep] {insight}")
            except Exception:
                pass
        except Exception as e:
            try:
                print(f"[Sleep] Ошибка анализа: {e}")
            except Exception:
                pass

    def capture_description(self, max_retries=1) -> str:
        if self.screen_sensor is not None:
            fps = max(1.0, float(self.cfg.get("screen_sensor_fps", 5) or 5))
            min_dt = 1.0 / fps
            now = time.time()
            if self.last_description and now - self._last_screen_sensor_call < min_dt:
                return self.last_description
            state = self.screen_sensor.analyze()
            self.frame_buffer.append(state)
            desc = state.short_text()
            self.last_description = desc
            self._last_screen_sensor_call = now
            return desc
        return "[Screen sensor недоступен: проверь dxcam/opencv-python]"

    def build_screen_context(self, max_depth=3) -> ScreenContext:
        desc = self.capture_description()
        state = getattr(self.screen_sensor, "_last_state", None) if self.screen_sensor is not None else None
        confidence = float(getattr(state, "confidence", 0.0) or 0.0) if state else 0.0
        capture_error = getattr(state, "error", "") if state else ""
        return ScreenContext(
            description=desc,
            ui_tree=self.get_ui_tree(max_depth=max_depth),
            active_window=self.get_active_window_info(),
            screenshot_hash=self._quick_screenshot_hash(),
            confidence=confidence,
            capture_error=capture_error,
        )

    def _quick_screenshot_hash(self) -> str:
        try:
            shot = pyautogui.screenshot()
            shot.thumbnail((240, 160), Image.Resampling.BILINEAR)
            return hashlib.md5(shot.convert("RGB").tobytes()).hexdigest()
        except Exception:
            return ""

    def get_latest_screen_state(self):
        if self.screen_sensor is None:
            return None
        try:
            state = self.screen_sensor.analyze()
            self.frame_buffer.append(state)
            return state
        except Exception as e:
            print(f"[Core] screen sensor analyze error: {e}")
            return None

    def capture_screenshot_only(self) -> str:
        os.makedirs("screenshots", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = f"screenshots/aim_{timestamp}.png"
        # Используем стандартный скриншот, т.к. screen_sensor не имеет capture_frame
        screenshot = pyautogui.screenshot()
        max_side = int(self.cfg.get("vision_max_side") or self.cfg.get("screen_analysis_max_side") or 768)
        if max_side > 0:
            shot = screenshot.convert("RGB")
            shot.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
            shot.save(path, format="PNG", optimize=True, compress_level=1)
        else:
            screenshot.save(path)
        return path

    def capture_visual_memory_snapshot(self, reason="manual", grid=(3, 3), min_interval_sec=None) -> dict:
        now = time.time()
        if min_interval_sec is None:
            min_interval_sec = float(self.cfg.get("visual_memory_min_interval_sec", 12.0) or 12.0)
        if now - self._last_visual_memory_time < min_interval_sec:
            return {}
        self._last_visual_memory_time = now
        try:
            base_dir = Path(self.cfg.get("visual_memory_dir", "memory/visual"))
            base_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            shot = pyautogui.screenshot().convert("RGB")
            original_w, original_h = shot.size
            full = shot.copy()
            max_side = int(self.cfg.get("visual_memory_max_side", 960) or 960)
            if max_side > 0:
                full.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
            full_path = base_dir / f"{stamp}_{reason}_full.jpg"
            full.save(full_path, format="JPEG", quality=72, optimize=True)
            cols, rows = grid
            tile_items = []
            names_y = ["верх", "центр", "низ"]
            names_x = ["лево", "центр", "право"]
            tile_source = full
            tw = max(1, tile_source.size[0] // cols)
            th = max(1, tile_source.size[1] // rows)
            for row in range(rows):
                for col in range(cols):
                    x1, y1 = col * tw, row * th
                    x2 = tile_source.size[0] if col == cols - 1 else (col + 1) * tw
                    y2 = tile_source.size[1] if row == rows - 1 else (row + 1) * th
                    tile = tile_source.crop((x1, y1, x2, y2))
                    gray = tile.convert("L")
                    stat = ImageStat.Stat(gray)
                    brightness = float(stat.mean[0]) / 255.0
                    contrast = float(stat.stddev[0]) / 128.0
                    label = f"{names_y[row] if row < 3 else row}-{names_x[col] if col < 3 else col}"
                    tile_path = base_dir / f"{stamp}_{reason}_r{row}c{col}.jpg"
                    tile.save(tile_path, format="JPEG", quality=65, optimize=True)
                    tile_items.append({
                        "id": f"r{row}c{col}",
                        "label": label,
                        "file": str(tile_path),
                        "box_scaled": [x1, y1, x2, y2],
                        "brightness": round(brightness, 3),
                        "contrast": round(contrast, 3),
                    })
            bright = sorted(tile_items, key=lambda t: t["brightness"], reverse=True)[:2]
            active = sorted(tile_items, key=lambda t: t["contrast"], reverse=True)[:3]
            summary = (
                "яркие зоны: " + ", ".join(t["label"] for t in bright) +
                "; детальные зоны: " + ", ".join(t["label"] for t in active)
            )
            snapshot = {
                "reason": reason,
                "full": str(full_path),
                "window": self.get_active_window_info(),
                "screen_hash": hashlib.md5(full.tobytes()).hexdigest(),
                "original_size": [original_w, original_h],
                "scaled_size": list(full.size),
                "tiles": tile_items,
                "summary": summary,
            }
            self._trim_visual_memory(base_dir)
            return snapshot
        except Exception as e:
            print(f"[Core] visual memory snapshot error: {e}")
            return {}

    def _trim_visual_memory(self, base_dir: Path):
        keep = int(self.cfg.get("visual_memory_keep_files", 360) or 360)
        files = sorted(base_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in files[keep:]:
            try:
                path.unlink()
            except Exception:
                pass

    def invalidate_screen_cache(self):
        self.last_screenshot_hash = None
        self.last_description = None

    def get_active_window_info(self) -> dict:
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) or ""
            rect = win32gui.GetWindowRect(hwnd)
            return {"hwnd": hwnd, "title": title, "rect": rect}
        except Exception as e:
            return {"hwnd": None, "title": "", "rect": None, "error": str(e)}

    def get_ui_tree(self, max_depth=2) -> str:
        try:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass
            import uiautomation as auto
            ctrl = auto.GetForegroundControl()
            rect = ctrl.BoundingRectangle
            rtxt = f"[{rect.left},{rect.top},{rect.right},{rect.bottom}]" if rect else "[?]"
            lines = [f"Window: {ctrl.Name} ({ctrl.ControlTypeName})  {rtxt}"]
            def walk(c, depth=0):
                if depth > max_depth or len(lines) > 60:
                    return
                for child in c.GetChildren():
                    name = child.Name.strip()
                    if name and len(name) < 100:
                        cr = child.BoundingRectangle
                        crt = f"[{cr.left},{cr.top},{cr.right},{cr.bottom}]" if cr else "[?]"
                        lines.append(f"{'  '*depth}- {name} ({child.ControlTypeName}) {crt}")
                        walk(child, depth + 1)
            walk(ctrl)
            return "\n".join(lines[:80])
        except Exception as e:
            return f"UI tree error: {e}"

    def get_system_context(self) -> str:
        return self.system_info.get_system_context_for_planner()

    def get_missing_programs(self) -> list:
        if hasattr(self, '_missing_programs'):
            return self._missing_programs
        return []

    def add_missing_program(self, prog: str):
        if not hasattr(self, '_missing_programs'):
            self._missing_programs = []
        if prog not in self._missing_programs:
            self._missing_programs.append(prog)

    def _as_keep_alive(self, value):
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        s = str(value).strip()
        if s.lstrip("-").isdigit():
            return int(s)
        return s

    def brain_keep_alive(self):
        return self._as_keep_alive(self.cfg.get("ollama_keep_alive", "0"))

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
        return {"keep_alive": self.brain_keep_alive()}

    def _model_names(self):
        try:
            res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
            if res.returncode == 0:
                names = []
                for line in (res.stdout or "").splitlines()[1:]:
                    parts = line.split()
                    if parts:
                        names.append(parts[0])
                if names:
                    return names
        except Exception:
            pass
        models = ollama.list()
        names = []
        for m in models.get("models", []):
            if isinstance(m, dict):
                name = m.get("model") or m.get("name")
            else:
                name = getattr(m, "model", None) or getattr(m, "name", None)
            if name:
                names.append(str(name))
        return names

    def _auto_select_model(self):
        try:
            names = self._model_names()
        except Exception:
            return
        if not names:
            print("[Core] Нет моделей в Ollama. Установите хотя бы одну: ollama pull <model>")
            return
        if self.brain_model in names:
            return
        print(f"[Core] Модель {self.brain_model} не найдена. Ищу замену...")
        preferred = ["qwen3", "gemma4", "llama3", "qwen2", "mistral", "phi4", "deepseek"]
        pick = None
        for pref in preferred:
            for n in names:
                if pref in n.lower():
                    pick = n
                    break
            if pick:
                break
        if not pick:
            pick = names[0]
        print(f"[Core] Выбрана модель: {pick}")
        self.brain_model = pick
        self.cfg["brain_model"] = pick

    def _check_models(self):
        if not self.brain_model:
            raise RuntimeError("brain_model пустой в config.json")
        try:
            names = self._model_names()
        except Exception as e:
            raise RuntimeError(f"Не удалось получить список моделей Ollama: {e}")
        if self.brain_model not in names:
            if self.cfg.get("allow_model_auto_pull", False):
                print(f"[Core] Скачиваю brain_model: {self.brain_model}")
                subprocess.run(["ollama", "pull", self.brain_model], check=True)
            else:
                self._auto_select_model()
        self.brain_available = True
        try:
            print(f"[Core] Brain model найдена: {self.brain_model}")
        except Exception:
            pass
