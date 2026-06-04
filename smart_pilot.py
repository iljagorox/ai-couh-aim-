# -*- coding: utf-8 -*-
"""Safe screen exploration helper.

SmartPilot is intentionally conservative: by default it only moves the mouse
and never clicks. It keeps per-session memory of visited zones so it does not
bounce between the same places forever. Hover reactions are treated as weak
signals, not as task progress.
"""
import time
import random
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab


@dataclass
class Zone:
    row: int
    col: int
    x: int
    y: int
    width: int
    height: int
    score: float = 0.0
    last_visit_time: float = 0.0
    visit_count: int = 0
    hover_count: int = 0
    real_change_count: int = 0
    blocked_until: float = 0.0

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def key(self) -> Tuple[int, int]:
        return (self.row, self.col)


class ScreenAnalyzer:
    """Finds visually dense regions using a cheap luminance-gradient score."""

    @staticmethod
    def find_hotspots(screen_w: int, screen_h: int, no_go_top: int = 200, top_n: int = 15):
        try:
            img = ImageGrab.grab().convert("L").resize((max(1, screen_w // 4), max(1, screen_h // 4)))
            arr = np.array(img, dtype=np.float32)
            # Контраст: растянуть гистограмму для тусклых кадров
            lo, hi = np.percentile(arr, 5), np.percentile(arr, 95)
            if hi - lo > 8:
                arr = np.clip((arr - lo) / (hi - lo + 1e-6) * 255, 0, 255)
            gx = np.abs(np.diff(arr, axis=1, append=arr[:, -1:]))
            gy = np.abs(np.diff(arr, axis=0, append=arr[-1:, :]))
            # Лапласиан для текстурных зон (кнопки, текст, иконки)
            lap = cv2.Laplacian(arr.astype(np.uint8), cv2.CV_32F)
            grad = gx + gy + np.abs(lap) * 0.3
            rows, cols = 8, 12
            rh, cw = max(1, grad.shape[0] // rows), max(1, grad.shape[1] // cols)
            regions = []
            for r in range(rows):
                for c in range(cols):
                    block = grad[r * rh:(r + 1) * rh, c * cw:(c + 1) * cw]
                    sal = float(np.mean(block)) + float(np.std(block)) * 0.5
                    sx = int((c + 0.5) * screen_w / cols)
                    sy = int((r + 0.5) * screen_h / rows)
                    if sy >= no_go_top:
                        regions.append((sx, sy, sal))
            regions.sort(key=lambda t: t[2], reverse=True)
            return regions[:top_n]
        except Exception:
            return []


class SmartPilot:
    def __init__(self, screen_w: int, screen_h: int, no_go_top: int = 200,
                 grid_cols: int = 12, grid_rows: int = 8, executor=None):
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
        self.max_explore_steps = 18
        self._baseline_hash = None
        self._hotspots: List[Tuple[int, int, float]] = []
        self._last_scan = 0.0
        self._recent_zones: Deque[Tuple[int, int]] = deque(maxlen=8)
        self._no_progress_steps = 0
        self._last_result = "idle"
        self._dead_zones = set()
        self._zone_lessons = []
        self._adaptive_scan_interval = 2.0
        self._last_movement_result = False

    def _cfg(self, key: str, default):
        try:
            cfg = getattr(getattr(self.executor, "core", None), "cfg", {}) or {}
            return cfg.get(key, default)
        except Exception:
            return default

    def _build_zones(self):
        zh = max(1, (self.screen_h - self.no_go_top) // self.grid_rows)
        zw = max(1, self.screen_w // self.grid_cols)
        for r in range(self.grid_rows):
            y = self.no_go_top + r * zh
            for c in range(self.grid_cols):
                self.zones.append(Zone(row=r, col=c, x=c * zw, y=y, width=zw, height=zh))

    def reset(self):
        for z in self.zones:
            z.last_visit_time = 0.0
            z.visit_count = 0
            z.hover_count = 0
            z.real_change_count = 0
            z.blocked_until = 0.0
            z.score = 0.0
        self.enabled = False
        self.steps_in_explore = 0
        self.max_explore_steps = int(self._cfg("smart_pilot_max_steps", 18))
        self._baseline_hash = None
        self._hotspots = []
        self._recent_zones.clear()
        self._no_progress_steps = 0
        self._last_result = "reset"
        self._dead_zones.clear()
        self._zone_lessons.clear()
        self._adaptive_scan_interval = 2.0
        self._last_movement_result = False

    def activate(self):
        self.enabled = True
        self.steps_in_explore = 0
        self.max_explore_steps = int(self._cfg("smart_pilot_max_steps", 18))
        self._no_progress_steps = 0
        self._recent_zones.clear()
        self._scan_screen(force=True)
        if self.executor:
            self._baseline_hash = self.executor._take_screenshot_hash()
        print(f"[SmartPilot] activated; hotspots={len(self._hotspots)}, max_steps={self.max_explore_steps}")

    def deactivate(self, reason: str = "done"):
        if self.enabled:
            print(f"[SmartPilot] stopped: {reason}")
        self.enabled = False
        self._baseline_hash = None
        self._last_result = reason

    def should_continue(self) -> bool:
        if not self.enabled:
            return False
        if self.steps_in_explore >= self.max_explore_steps:
            self.deactivate("step_limit")
            return False
        stop_after = int(self._cfg("smart_pilot_stop_after_no_progress", 8))
        if self._no_progress_steps >= stop_after:
            self.deactivate("no_progress")
            return False
        return True

    def _scan_screen(self, force: bool = False):
        now = time.time()
        interval = self._adaptive_scan_interval if not force else 0
        if force or now - self._last_scan > interval or not self._hotspots:
            self._hotspots = ScreenAnalyzer.find_hotspots(self.screen_w, self.screen_h, self.no_go_top)
            self._last_scan = now
            # Адаптивный интервал: если есть горячие точки — сканируем чаще
            if self._hotspots and self._hotspots[0][2] > 1.0:
                self._adaptive_scan_interval = max(0.5, self._adaptive_scan_interval * 0.8)
            else:
                self._adaptive_scan_interval = min(5.0, self._adaptive_scan_interval * 1.2)

    def _zone_salience(self, z: Zone) -> float:
        cx, cy = z.center
        return sum(ss * max(0.0, 1.0 - (((cx - sx) ** 2 + (cy - sy) ** 2) ** 0.5 / 100.0))
                   for sx, sy, ss in self._hotspots[:15])

    def _allowed_zone(self, z: Zone) -> bool:
        """Avoid taskbar/bottom strip and screen edges; those made the cursor skate along the bottom."""
        cx, cy = z.center
        bottom = int(self._cfg("smart_pilot_no_go_bottom", 180) or 180)
        left = int(self._cfg("smart_pilot_no_go_left", 120) or 120)
        right = int(self._cfg("smart_pilot_no_go_right", 120) or 120)
        if cy >= self.screen_h - bottom:
            return False
        if cx <= left or cx >= self.screen_w - right:
            return False
        if bool(self._cfg("smart_pilot_avoid_bottom_rows", True)) and z.row >= self.grid_rows - 2:
            return False
        return True

    def select_best_zone(self) -> Optional[Zone]:
        self._scan_screen()
        now = time.time()
        max_visits = int(self._cfg("smart_pilot_max_zone_visits", 2))
        recent_set = set(self._recent_zones)
        candidates = []

        for z in self.zones:
            if not self._allowed_zone(z):
                continue
            if z.key in self._dead_zones:
                continue
            if z.blocked_until > now:
                continue
            if z.visit_count >= max_visits:
                continue

            sal = self._zone_salience(z)
            novelty = 3.0 / (1.0 + z.visit_count)
            center = 1.0 - (abs(z.center[0] - self.screen_w / 2) / (self.screen_w / 2) +
                            abs(z.center[1] - self.screen_h / 2) / (self.screen_h / 2)) / 2.0
            repeat_penalty = 12.0 if z.key in recent_set else 0.0
            # Strongly punish edges and low rows. They are usually taskbar, dock, scrollbars or dead space.
            low_row_penalty = max(0, z.row - (self.grid_rows // 2)) * 3.0
            edge_col_penalty = 4.0 if z.col in (0, self.grid_cols - 1) else 0.0
            edge_penalty = low_row_penalty + edge_col_penalty
            hover_penalty = z.hover_count * 3.0
            no_result_penalty = max(0, z.visit_count - z.real_change_count) * 8.0
            recent_time_penalty = 3.0 if (now - z.last_visit_time) < float(self._cfg("smart_pilot_zone_cooldown_sec", 8.0)) else 0.0

            z.score = sal * 1.8 + novelty + center * 0.7 - repeat_penalty - edge_penalty - hover_penalty - no_result_penalty - recent_time_penalty
            candidates.append(z)

        if not candidates:
            return None

        candidates.sort(key=lambda zone: zone.score, reverse=True)
        top_n = max(1, min(4, len(candidates)))
        # Mostly pick the best non-recent zone, sometimes explore a nearby alternative.
        return candidates[0] if random.random() < 0.82 else random.choice(candidates[:top_n])

    def _mark_visit(self, zone: Zone, hover_changed: bool, real_change: bool):
        now = time.time()
        zone.last_visit_time = now
        zone.visit_count += 1
        if hover_changed:
            zone.hover_count += 1
        if real_change:
            zone.real_change_count += 1
        self._recent_zones.append(zone.key)

        # Do not keep returning to a region just because hover animation flickers there.
        cooldown = float(self._cfg("smart_pilot_zone_cooldown_sec", 8.0))
        if hover_changed and not real_change:
            zone.blocked_until = now + cooldown
        if zone.visit_count >= int(self._cfg("smart_pilot_max_zone_visits", 2)):
            zone.blocked_until = now + cooldown * 2
        if zone.visit_count >= 1 and not real_change and not hover_changed:
            self._dead_zones.add(zone.key)
            self._zone_lessons.append(f"zone {zone.key}: пусто, не возвращаться без новой причины")
        elif zone.visit_count >= 2 and not real_change:
            self._dead_zones.add(zone.key)
            self._zone_lessons.append(f"zone {zone.key}: hover/повтор без результата")

    def perform_step(self, task_hint: str = "") -> bool:
        if not self.enabled:
            return False

        zone = self.select_best_zone()
        if not zone:
            self.deactivate("no_zones_left")
            return False

        cx, cy = zone.center
        cx += random.randint(-3, 3)
        cy += random.randint(-3, 3)
        cx = max(int(self._cfg("smart_pilot_no_go_left", 140)), min(self.screen_w - int(self._cfg("smart_pilot_no_go_right", 140)), cx))
        cy = max(self.no_go_top + 5, min(self.screen_h - int(self._cfg("smart_pilot_no_go_bottom", 180)), cy))

        print(f"[SmartPilot] step={self.steps_in_explore + 1} zone=({zone.row},{zone.col}) score={zone.score:.1f} move=({cx},{cy})")
        before = self.executor._take_screenshot_hash() if self.executor else None
        pyautogui.moveTo(cx, cy, duration=0.03)
        time.sleep(float(self._cfg("smart_pilot_hover_delay_sec", 0.16)))

        hover_changed = False
        if self.executor and before:
            hover_hash = self.executor._take_screenshot_hash()
            hover_changed = bool(hover_hash and hover_hash != before)

        click_enabled = bool(self._cfg("smart_pilot_click_enabled", False))
        real_change = False
        if click_enabled:
            pyautogui.click()
            time.sleep(0.25)
            if self.executor and before:
                after = self.executor._take_screenshot_hash()
                real_change = bool(after and after != before)
        else:
            print("[SmartPilot] click disabled; move only")

        self.steps_in_explore += 1
        self._mark_visit(zone, hover_changed=hover_changed, real_change=real_change)

        if real_change:
            self._no_progress_steps = 0
            self._hotspots = []
            print(f"[SmartPilot] real screen change at step {self.steps_in_explore}")
            return True

        # Hover animation is not task progress. It only means the zone is interactive/alive.
        self._no_progress_steps += 1
        if hover_changed:
            print(f"[SmartPilot] hover reacted, but not counted as progress ({self._no_progress_steps})")
        else:
            print(f"[SmartPilot] no progress ({self._no_progress_steps})")
        return False

    def lessons(self) -> List[str]:
        return self._zone_lessons[-12:]
