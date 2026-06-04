# -*- coding: utf-8 -*-
import json
import re
import time
import math
from collections import deque
from datetime import datetime

import ollama

from benchmark_providers import PROVIDERS, find_match, rank_for_score

from game_knowledge import infer_game_profile, profile_context
from aim_analytics import AimAnalytics
from aim_benchmark import AimBenchmark

GAME_PROFILES = {
    "Auto Detect": {"focus": "найти игру/тренажер и видимую aim-проблему", "cooldown": 3.0},
    "CS2": {"focus": "pre-aim, уровень головы, остановка перед выстрелом", "cooldown": 4.0},
    "Valorant": {"focus": "head level, peeking, micro-corrections, recoil reset", "cooldown": 4.0},
    "Osu": {"focus": "путь курсора, ритм, тайминг клика", "cooldown": 3.0},
    "Aim Lab": {"focus": "smoothness, target switching, click timing", "cooldown": 3.0},
    "KovaaK": {"focus": "tracking stability, flick path, re-centering", "cooldown": 3.0},
    "TF2": {"focus": "projectile lead, tracking, movement aim", "cooldown": 4.0},
}

DEFAULT_COOLDOWN = 4.0
BAD_SCENES = {"self_gui", "console", "desktop", "browser", "no_frame"}
GAME_SCENES = {"gameplay", "possible_gameplay", "game_window_unclear", "result_or_menu"}


