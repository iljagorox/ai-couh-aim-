# -*- coding: utf-8 -*-
import re
import subprocess
import time
import urllib.parse
import webbrowser
import hashlib
from pathlib import Path

import pyautogui
from PIL import ImageGrab, Image
import pygetwindow as gw

from smart_pilot import SmartPilot

_MAX_READ_BYTES = 400_000
_MAX_LIST = 120

NO_GO_ZONE_HEIGHT = 200

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.02


class Executor:
    def __init__(self, core=None, auto=False, search_engine="https://yandex.ru/search/?text={query}", offline_mode=True):
        self.core = core
        self.auto = auto
        self.search_engine = search_engine
        self.offline_mode = offline_mode
        self.screen_w, self.screen_h = pyautogui.size()
        self.last_focused_window = None

        self.wait_count = 0
        self.no_change_steps = 0
        self.last_cmd = ""

        self.smart_pilot = SmartPilot(
            screen_w=self.screen_w,
            screen_h=self.screen_h,
            no_go_top=NO_GO_ZONE_HEIGHT,
            grid_cols=12,          # увеличено для более мелкого шага
            grid_rows=8,           # увеличено для более мелкого шага
            executor=self
        )

    def _take_screenshot_hash(self):
        try:
            img = ImageGrab.grab()
            if NO_GO_ZONE_HEIGHT > 0:
                img = img.crop((0, NO_GO_ZONE_HEIGHT, self.screen_w, self.screen_h))
            img.thumbnail((320, 240), Image.Resampling.LANCZOS)
            return hashlib.md5(img.tobytes()).hexdigest()
        except Exception:
            return None

    def _focus_window_by_title(self, title_contains: str) -> bool:
        try:
            windows = gw.getWindowsWithTitle(title_contains)
            if windows:
                win = windows[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.3)
                self.last_focused_window = win.title
                print(f"[Executor] Фокус на окно: {win.title}")
                return True
        except Exception as e:
            print(f"[Executor] Ошибка фокусировки окна: {e}")
        return False

    def _ensure_browser_focus(self):
        browsers = ["Edge", "Chrome", "Firefox", "Opera", "Yandex", "Brave"]
        for b in browsers:
            if self._focus_window_by_title(b):
                return True
        print("[Executor] ⚠ Браузер не найден")
        return False

    def _is_in_no_go_zone(self, x: int, y: int) -> bool:
        return y < NO_GO_ZONE_HEIGHT

    def execute(self, cmd: str) -> bool:
        if not cmd or cmd.startswith("ERROR"):
            return False
        cu = cmd.strip().upper()
        print(f"[Executor] Выполняю: {cmd}")

        if cu.startswith("SEARCH:") and self.last_cmd == cu:
            print("[Executor] ❌ Повтор SEARCH подряд — блокирую")
            return False
        self.last_cmd = cu

        before_hash = self._take_screenshot_hash()
        result = False
        try:
            if cu.startswith("MOVE:"):
                result = self._move(cmd)
            elif cu.startswith(("CLICK:", "DBLCLICK:", "RIGHTCLICK:")):
                result = self._click(cmd, cu)
            elif cu.startswith("TYPE:"):
                result = self._type(cmd)
            elif cu.startswith("HOTKEY:"):
                result = self._hotkey(cmd)
            elif cu.startswith("SCROLL:"):
                result = self._scroll(cmd)
            elif cu.startswith("SEARCH:"):
                result = self._search(cmd)
            elif cu.startswith("OPEN:"):
                result = self._open(cmd)
            elif cu.startswith("WAIT:"):
                result = self._wait(cmd)
            elif cu == "DONE":
                return True
            elif cu.startswith("READ_FILE:"):
                result = self._read_file(cmd)
            elif cu.startswith("LIST_DIR:"):
                result = self._list_dir(cmd)
            elif cu.startswith("WRITE_FILE:"):
                result = self._write_file(cmd)
            elif cu.startswith("SMART_EXPLORE"):
                result = self._smart_explore()
                return result
            else:
                print(f"[Executor] Неизвестная команда: {cmd}")
                return False

            visual_commands = ("CLICK:", "DBLCLICK:", "RIGHTCLICK:", "TYPE:", "HOTKEY:", "SCROLL:", "OPEN:", "SEARCH:", "MOVE:")
            if cu.startswith(visual_commands):
                time.sleep(0.3)
                after_hash = self._take_screenshot_hash()
                changed = before_hash != after_hash if before_hash and after_hash else True
                if result and changed:
                    print(f"[Executor] ✓ Успешно, экран изменился")
                    self.no_change_steps = 0
                    return True
                elif result and not changed:
                    print(f"[Executor] ⚠ Команда выполнена, но экран НЕ изменился")
                    self.no_change_steps += 1
                    return False
                else:
                    print(f"[Executor] ✗ Не выполнено")
                    self.no_change_steps += 1
                    return False
            else:
                if result:
                    if cu.startswith("WAIT:"):
                        self.wait_count += 1
                        if self.wait_count > 2:
                            print("[Executor] ❌ Слишком много WAIT подряд")
                            return False
                    else:
                        self.wait_count = 0
                    print(f"[Executor] ✓ Выполнено (невизуальная команда)")
                    return True
                else:
                    print(f"[Executor] ✗ Не выполнено")
                    return False
        except Exception as e:
            print(f"[Executor] Ошибка: {e}")
            return False

    def _smart_explore(self) -> bool:
        """
        Запускает полный цикл исследования экрана.
        SmartPilot проходит все шаги до лимита — не останавливается на первом изменении.
        """
        task_hint = getattr(self.core, 'last_task', '') if self.core else ''

        # Если пилот уже активен — не активируем повторно, просто продолжаем
        if not self.smart_pilot.enabled:
            self.smart_pilot.reset()
            self.smart_pilot.activate()

        found_change = False
        steps_done = 0

        print(f"[Executor] 🔍 SmartExplore начат (лимит {self.smart_pilot.max_explore_steps} шагов)")

        while self.smart_pilot.should_continue():
            step_changed = self.smart_pilot.perform_step(task_hint)
            if step_changed:
                found_change = True
            steps_done += 1
            time.sleep(0.15)  # пауза между шагами

        print(f"[Executor] 🔍 SmartExplore завершён: {steps_done} шагов, изменений={'да' if found_change else 'нет'}")

        # сбросить счётчик зависаний
        self.no_change_steps = 0

        # сбросить consecutive_failures в планировщике если есть
        if self.core:
            planner = getattr(self.core, 'planner', None)
            if planner and hasattr(planner, 'consecutive_failures'):
                planner.consecutive_failures = 0

        return found_change

    # ---------- Вспомогательные методы ----------

    def _click(self, cmd: str, cu: str) -> bool:
        nums = re.findall(r"-?\d+", cmd)
        if len(nums) >= 2:
            x, y = int(nums[0]), int(nums[1])
            if not (0 <= x <= self.screen_w and 0 <= y <= self.screen_h) or self._is_in_no_go_zone(x, y):
                x, y = self.screen_w // 2, self.screen_h // 2
            pyautogui.moveTo(x, y, duration=0.05)
            import random
            pyautogui.moveRel(random.randint(-5, 5), random.randint(-5, 5), duration=0.01)
            if cu.startswith("DBLCLICK"):
                pyautogui.doubleClick()
            elif cu.startswith("RIGHTCLICK"):
                pyautogui.rightClick()
            else:
                pyautogui.click()
            return True
        return False

    def _move(self, cmd: str) -> bool:
        nums = re.findall(r"-?\d+", cmd)
        if len(nums) >= 2:
            x, y = int(nums[0]), int(nums[1])
            if self._is_in_no_go_zone(x, y):
                return False
            if 0 <= x <= self.screen_w and 0 <= y <= self.screen_h:
                pyautogui.moveTo(x, y, duration=0.1)
                return True
        return False

    def _type(self, cmd: str) -> bool:
        text = cmd[5:].strip()
        if not text:
            return False
        if not self.offline_mode:
            if not self._ensure_browser_focus():
                return False
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.2)
        else:
            cx, cy = self.screen_w // 2, self.screen_h // 2
            if self._is_in_no_go_zone(cx, cy):
                return False
            pyautogui.click(cx, cy)
            time.sleep(0.2)
        pyautogui.typewrite(text, interval=0.02)
        return True

    def _hotkey(self, cmd: str) -> bool:
        keys = [k.strip().lower() for k in cmd[7:].strip().split('+') if k.strip()]
        if keys:
            pyautogui.hotkey(*keys)
            return True
        return False

    def _scroll(self, cmd: str) -> bool:
        m = re.search(r"-?\d+", cmd)
        if m:
            pyautogui.scroll(int(m.group()))
            return True
        return False

    def _search(self, cmd: str) -> bool:
        if self.offline_mode:
            return False
        query = cmd[7:].strip()
        if not query:
            return False
        if not self._ensure_browser_focus():
            return False
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(0.2)
        pyautogui.typewrite(query, interval=0.02)
        time.sleep(0.2)
        pyautogui.press('enter')
        return True

    def _open(self, cmd: str) -> bool:
        target = cmd[5:].strip().strip('"')
        if not target:
            return False
        if re.match(r"https?://", target, re.I):
            if self.offline_mode:
                return False
            webbrowser.open(target)
            return True
        try:
            subprocess.Popen(target, shell=True)
            return True
        except Exception:
            pass
        if self.core and hasattr(self.core, 'system_info'):
            path = self.core.system_info.find_program(target)
            if path:
                try:
                    subprocess.Popen(f'"{path}"', shell=True)
                    return True
                except Exception:
                    pass
            if any(b in target.lower() for b in ['браузер', 'browser', 'chrome', 'firefox', 'edge']):
                browsers = self.core.system_info.get_available_browsers()
                if browsers:
                    browser_path = self.core.system_info.browsers.get(browsers[0])
                    if browser_path:
                        try:
                            subprocess.Popen(f'"{browser_path}"', shell=True)
                            return True
                        except Exception:
                            pass
        try:
            subprocess.run(f'start "" "{target}"', shell=True, check=True)
            return True
        except Exception:
            pass
        return False

    def _wait(self, cmd: str) -> bool:
        m = re.search(r"\d+\.?\d*", cmd)
        secs = float(m.group()) if m else 0.3
        time.sleep(secs)
        return True

    def _read_file(self, cmd: str) -> bool:
        raw = cmd[9:].strip().strip('"')
        if not raw:
            return False
        path = Path(raw).expanduser()
        if not path.is_file():
            return False
        try:
            data = path.read_text(encoding="utf-8", errors="replace")
            if len(data) > _MAX_READ_BYTES:
                data = data[:_MAX_READ_BYTES] + "\n…[обрезано]"
            if self.core:
                self.core.last_file_read = {"path": str(path), "content": data}
            return True
        except OSError:
            return False

    def _list_dir(self, cmd: str) -> bool:
        raw = cmd[9:].strip().strip('"')
        if not raw:
            return False
        path = Path(raw).expanduser()
        if not path.is_dir():
            return False
        try:
            names = sorted(path.iterdir(), key=lambda p: p.name.lower())
            lines = []
            for p in names[:_MAX_LIST]:
                kind = "DIR " if p.is_dir() else "FILE"
                lines.append(f"{kind}\t{p.name}")
            if self.core:
                self.core.last_dir_listing = {"path": str(path), "listing": "\n".join(lines)}
            return True
        except OSError:
            return False

    def _write_file(self, cmd: str) -> bool:
        rest = cmd[len("WRITE_FILE:"):].strip()
        if "::" not in rest:
            return False
        path_s, content = rest.split("::", 1)
        path = Path(path_s.strip().strip('"')).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="")
            return True
        except OSError:
            return False