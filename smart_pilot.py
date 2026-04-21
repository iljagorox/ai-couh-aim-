# -*- coding: utf-8 -*-
import time
import random
from dataclasses import dataclass
from typing import List, Tuple, Optional
import pyautogui

@dataclass
class Zone:
    row: int
    col: int
    x: int
    y: int
    width: int
    height: int
    last_visit_time: float = 0.0
    visit_count: int = 0
    was_useful: bool = False

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


class SmartPilot:
    def __init__(self, screen_w: int, screen_h: int, no_go_top: int = 200,
                 grid_cols: int = 12, grid_rows: int = 8, executor=None):
        """
        Увеличены grid_cols и grid_rows для более мелкого шага (меньше дистанция рывков).
        """
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.no_go_top = no_go_top
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.executor = executor
        self.zones: List[Zone] = []
        self._build_zones()
        self.enabled = False
        self.steps_in_explore = 0
        self.max_explore_steps = 100  # увеличено в 10 раз (было 10)
        self.last_screen_hash = None
        self._baseline_hash = None

    def _build_zones(self):
        usable_height = self.screen_h - self.no_go_top
        zone_height = usable_height // self.grid_rows
        zone_width = self.screen_w // self.grid_cols
        for r in range(self.grid_rows):
            y = self.no_go_top + r * zone_height
            for c in range(self.grid_cols):
                x = c * zone_width
                self.zones.append(Zone(
                    row=r, col=c, x=x, y=y,
                    width=zone_width, height=zone_height
                ))

    def reset(self):
        for z in self.zones:
            z.last_visit_time = 0.0
            z.visit_count = 0
            z.was_useful = False
        self.enabled = False
        self.steps_in_explore = 0
        self._baseline_hash = None

    def activate(self):
        self.enabled = True
        self.steps_in_explore = 0
        if self.executor:
            self._baseline_hash = self.executor._take_screenshot_hash()
        print("[SmartPilot] 🔍 Активирован режим исследования")

    def deactivate(self):
        self.enabled = False
        self._baseline_hash = None
        print("[SmartPilot] ✅ Режим исследования завершён")

    def should_continue(self) -> bool:
        if not self.enabled:
            return False
        if self.steps_in_explore >= self.max_explore_steps:
            self.deactivate()
            return False
        return True

    def select_best_zone(self) -> Optional[Zone]:
        """Выбирает зону с предпочтением центральных, незнакомых областей."""
        best_zone = None
        best_score = -1
        for zone in self.zones:
            if zone.visit_count >= 2:
                continue
            cx, cy = zone.center
            novelty = 1.0 if zone.visit_count == 0 else 0.3
            center_x_dist = abs(cx - self.screen_w / 2) / (self.screen_w / 2)
            center_y_dist = abs(cy - self.screen_h / 2) / (self.screen_h / 2)
            center_score = 1.0 - (center_x_dist + center_y_dist) / 2
            # Уменьшен штраф за верх, т.к. сетка стала плотнее
            top_penalty = 0.2 if cy < self.screen_h * 0.25 else 0.0
            bottom_penalty = 0.5 if cy > self.screen_h * 0.9 else 0.0
            score = novelty * 1.5 + center_score * 2.0 - top_penalty - bottom_penalty
            if score > best_score:
                best_score = score
                best_zone = zone
        if best_zone is None:
            for zone in self.zones:
                if zone.visit_count < 3:
                    return zone
        return best_zone or self.zones[len(self.zones) // 2]

    def perform_step(self, task_hint: str = "") -> bool:
        """
        Делает один шаг исследования. Возвращает True если экран изменился.
        """
        if not self.enabled:
            return False

        zone = self.select_best_zone()
        if not zone:
            self.deactivate()
            return False

        cx, cy = zone.center
        # Уменьшен разброс (было ±10)
        cx += random.randint(-3, 3)
        cy += random.randint(-3, 3)
        cx = max(10, min(self.screen_w - 10, cx))
        cy = max(self.no_go_top + 5, min(self.screen_h - 10, cy))

        print(f"[SmartPilot] 👉 Зона ({zone.row},{zone.col}) → ({cx},{cy})")

        before = self.executor._take_screenshot_hash() if self.executor else None

        # Увеличены паузы для надёжности реакции интерфейса
        pyautogui.moveTo(cx, cy, duration=0.12)
        time.sleep(0.1)      # было 0.06
        pyautogui.click()
        time.sleep(0.6)      # было 0.35

        zone.last_visit_time = time.time()
        zone.visit_count += 1
        self.steps_in_explore += 1

        changed = False
        if self.executor and before:
            after = self.executor._take_screenshot_hash()
            changed = (before != after)
            if changed:
                zone.was_useful = True
                print(f"[SmartPilot] ✓ Шаг {self.steps_in_explore}: изменение в зоне ({zone.row},{zone.col})")

        if self.steps_in_explore >= self.max_explore_steps:
            print(f"[SmartPilot] Лимит {self.max_explore_steps} шагов достигнут")
            self.deactivate()

        return changed