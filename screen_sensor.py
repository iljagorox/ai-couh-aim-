# -*- coding: utf-8 -*-
"""
ScreenSensor V3.4 — исправлены ошибки региона и размера кадров.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import io
import threading
import queue

import numpy as np
from PIL import ImageGrab, Image as PILImage
import cv2
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

try:
    import win32gui
    import win32process
    import psutil
    WIN32 = True
except ImportError:
    WIN32 = False

# Shared state for GUI preview — последний кадр с разметкой (JPEG bytes, ~200px)
LAST_SCREEN: Optional[bytes] = None
LAST_SCREEN_STATE: Optional[str] = None

SELF_HINTS = ("sentinel", "local ai", "saga", "translator")
CONSOLE_HINTS = ("powershell", "command prompt", "cmd.exe", "terminal", "python.exe")
EDITOR_HINTS = ("visual studio code", "pycharm", "notepad", "explorer")
GAME_HINTS = ("aim lab", "aimlabs", "kovaak", "counter-strike", "cs2", "valorant",
              "osu", "team fortress", "tf2", "steam", "benchmark", "practice",
              "overwatch", "ow2", "fragpunk", "marvel rivals", "deadlock",
              "payday 2", "pd2", "3d aim", "aimbeast", "furry aim",
              "aim trainer", "fpsaimtrainer", "aim lab", "aimlab")
BROWSER_HINTS = ("chrome", "msedge", "edge", "firefox", "browser", "yandex", "opera",
                 "brave", "яндекс", "браузер", "yabrowser")

@dataclass
class WindowInfo:
    title: str = ""
    process: str = ""
    rect: Optional[Tuple[int, int, int, int]] = None
    kind: str = "unknown"

@dataclass
class ScreenState:
    timestamp: float
    backend: str
    window: WindowInfo
    frame_w: int
    frame_h: int
    scene: str
    confidence: float
    motion: str
    motion_value: float
    center_activity: float
    edge_density: float
    brightness: float
    likely_crosshair: bool
    likely_result_screen: bool
    objects: List[str]
    enemies: List[Tuple[int, int, int, int]]
    hint: str
    error: str = ""
    ui_buttons: List[Tuple[int, int, int, int]] = field(default_factory=list)
    ui_text_regions: List[Tuple[int, int, int, int]] = field(default_factory=list)
    ui_input_fields: List[Tuple[int, int, int, int]] = field(default_factory=list)
    ui_icons: List[Tuple[int, int, int, int]] = field(default_factory=list)
    ocr_text: str = ""

    def short_text(self) -> str:
        w = self.window
        ui_parts = []
        if self.ui_buttons:
            ui_parts.append(f"BUTTONS: {len(self.ui_buttons)}")
        if self.ui_input_fields:
            ui_parts.append(f"INPUTS: {len(self.ui_input_fields)}")
        if self.ui_text_regions:
            ui_parts.append(f"TEXT_BLOCKS: {len(self.ui_text_regions)}")
        if self.ui_icons:
            ui_parts.append(f"ICONS: {len(self.ui_icons)}")
        ui_line = f"UI: {', '.join(ui_parts)}" if ui_parts else "UI: none detected"
        text_line = f"OCR: {self.ocr_text[:120]}" if self.ocr_text else ""
        return (
            f"SCENE: {self.scene} (conf={self.confidence:.2f})\n"
            f"WINDOW: {w.kind} | {w.title[:80]} | {w.process}\n"
            f"MOTION: {self.motion} ({self.motion_value:.3f}) | BRIGHT: {self.brightness:.2f}\n"
            f"EDGES: {self.edge_density:.3f} | CENTER_ACT: {self.center_activity:.3f}\n"
            f"CROSSHAIR: {self.likely_crosshair} | RESULT: {self.likely_result_screen}\n"
            f"ENEMIES: {len(self.enemies)} detected\n"
            f"{ui_line}\n"
            + (f"{text_line}\n" if text_line else "")
            + f"HINT: {self.hint}"
            + (f"\nERROR: {self.error}" if self.error else "")
        )

class WindowSniffer:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    def get_window_info(self) -> WindowInfo:
        title, process, rect = "", "", None
        if WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd) or ""
                rect = tuple(int(x) for x in win32gui.GetWindowRect(hwnd))
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid).name()
            except Exception:
                pass
        else:
            title = "Mock Window"
            process = "mock.exe"
            rect = (100, 100, 1000, 700)

        hay = f"{title} {process}".lower()
        kind = "unknown"
        if any(x in hay for x in SELF_HINTS): kind = "self_gui"
        elif any(x in hay for x in CONSOLE_HINTS): kind = "console"
        elif any(x in hay for x in EDITOR_HINTS): kind = "desktop"
        elif any(x in hay for x in GAME_HINTS): kind = "game"
        elif any(x in hay for x in BROWSER_HINTS): kind = "browser"

        return WindowInfo(title=title, process=process, rect=rect, kind=kind)

    def get_region_from_window(self, w: WindowInfo) -> Optional[Tuple[int, int, int, int]]:
        if not self.cfg.get("screen_capture_active_window_only", True):
            return None
        if not w.rect:
            return None
        x1, y1, x2, y2 = w.rect
        # Защита от некорректных координат (минимальный размер)
        if x2 - x1 < 120 or y2 - y1 < 120:
            return None
        # Обрезаем до видимой области экрана (если окно вылезло за пределы)
        screen_w = self.cfg.get("screen_width", 1920)
        screen_h = self.cfg.get("screen_height", 1080)
        x1 = max(0, min(x1, screen_w - 10))
        y1 = max(0, min(y1, screen_h - 10))
        x2 = max(x1 + 10, min(x2, screen_w))
        y2 = max(y1 + 10, min(y2, screen_h))
        pad = int(self.cfg.get("screen_capture_window_pad", 0) or 0)
        return (x1+pad, y1+pad, x2-pad, y2-pad)

class CaptureService:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.backend = "imagegrab"
        self.camera = None
        self._init_backend()

    def _init_backend(self):
        preferred = str(self.cfg.get("screen_capture_backend", "dxcam")).lower()
        if preferred == "dxcam":
            try:
                import dxcam
                self.camera = dxcam.create(output_idx=0, output_color="RGB")
                # Получаем реальные размеры экрана для dxcam
                if self.camera:
                    self.cfg["screen_width"] = self.camera.width
                    self.cfg["screen_height"] = self.camera.height
                self.backend = "dxcam"
            except Exception:
                self.backend = "imagegrab"

    def capture_frame(self, region: Optional[Tuple[int,int,int,int]]) -> tuple[Optional[np.ndarray], str]:
        if self.backend == "dxcam" and self.camera:
            # dxcam требует регион в пределах экрана
            if region is not None:
                x1, y1, x2, y2 = region
                if x1 < 0 or y1 < 0 or x2 > self.camera.width or y2 > self.camera.height:
                    # Регион невалидный — падаем на ImageGrab
                    print(f"[Capture] Invalid dxcam region {region}, falling back to ImageGrab")
                    return self._fallback_grab(region)
            frame = self.camera.grab(region=region)
            if frame is not None:
                return frame, ""
            if region is not None:
                full = self.camera.grab(region=None)
                if full is not None:
                    return full, "active window grab returned None; used full screen"
            return None, "dxcam grab returned None"
        return self._fallback_grab(region)

    def _fallback_grab(self, region):
        try:
            img = ImageGrab.grab(bbox=region)
            return np.array(img.convert("RGB")), ""
        except Exception as e:
            if region is not None:
                try:
                    img = ImageGrab.grab()
                    return np.array(img.convert("RGB")), f"active window grab failed; used full screen: {e}"
                except Exception as e2:
                    return None, f"{e}; full screen fallback failed: {e2}"
            return None, str(e)

class VisionEngine:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self._last_gray: Optional[np.ndarray] = None
        self._frame_buffer = deque(maxlen=cfg.get("frame_buffer_size", 30))
        self._enemy_history = deque(maxlen=cfg.get("enemy_track_frames", 10))
        max_side = cfg.get("screen_analysis_max_side", 640)
        self._target_size = (max_side, max_side)
        self._ocr_result: str = ""
        self._ocr_lock = threading.Lock()
        self._ocr_queue: "queue.Queue[Optional[np.ndarray]]" = queue.Queue(maxsize=2)
        self._ocr_thread = threading.Thread(target=self._ocr_worker, daemon=True, name="ocr-worker")
        self._ocr_thread.start()

    def _ocr_worker(self):
        while True:
            try:
                frame = self._ocr_queue.get(timeout=5)
            except queue.Empty:
                with self._ocr_lock:
                    self._ocr_result = ""
                continue
            if frame is None:
                continue
            text = self._ocr_frame_sync(frame)
            with self._ocr_lock:
                self._ocr_result = text

    def queue_ocr(self, frame: np.ndarray):
        try:
            if not self._ocr_queue.full():
                self._ocr_queue.put_nowait(frame.copy())
        except queue.Full:
            pass

    def get_ocr(self) -> str:
        with self._ocr_lock:
            return self._ocr_result

    def preprocess_image(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        target_w, target_h = self._target_size
        max_side = max(target_w, target_h)
        if h < 10 or w < 10:
            return frame
        scale = max_side / max(h, w) if max(h, w) > max_side else 1.0
        if scale != 1.0:
            new_w = max(10, int(w * scale))
            new_h = max(10, int(h * scale))
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            frame = cv2.resize(frame, (new_w, new_h), interpolation=interp)
        return frame

    def detect_enemies(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Проверяем, что текущий кадр совместим с предыдущим
        if len(self._frame_buffer) > 0:
            prev = self._frame_buffer[-1]
            if prev.shape != blurred.shape:
                # Размеры не совпадают — очищаем буфер и начинаем заново
                self._frame_buffer.clear()
                self._frame_buffer.append(blurred)
                return []
        self._frame_buffer.append(blurred)
        if len(self._frame_buffer) < 3:
            return []

        prev = self._frame_buffer[-2]
        if prev.shape != blurred.shape:
            return []

        diff = cv2.absdiff(blurred, prev)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        enemies = []
        h, w = gray.shape
        min_area = int(self.cfg.get("enemy_min_area", 80))
        max_area = int(self.cfg.get("enemy_max_area", 30000))
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:
                continue
            x, y, wc, hc = cv2.boundingRect(cnt)
            if x < 20 or y < 20 or x + wc > w - 20 or y + hc > h - 20:
                continue
            enemies.append((x, y, wc, hc))

        if enemies:
            self._enemy_history.append(enemies)
        else:
            self._enemy_history.append([])
        return enemies

    def get_metrics(self, frame: np.ndarray) -> Tuple[str, float, float, float, float]:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        edge_density = float(np.mean(edges > 0))
        brightness = float(np.mean(gray) / 255.0)
        h, w = gray.shape
        cy1, cy2 = int(h*0.35), int(h*0.65)
        cx1, cx2 = int(w*0.38), int(w*0.62)
        center = gray[cy1:cy2, cx1:cx2]
        center_activity = float(np.std(center) / 128.0) if center.size else 0.0

        motion_val = 0.0
        if self._last_gray is not None and self._last_gray.shape == gray.shape:
            motion_val = float(np.mean(np.abs(gray.astype(np.float32) - self._last_gray.astype(np.float32))) / 255.0)
        self._last_gray = gray.copy()

        if motion_val > 0.09:
            motion_label = "high"
        elif motion_val > 0.025:
            motion_label = "medium"
        else:
            motion_label = "low"
        return motion_label, motion_val, edge_density, brightness, center_activity

    def detect_ui_elements(self, frame: np.ndarray) -> Dict[str, List[Tuple[int, int, int, int]]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        buttons = []
        text_regions = []
        input_fields = []
        icons = []

        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw < 15 or ch < 10 or x < 5 or y < 5 or x + cw > w - 5 or y + ch > h - 5:
                continue
            area = cv2.contourArea(cnt)
            ratio = cw / max(ch, 1)
            hull = cv2.convexHull(cnt)
            solidity = area / max(cv2.contourArea(hull), 1)

            if solidity > 0.85:
                if 2.0 < ratio < 8.0 and 20 < cw < 400 and 15 < ch < 80:
                    buttons.append((x, y, cw, ch))
                elif 0.3 < ratio < 1.8 and 10 < cw < 60 and 10 < ch < 60:
                    icons.append((x, y, cw, ch))

        edge_binary = cv2.Canny(gray, 50, 150)
        edge_dilated = cv2.dilate(edge_binary, np.ones((3, 3), np.uint8), iterations=1)
        text_contours, _ = cv2.findContours(edge_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in text_contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if 20 < cw < 600 and 8 < ch < 100 and cw > ch * 1.5:
                text_regions.append((x, y, cw, ch))

        input_contours, _ = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in input_contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if 60 < cw < 800 and 15 < ch < 60 and 3.0 < cw / max(ch, 1) < 20:
                roi = gray[y:y+ch, x:x+cw]
                if roi.size > 0 and np.std(roi) < 30:
                    input_fields.append((x, y, cw, ch))

        return {
            "buttons": buttons[:20],
            "text_regions": text_regions[:15],
            "input_fields": input_fields[:10],
            "icons": icons[:15],
        }

    def detect_crosshair_by_heuristic(self, frame: np.ndarray) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape
        cy, cx = h//2, w//2
        strip_len = min(40, w//10)
        hor_strip = gray[cy, cx-strip_len:cx+strip_len+1]
        ver_strip = gray[cy-strip_len:cy+strip_len+1, cx]
        bg = np.mean(gray)
        return np.mean(hor_strip) > bg + 30 and np.mean(ver_strip) > bg + 30

    def annotate_frame(self, frame: np.ndarray, state: ScreenState) -> np.ndarray:
        vis = frame.copy()
        colors = {
            "enemies": (0, 0, 255),
            "buttons": (0, 255, 0),
            "text_regions": (255, 255, 0),
            "input_fields": (0, 255, 255),
            "icons": (255, 0, 255),
        }
        for (x, y, cw, ch) in state.enemies:
            cv2.rectangle(vis, (x, y), (x + cw, y + ch), colors["enemies"], 2)
        for (x, y, cw, ch) in state.ui_buttons:
            cv2.rectangle(vis, (x, y), (x + cw, y + ch), colors["buttons"], 2)
            cv2.putText(vis, "btn", (x, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, colors["buttons"], 1)
        for (x, y, cw, ch) in state.ui_text_regions:
            cv2.rectangle(vis, (x, y), (x + cw, y + ch), colors["text_regions"], 1)
            cv2.putText(vis, "txt", (x, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, colors["text_regions"], 1)
        for (x, y, cw, ch) in state.ui_input_fields:
            cv2.rectangle(vis, (x, y), (x + cw, y + ch), colors["input_fields"], 2)
            cv2.putText(vis, "inp", (x, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, colors["input_fields"], 1)
        for (x, y, cw, ch) in state.ui_icons:
            cv2.rectangle(vis, (x, y), (x + cw, y + ch), colors["icons"], 2)
            cv2.putText(vis, "ico", (x, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, colors["icons"], 1)
        ocr = getattr(state, "ocr_text", "")
        if ocr:
            h, w = vis.shape[:2]
            lines = ocr.split(" | ")[:4]
            for i, line in enumerate(lines):
                y_pos = h - 20 - i * 18
                cv2.rectangle(vis, (4, y_pos - 14), (len(line) * 8 + 10, y_pos + 4), (0, 0, 0), -1)
                cv2.putText(vis, line[:60], (8, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        return vis

    def _ocr_frame_sync(self, frame: np.ndarray) -> str:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape
        scale = min(1600 / w, 2.0, 1200 / h)
        if scale != 1.0:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        try:
            data = pytesseract.image_to_data(binary, lang="eng+rus", config="--psm 6 --oem 3", output_type=pytesseract.Output.DICT)
            words, scores = [], []
            for i, text in enumerate(data["text"]):
                text = text.strip()
                conf = int(data["conf"][i])
                if text and conf > 30 and len(text) >= 1:
                    if len(text) >= 3 or text.isdigit():
                        words.append(text)
                        scores.append(conf)
            groups, current = [], []
            for w in words:
                if current and w[0].isupper() != current[-1][0].isupper() and len(current) >= 2:
                    groups.append(" ".join(current))
                    current = [w]
                else:
                    current.append(w)
            if current:
                groups.append(" ".join(current))
            return " | ".join(groups[:12])
        except Exception:
            return ""

    def ocr_frame(self, frame: np.ndarray) -> str:
        self.queue_ocr(frame)
        return self._ocr_frame_sync(frame)

    def detect_result_screen_heuristic(self, frame: np.ndarray) -> bool:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.mean(edges > 0)
        h, w = gray.shape
        center = gray[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
        center_std = np.std(center)
        return edge_density > 0.15 and center_std < 45

class StateClassifier:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    def classify(self, w: WindowInfo, crosshair: bool, result_screen: bool,
                 edge_density: float, objects: List[str]) -> Tuple[str, float]:
        if w.kind in ("self_gui", "console", "desktop", "browser"):
            return w.kind, 0.95
        if result_screen:
            return "result_or_menu", 0.82 if w.kind == "game" else 0.65
        if w.kind == "game" and crosshair:
            return "gameplay", 0.84
        if objects:
            return "gameplay", 0.7
        return "unknown", 0.25

    def generate_hint(self, scene: str, motion: str, crosshair: bool,
                      result_screen: bool, center_activity: float) -> str:
        if scene in ("self_gui", "console", "desktop", "browser"):
            return "не игровое окно; не выдавать игровую аналитику"
        if scene == "gameplay":
            return "игровой процесс; можно давать drill и советы по прицеливанию"
        if scene == "result_or_menu":
            return "экран результатов или меню; анализировать статистику"
        return "недостаточно данных; давать только общие рекомендации"

class ScreenSensor:
    def __init__(self, cfg: Dict[str, Any], log_callback=None):
        self.cfg = cfg
        self.log = log_callback or (lambda _: None)
        self.sniffer = WindowSniffer(cfg)
        self.capture_service = CaptureService(cfg)
        self.vision = VisionEngine(cfg)
        self.classifier = StateClassifier(cfg)
        self.backend = self.capture_service.backend
        self._last_state: Optional[ScreenState] = None
        self._last_debug_save = 0.0

    def analyze(self) -> ScreenState:
        w = self.sniffer.get_window_info()
        region = self.sniffer.get_region_from_window(w)

        frame, cap_err = self.capture_service.capture_frame(region)
        if frame is None:
            return ScreenState(
                timestamp=time.time(), backend=self.backend, window=w,
                frame_w=0, frame_h=0, scene="no_frame", confidence=0.0,
                motion="unknown", motion_value=0.0, center_activity=0.0,
                edge_density=0.0, brightness=0.0,
                likely_crosshair=False, likely_result_screen=False,
                objects=[], enemies=[], hint="Ошибка захвата", error=cap_err
            )

        frame = self.vision.preprocess_image(frame)
        self._save_debug_frame(frame, cap_err)
        motion_label, motion_val, edge_dens, brightness, center_act = self.vision.get_metrics(frame)
        enemies = self.vision.detect_enemies(frame)
        crosshair = self.vision.detect_crosshair_by_heuristic(frame)
        result_screen = self.vision.detect_result_screen_heuristic(frame)
        ui_elements = self.vision.detect_ui_elements(frame)
        objects = []
        if enemies:
            objects.append(f"enemies:{len(enemies)}")
        if ui_elements.get("buttons"):
            objects.append(f"buttons:{len(ui_elements['buttons'])}")
        if ui_elements.get("input_fields"):
            objects.append(f"inputs:{len(ui_elements['input_fields'])}")
        scene, conf = self.classifier.classify(w, crosshair, result_screen, edge_dens, objects)
        ocr_text = self.vision.ocr_frame(frame)
        hint = self.classifier.generate_hint(scene, motion_label, crosshair, result_screen, center_act)

        state = ScreenState(
            timestamp=time.time(),
            backend=self.backend,
            window=w,
            frame_w=frame.shape[1],
            frame_h=frame.shape[0],
            scene=scene,
            confidence=conf,
            motion=motion_label,
            motion_value=motion_val,
            center_activity=center_act,
            edge_density=edge_dens,
            brightness=brightness,
            likely_crosshair=crosshair,
            likely_result_screen=result_screen,
            objects=objects,
            enemies=enemies,
            ui_buttons=ui_elements.get("buttons", []),
            ui_text_regions=ui_elements.get("text_regions", []),
            ui_input_fields=ui_elements.get("input_fields", []),
            ui_icons=ui_elements.get("icons", []),
            ocr_text=ocr_text,
            hint=hint,
            error=""
        )

        self._update_last_screen(frame, state)
        self._last_state = state
        return state

    def describe(self) -> str:
        return self.analyze().short_text()

    def _update_last_screen(self, frame: np.ndarray, state: ScreenState):
        global LAST_SCREEN, LAST_SCREEN_STATE
        try:
            vis = self.vision.annotate_frame(frame, state) if hasattr(self, 'vision') else frame
            h, w = vis.shape[:2]
            scale = min(200 / w, 112 / h, 1.0)
            if scale < 1.0:
                nw, nh = int(w * scale), int(h * scale)
                vis = cv2.resize(vis, (nw, nh), interpolation=cv2.INTER_AREA)
            ret, buf = cv2.imencode('.jpg', cv2.cvtColor(vis, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                LAST_SCREEN = buf.tobytes()
                LAST_SCREEN_STATE = state.short_text()
        except Exception:
            pass

    def _save_debug_frame(self, frame: np.ndarray, reason: str = ""):
        if not self.cfg.get("screen_debug_screenshots", False):
            return
        now = time.time()
        interval = float(self.cfg.get("screen_debug_interval_sec", 2.0) or 2.0)
        if now - self._last_debug_save < interval and not reason:
            return
        self._last_debug_save = now
        try:
            debug_dir = Path(self.cfg.get("screen_debug_dir", "screenshots/sensor"))
            debug_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            path = debug_dir / f"sensor_{stamp}.png"
            cv2.imwrite(str(path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            keep = int(self.cfg.get("screen_debug_keep_last", 120) or 120)
            old = sorted(debug_dir.glob("sensor_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[keep:]
            for p in old:
                try:
                    p.unlink()
                except Exception:
                    pass
        except Exception:
            pass