class AimCoach:
    def __init__(self, core, planner, log_callback=None, history_file="aim_history.json", memory_store=None):
        self.core = core
        self.planner = planner
        self.log_callback = log_callback
        self.history_file = history_file
        self.memory_store = memory_store
        self.is_active = False
        self.game_profile = "Auto Detect"
        self.data = {"sessions": [], "qa": [], "benchmarks": [], "screen_events": []}
        self.recent_advice = deque(maxlen=5)
        self._last_advice_time = 0.0
        self._last_brain_advice_time = 0.0
        self._last_benchmark_scene_time = 0.0
        self._last_state_text = ""

        # Улучшенное зрение: история движений и зон активности
        self._motion_history = deque(maxlen=60)
        self._enemy_tracks = {}  # enemy_id -> [positions]
        self._enemy_id_counter = 0
        self._heat_map = [[0]*12 for _ in range(8)]  # 8x12 grid zones
        self._heat_map_decay = 0.97  # затухание старых зон
        self._screen_center_history = deque(maxlen=30)
        self._last_motion_val = 0.0
        self._stability_score = 1.0
        self._trend_history = deque(maxlen=10)  # для тренда движения
        self._session_intensity = 0.5  # адаптивная интенсивность сессии
        self.analytics = AimAnalytics("aim_analytics.json")
        self.benchmarks = AimBenchmark("aim_benchmarks.json")
        self.load()

    def set_game_profile(self, profile_name):
        self.game_profile = profile_name or "Auto Detect"
        self._last_advice_time = 0.0
        self._last_brain_advice_time = 0.0
        self.recent_advice.clear()
        self._log(f"Aim profile switched: {self.game_profile}")

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def load(self):
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except Exception:
            pass
        for key in ("sessions", "qa", "benchmarks", "screen_events"):
            self.data.setdefault(key, [])

    def save(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def start_session(self):
        self.is_active = True
        self._motion_history.clear()
        self._enemy_tracks.clear()
        self._enemy_id_counter = 0
        self._heat_map = [[0]*12 for _ in range(8)]
        self._screen_center_history.clear()
        self._trend_history.clear()
        self._session_intensity = 0.5
        if self.memory_store:
            self.memory_store.bump_stat("aim_sessions_started")
        self._log(f"Aim coach started ({self.game_profile})")

    def stop_session(self):
        self.is_active = False
        self.save()
        self._log("Aim coach stopped")

    def _get_state(self):
        if self.core and hasattr(self.core, "get_latest_screen_state"):
            return self.core.get_latest_screen_state()
        return None

    def _state_text(self, state) -> str:
        if state is None:
            return "screen sensor недоступен"
        try:
            return state.short_text()
        except Exception:
            return str(state)

    def _detect_profile_from_state(self, state):
        if not state or self.game_profile != "Auto Detect":
            return
        text = f"{getattr(state.window, 'title', '')} {getattr(state.window, 'process', '')} {getattr(state, 'hint', '')} {getattr(state, 'scene', '')}"
        detected = infer_game_profile(text, text, "Auto Detect")
        if detected != "Auto Detect":
            self.game_profile = detected

    def _check_benchmarks(self, state) -> str:
        """Сравнивает OCR-текст с порогами всех бенчмарк-провайдеров."""
        ocr = getattr(state, "ocr_text", "") or ""
        if not ocr:
            return ""
        score = self._find_main_score(ocr)
        if not score:
            return ""
        m = find_match(ocr)
        if not m:
            return ""
        prov, can_name, thresholds = m
        r = rank_for_score(thresholds, prov["ranks"], score)
        line = f"  {prov['name']} | {can_name}: {score} — "
        if r["rank"]:
            line += f"{r['rank']} {r['emoji']}"
            if r["next_rank"]:
                line += f"  (до {r['next_rank']} +{r['needed']})"
        else:
            line += f"ниже ранга  (до {r['next_rank']} нужно {r['needed']})"
        return line

    def _find_main_score(self, text: str) -> int:
        """Ищет самое вероятное число-результат в OCR."""
        nums = re.findall(r"\b(\d{2,5})\b", text)
        ints = [int(n) for n in nums if 10 < int(n) < 99999]
        if not ints:
            return 0
        candidates = [n for n in ints if n > 100]
        return max(candidates) if candidates else max(ints)

    def _extract_metrics_from_text(self, text: str) -> dict:
        metrics = {}
        patterns = {
            "accuracy": r"(?:accuracy|acc|точность)[:\s]*(\d+(?:[\.,]\d+)?)\s*%",
            "score": r"(?:score|сч[её]т|очки)[:\s]*(\d+)",
            "kills": r"(?:kills|targets|hits|frags|убийств[а]?|целей|фрагов)[:\s]*(\d+)",
            "deaths": r"(?:deaths|dealth|смертей|смерти)[:\s]*(\d+)",
            "reaction_ms": r"(?:reaction|реакц\w*|ms)[:\s]*(\d+(?:[\.,]\d+)?)\s*ms",
            "health": r"(?:health|hp|здоровье|хп)[:\s]*(\d+)",
            "ammo": r"(?:ammo|патрон[ыов]?|mags)[:\s]*(\d+)\s*(?:/|из)\s*(\d+)",
            "level": r"(?:level|lvl|уровень)[:\s]*(\d+)",
        }
        for key, pat in patterns.items():
            m = re.search(pat, text, re.I)
            if m:
                raw = m.group(1).replace(",", ".")
                try:
                    metrics[key] = float(raw) if "." in raw else int(raw)
                except ValueError:
                    pass
        return metrics

    def _extract_metrics_from_state(self, state) -> dict:
        metrics = self._extract_metrics_from_text(self._state_text(state))
        ocr = getattr(state, "ocr_text", "")
        if ocr:
            ocr_metrics = self._extract_metrics_from_text(ocr)
            for k, v in ocr_metrics.items():
                if k not in metrics or v > metrics.get(k, 0):
                    metrics[k] = v
        return metrics

    def _analyze_motion_pattern(self, state):
        """Анализ паттерна движения: равномерность, резкие рывки, паузы, тренд"""
        mval = float(getattr(state, "motion_value", 0.0) or 0.0)
        self._motion_history.append(mval)
        self._trend_history.append(mval)

        if len(self._motion_history) < 5:
            return {}, 0.0

        avg = sum(self._motion_history) / len(self._motion_history)
        variance = sum((x - avg)**2 for x in self._motion_history) / len(self._motion_history)
        jerk_count = sum(1 for i in range(1, len(self._motion_history))
                         if abs(self._motion_history[i] - self._motion_history[i-1]) > 0.05)

        # Тренд: растёт или падает активность?
        trend = 0
        if len(self._trend_history) >= 5:
            half = len(self._trend_history) // 2
            trend = (sum(self._trend_history[-half:]) / half) - (sum(self._trend_history[:half]) / half)

        # Адаптивная интенсивность сессии
        if avg > 0.08:
            self._session_intensity = min(1.0, self._session_intensity + 0.05)
        elif avg < 0.02:
            self._session_intensity = max(0.1, self._session_intensity - 0.03)

        pattern = {
            "avg_motion": round(avg, 4),
            "variance": round(variance, 4),
            "jerk_count": jerk_count,
            "smoothness": 1.0 / (1.0 + variance * 50),
            "trend": round(trend, 4),
            "intensity": round(self._session_intensity, 2),
        }
        self._stability_score = pattern["smoothness"]
        return pattern, avg

    def _track_enemies(self, enemies, fw, fh):
        """Сопоставление врагов между кадрами по близости позиций"""
        matched = {}
        new_tracks = {}
        for ex, ey, ew, eh in enemies:
            cx, cy = ex + ew // 2, ey + eh // 2
            best_id, best_dist = None, 999
            for eid, positions in self._enemy_tracks.items():
                if not positions:
                    continue
                lx, ly = positions[-1]
                d = abs(cx - lx) + abs(cy - ly)
                if d < best_dist and d < fw * 0.15:
                    best_dist = d
                    best_id = eid
            if best_id is not None:
                new_tracks[best_id] = self._enemy_tracks[best_id] + [(cx, cy)]
                new_tracks[best_id] = new_tracks[best_id][-8:]
                matched[best_id] = (cx, cy)
            else:
                nid = f"e_{self._enemy_id_counter}"
                self._enemy_id_counter += 1
                new_tracks[nid] = [(cx, cy)]
                matched[nid] = (cx, cy)
        self._enemy_tracks = new_tracks
        return matched

    def _analyze_enemy_pattern(self, state):
        """Отслеживание врагов: куда чаще бегают, где появляются"""
        enemies = getattr(state, "enemies", []) or []
        fw = float(getattr(state, "frame_w", 1920) or 1920)
        fh = float(getattr(state, "frame_h", 1080) or 1080)
        if fw <= 0 or fh <= 0:
            fw, fh = 1920, 1080

        matched = self._track_enemies(enemies, fw, fh)
        enemy_zones = {"left": 0, "center": 0, "right": 0, "top": 0, "bottom": 0, "count": len(enemies), "moving": 0}

        # Затухание хит-мапа
        for gy in range(8):
            for gx in range(12):
                self._heat_map[gy][gx] *= self._heat_map_decay

        for eid, (cx, cy) in matched.items():
            # Зоны по горизонтали
            if cx < fw * 0.33:
                enemy_zones["left"] += 1
            elif cx < fw * 0.66:
                enemy_zones["center"] += 1
            else:
                enemy_zones["right"] += 1
            # Зоны по вертикали
            if cy < fh * 0.33:
                enemy_zones["top"] += 1
            elif cy > fh * 0.66:
                enemy_zones["bottom"] += 1
            # Хит-мап
            gx = min(11, int(cx / fw * 12))
            gy = min(7, int(cy / fh * 8))
            self._heat_map[gy][gx] += 1.0
            # Движется ли враг?
            pos = self._enemy_tracks.get(eid, [])
            if len(pos) >= 3:
                dx = abs(pos[-1][0] - pos[-3][0])
                dy = abs(pos[-1][1] - pos[-3][1])
                if dx > 5 or dy > 5:
                    enemy_zones["moving"] += 1

        # Где чаще всего появляются враги
        hot_zones = []
        for gy in range(8):
            for gx in range(12):
                if self._heat_map[gy][gx] >= 2.5:
                    zone_name = f"{'левый' if gx < 4 else 'правый' if gx > 7 else 'центр'}"
                    zone_name += f" {'верх' if gy < 3 else 'низ' if gy > 5 else 'середина'}"
                    hot_zones.append(zone_name)

        if enemies:
            nearest = min(enemies, key=lambda e: abs(e[0] + e[2]//2 - fw//2))
            enemy_zones["nearest_x"] = nearest[0] + nearest[2] // 2
            enemy_zones["nearest_y"] = nearest[1] + nearest[3] // 2

        enemy_zones["hot_zones"] = list(set(hot_zones))[:4]
        return enemy_zones

    def _analyze_crosshair_placement(self, state):
        """Оценка качества позиции прицела"""
        center_act = float(getattr(state, "center_activity", 0.0) or 0.0)
        has_crosshair = bool(getattr(state, "likely_crosshair", False))
        motion = str(getattr(state, "motion", "low"))
        edge = float(getattr(state, "edge_density", 0.0) or 0.0)
        brightness = float(getattr(state, "brightness", 0.5) or 0.5)

        self._screen_center_history.append(center_act)

        # if crosshair is detected but center has low activity -> holding still, good
        # if high motion and high center activity -> in action, check smoothness
        if has_crosshair and motion == "low" and center_act < 0.12:
            return "hold", center_act
        if has_crosshair and motion == "low" and center_act >= 0.12:
            return "micro_correct", center_act
        if motion == "high" and center_act > 0.2:
            return "flicking", center_act
        if motion == "high" and center_act <= 0.2:
            return "tracking", center_act
        if not has_crosshair and center_act < 0.05:
            return "lost", center_act
        return "unknown", center_act

    def _remember_screen_event(self, state, advice: str):
        if state is None:
            return
        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "game": self.game_profile,
            "scene": getattr(state, "scene", "unknown"),
            "confidence": float(getattr(state, "confidence", 0.0) or 0.0),
            "motion": getattr(state, "motion", "unknown"),
            "motion_value": round(float(getattr(state, "motion_value", 0.0) or 0.0), 4),
            "center_activity": round(float(getattr(state, "center_activity", 0.0) or 0.0), 3),
            "edge_density": round(float(getattr(state, "edge_density", 0.0) or 0.0), 3),
            "crosshair": bool(getattr(state, "likely_crosshair", False)),
            "result_screen": bool(getattr(state, "likely_result_screen", False)),
            "window": getattr(getattr(state, "window", None), "title", "")[:160],
            "enemy_count": len(getattr(state, "enemies", []) or []),
            "stability": round(self._stability_score, 3),
            "ocr_text": getattr(state, "ocr_text", "")[:200],
            "advice": advice[:300],
        }
        self.data.setdefault("screen_events", []).append(row)
        self.data["screen_events"] = self.data["screen_events"][-400:]
        if row["result_screen"] or row["scene"] == "result_or_menu":
            if time.time() - self._last_benchmark_scene_time > 8.0:
                self.data.setdefault("benchmarks", []).append(row)
                self.data["benchmarks"] = self.data["benchmarks"][-200:]
                self._last_benchmark_scene_time = time.time()
                if self.memory_store and hasattr(self.memory_store, "remember_benchmark_event"):
                    self.memory_store.remember_benchmark_event(row)
        self.save()

    def _remember_aim_frame_memory(self, state, advice: str):
        if not self.memory_store or state is None:
            return
        scene = getattr(state, "scene", "unknown")
        enemies = getattr(state, "enemies", []) or []
        should_snapshot = (
            scene in ("gameplay", "result_or_menu") or
            bool(enemies) or
            bool(getattr(state, "likely_result_screen", False))
        )
        payload = {
            "profile": self.game_profile,
            "scene": scene,
            "confidence": round(float(getattr(state, "confidence", 0.0) or 0.0), 3),
            "motion": getattr(state, "motion", "unknown"),
            "motion_value": round(float(getattr(state, "motion_value", 0.0) or 0.0), 4),
            "center_activity": round(float(getattr(state, "center_activity", 0.0) or 0.0), 3),
            "crosshair": bool(getattr(state, "likely_crosshair", False)),
            "result_screen": bool(getattr(state, "likely_result_screen", False)),
            "enemy_count": len(enemies),
            "enemy_boxes": [list(map(int, e)) for e in enemies[:12]],
            "stability": round(self._stability_score, 3),
            "advice": advice[:400],
        }
        try:
            if hasattr(self.memory_store, "remember_aim_frame"):
                self.memory_store.remember_aim_frame(payload)
        except Exception:
            pass
        if should_snapshot:
            try:
                snap = self.core.capture_visual_memory_snapshot(reason="coach", min_interval_sec=24.0) if self.core else {}
                if snap and hasattr(self.memory_store, "remember_visual_snapshot"):
                    snap["summary"] = f"Aim {self.game_profile}: {payload['scene']}, врагов {payload['enemy_count']}; " + snap.get("summary", "")
                    self.memory_store.remember_visual_snapshot(snap)
            except Exception:
                pass

    def _rule_advice(self, state) -> str:
        if state is None:
            return "Не вижу экран: проверь DXcam/OpenCV и активное окно."
        scene = getattr(state, "scene", "unknown")
        win = getattr(state, "window", None)
        title = getattr(win, "title", "") if win else ""
        if scene in BAD_SCENES:
            return f"Не анализирую aim: активно неигровое окно ({title[:40] or scene})."
        if getattr(state, "likely_result_screen", False) or scene == "result_or_menu":
            return "Экран результатов: проанализирую после пары таких снимков."
        conf = float(getattr(state, "confidence", 0.0) or 0.0)
        if conf < 0.45:
            return "Кадр нестабильный: дай игре 5 сек, держи прицел в центре."

        motion = getattr(state, "motion", "unknown")
        motion_val = float(getattr(state, "motion_value", 0.0) or 0.0)
        center = float(getattr(state, "center_activity", 0.0) or 0.0)
        cross = bool(getattr(state, "likely_crosshair", False))
        enemies = getattr(state, "enemies", []) or []
        brightness = float(getattr(state, "brightness", 0.5) or 0.5)
        edge = float(getattr(state, "edge_density", 0.0) or 0.0)

        # Продвинутый анализ
        motion_pattern, avg_motion = self._analyze_motion_pattern(state)
        enemy_info = self._analyze_enemy_pattern(state)
        placement, center_val = self._analyze_crosshair_placement(state)

        # Советы по врагам (самые приоритетные)
        if enemies:
            count = len(enemies)
            nearest_x = enemy_info.get("nearest_x", 0)
            nearest_y = enemy_info.get("nearest_y", 0)
            fw = float(getattr(state, "frame_w", 1920) or 1920)

            if count >= 3:
                return f"Целей {count}: переключение между ними. Довод → клик → следующая. Не залипай на одной."
            if nearest_x < fw * 0.25:
                return f"Враг слева ({nearest_x},{nearest_y}). Вести прицел левее, довод параллельно движению."
            if nearest_x > fw * 0.75:
                return f"Враг справа. Разворот корпуса + плавный довод, не перекручивай."
            if abs(nearest_x - fw/2) < fw * 0.08:
                return f"Враг почти в центре ({nearest_x},{nearest_y}). Микрокоррекция, выдох, клик."
            return f"Враг ({nearest_x},{nearest_y}). Довод от центра, пауза перед кликом."

        # Советы по постановке прицела
        if placement == "hold" and avg_motion < 0.02:
            return "Прицел стоит — хорошая стойка. Не теряй фокус, жди цель."
        if placement == "micro_correct" and motion == "low":
            return "Микрокоррекции: не дёргай, плавный довод на 1-2px."
        if placement == "flicking":
            smooth = motion_pattern.get("smoothness", 0.5)
            if smooth < 0.3:
                return f"Рывок резкий (гладкость {smooth:.2f}). Первое движение медленнее, клик на остановке."
            return "Рывок уверенный. Сократи дистанцию довода, целься сразу в голову."
        if placement == "tracking":
            if center < 0.15:
                return "Отрыв от цели: сократи микро-паузу и доводи плавнее."
            return "Трекинг: работай запястьем, корпус неподвижен."

        # Советы по стабильности
        jerk = motion_pattern.get("jerk_count", 0)
        if jerk >= 4:
            return f"Рывков {jerk} за кадр: слишком резко. Замедли довод на 30%."
        smooth = motion_pattern.get("smoothness", 0.5)
        if smooth < 0.35:
            return "Движение дёрганое: дыши ровно, довод плавнее, клик после паузы."

        # Советы по сцене
        if not cross and scene in GAME_SCENES:
            return "Прицел не вижу: держи центр экрана на уровне появления целей."
        if center < 0.06:
            return "Центр пустой — заранее готовь прицел к следующей зоне появления."
        if center > 0.2 and motion == "low":
            return "Центр активен — молодец, но не перевозбуждайся. Жди цель спокойно."

        # Скорость реакции (косвенная оценка)
        if avg_motion > 0.08 and placement == "tracking":
            return "Высокая скорость трекинга: снизь чувствительность мыши на 5-10%."
        if avg_motion < 0.01 and not enemies:
            return "Слишком статично: шевелись, ищи цели, не давай прицелу застыть."

        # Универсальные советы
        tips = [
            "Сделай микро-паузу перед кликом: точность важнее рывка.",
            "Глаза на цель, мышь ведёт — не смотри на прицел.",
            "Выдохни перед кликом: напряжение убивает точность.",
            "Кликай в конце довода, а не во время.",
            "Довод от локтя, микрокоррекция пальцами.",
        ]
        return tips[hash(str(time.time())) % len(tips)]

    def _brain_advice(self, state, rule_advice: str) -> str:
        if not self.core.cfg.get("aim_use_brain_for_advice", True):
            return rule_advice
        now = time.time()
        interval = float(self.core.cfg.get("aim_brain_advice_min_interval_sec", 20.0) or 20.0)
        if now - self._last_brain_advice_time < interval:
            return rule_advice
        if getattr(state, "scene", "") in BAD_SCENES:
            return rule_advice
        self._last_brain_advice_time = now
        recent = "; ".join(self.recent_advice) or "нет"
        state_text = self._state_text(state)

        # Добавляем аналитику мозга
        motion_analysis = self._analyze_motion_pattern(state)
        enemy_zones = self._analyze_enemy_pattern(state)
        crosshair = self._analyze_crosshair_placement(state)

        system = (
            "Ты локальный aim coach. У тебя нет картинки, только числовые метрики screen sensor. "
            "Проанализируй motion, стабильность, положение врагов. "
            "Дай чёткий совет (до 15 слов) по-русски. Только совет, без пояснений."
        )
        prompt = (
            f"Профиль: {self.game_profile}. {profile_context(self.game_profile)}\n"
            f"Факты экрана:\n{state_text}\n"
            f"Аналитика: motion_avg={motion_analysis.get('avg_motion','?')}, smoothness={motion_analysis.get('smoothness','?'):.2f}\n"
            f"Враги: {enemy_zones.get('count',0)}, зоны: {enemy_zones.get('hot_zones',[])}\n"
            f"Прицел: {crosshair[0]}, center_act={crosshair[1]:.3f}\n"
            f"Правило сказало: {rule_advice}\n"
            f"Последние советы: {recent}\nОтветь только советом."
        )
        try:
            resp = ollama.chat(
                model=self.planner.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                options=self.core.ollama_chat_options(0.25, num_predict=60),
                **self.core._ollama_keep_alive_kw(),
            )
            text = " ".join(resp["message"]["content"].strip().split())
            if 4 <= len(text) <= 140:
                return text
        except Exception as e:
            self._log(f"Brain advice skipped: {e}")
        return rule_advice

    def observe_and_advise(self):
        if not self.is_active:
            return ""
        now = time.time()

        # Адаптивная задержка: меньше в бою, больше в тишине
        cooldown = float(GAME_PROFILES.get(self.game_profile, {}).get("cooldown", DEFAULT_COOLDOWN))
        if self._session_intensity > 0.7:
            cooldown = max(0.8, cooldown * 0.5)  # в бою — чаще
        elif self._session_intensity < 0.2:
            cooldown = min(6.0, cooldown * 1.5)  # в тишине — реже
        if now - self._last_advice_time < cooldown:
            return self.recent_advice[-1] if self.recent_advice else ""

        state = self._get_state()
        self._detect_profile_from_state(state)
        motion_pattern, _ = self._analyze_motion_pattern(state)
        rule = self._rule_advice(state)

        benchmark_line = self._check_benchmarks(state) if state else ""
        if benchmark_line:
            self._log(benchmark_line)

        advice = self._brain_advice(state, rule)
        self.recent_advice.append(advice)
        self._last_advice_time = now

        metrics = self._extract_metrics_from_state(state) if state else {}
        if metrics:
            self.analytics.record_session(metrics, self.game_profile, cooldown)

        self.data.setdefault("sessions", []).append({
            "type": "screen_advice",
            "text": advice,
            "game": self.game_profile,
            "state": self._state_text(state)[:1200],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self.data["sessions"] = self.data["sessions"][-250:]
        self._remember_screen_event(state, advice)
        if self.memory_store:
            self._remember_aim_frame_memory(state, advice)
            self.memory_store.bump_stat("aim_auto_advices")
            if hasattr(self.memory_store, "remember_aim_observation"):
                self.memory_store.remember_aim_observation(self._state_text(state), advice, self.game_profile)
        self._log(f"Tip: {advice}")
        return advice

    def ask_question(self, question: str) -> str:
        if not question.strip():
            return "Empty question."
        if self.memory_store:
            self.memory_store.bump_stat("aim_questions")
        sessions = self.data.get("sessions", [])[-12:]
        benches = self.data.get("benchmarks", [])[-10:]
        screen_events = self.data.get("screen_events", [])[-15:]
        context = json.dumps({
            "last_sessions": sessions,
            "benchmarks": benches,
            "screen_events": screen_events,
        }, ensure_ascii=False)[:5000]
        system = (
            f"Ты aim coach для профиля {self.game_profile}. {profile_context(self.game_profile)}\n"
            "Отвечай на русском. Не выдумывай статистику. "
            "Разбирай только факты из локальной истории и screen sensor. "
            "Формат: причина -> что делать сейчас -> drill на 1 минуту."
        )
        try:
            resp = ollama.chat(
                model=self.planner.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"История:\n{context}\n\nВопрос: {question}"},
                ],
                options=self.core.ollama_chat_options(0.3, num_predict=220),
                **self.core._ollama_keep_alive_kw(),
            )
            ans = resp["message"]["content"].strip()
            self.data.setdefault("qa", []).append({
                "q": question, "a": ans,
                "timestamp": datetime.now().isoformat(timespec="seconds")
            })
            self.data["qa"] = self.data["qa"][-80:]
            self.save()
            if self.memory_store:
                self.memory_store.bump_stat("aim_answers")
                self.memory_store.remember_aim_qa(question, ans, self.game_profile)
            return ans
        except Exception as e:
            return f"Error: {e}"
