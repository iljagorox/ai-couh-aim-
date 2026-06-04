# -*- coding: utf-8 -*-
import json, time, random
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DrillResult:
    name: str
    score: float
    accuracy: float
    targets_hit: int
    targets_total: int
    duration: float
    timestamp: str = ""


DRILLS = {
    "smoothness": {
        "name": "Плавное ведение",
        "desc": "Веди прицел по горизонтали 30 сек, минимизируя дрожь",
        "duration": 30,
        "target": "tracking",
    },
    "flick_180": {
        "name": "Резкий разворот на 180",
        "desc": "Развернись на 180° и наведись на цель. 10 повторений",
        "duration": 45,
        "target": "flick",
    },
    "micro_flick": {
        "name": "Микро-флик",
        "desc": "5 быстрых переключений между мелкими целями за 10 сек",
        "duration": 20,
        "target": "flick",
    },
    "target_switch": {
        "name": "Переключение целей",
        "desc": "Переключайся между 4 целями по часовой стрелке. 30 сек",
        "duration": 30,
        "target": "switching",
    },
    "click_timing": {
        "name": "Тайминг клика",
        "desc": "Кликай по появляющимся целям в ритме — 20 появлений",
        "duration": 25,
        "target": "timing",
    },
    "vertical_track": {
        "name": "Вертикальное сопровождение",
        "desc": "Сопровождай вертикально движущуюся цель 30 сек",
        "duration": 30,
        "target": "tracking",
    },
    "distance_shot": {
        "name": "Дальний выстрел",
        "desc": "Попади по мелкой цели на расстоянии. 5 попыток",
        "duration": 20,
        "target": "precision",
    },
}


class AimBenchmark:
    def __init__(self, history_file="aim_benchmarks.json"):
        self.history_file = history_file
        self.data = {
            "drills": [],
            "benchmarks": [],
            "milestones": [],
            "current_streak": 0,
            "best_streak": 0,
        }
        self._load()

    def _load(self):
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except Exception:
            pass

    def save(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def available_drills(self) -> list:
        return [{"id": k, **v} for k, v in DRILLS.items()]

    def record_drill(self, drill_id: str, hits: int, total: int, duration: float):
        if drill_id not in DRILLS:
            return None
        drill_info = DRILLS[drill_id]
        accuracy = (hits / total * 100) if total > 0 else 0
        score = accuracy * (hits / max(duration, 1))
        result = DrillResult(
            name=drill_info["name"],
            score=round(score, 1),
            accuracy=round(accuracy, 1),
            targets_hit=hits,
            targets_total=total,
            duration=duration,
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )
        self.data.setdefault("drills", []).append({
            "drill_id": drill_id,
            "name": result.name,
            "score": result.score,
            "accuracy": result.accuracy,
            "hits": hits,
            "total": total,
            "duration": duration,
            "timestamp": result.timestamp,
        })
        self.data["drills"] = self.data["drills"][-200:]
        self._check_milestones(result)
        self._update_streak(result)
        self.save()
        return result

    def _check_milestones(self, result: DrillResult):
        if result.accuracy >= 95:
            self.data.setdefault("milestones", []).append({
                "type": "accuracy",
                "value": result.accuracy,
                "drill": result.name,
                "timestamp": result.timestamp,
            })
        if result.score > 50:
            self.data.setdefault("milestones", []).append({
                "type": "score",
                "value": result.score,
                "drill": result.name,
                "timestamp": result.timestamp,
            })
        self.data["milestones"] = self.data["milestones"][-50:]

    def _update_streak(self, result: DrillResult):
        if result.accuracy >= 80:
            self.data["current_streak"] = self.data.get("current_streak", 0) + 1
        else:
            self.data["current_streak"] = 0
        if self.data["current_streak"] > self.data.get("best_streak", 0):
            self.data["best_streak"] = self.data["current_streak"]

    def get_drill_stats(self, drill_id: str) -> dict:
        drills = [d for d in self.data.get("drills", []) if d.get("drill_id") == drill_id]
        if not drills:
            return {"count": 0, "avg_accuracy": 0, "best_accuracy": 0}
        accs = [d.get("accuracy", 0) for d in drills]
        return {
            "count": len(drills),
            "avg_accuracy": round(sum(accs) / len(accs), 1),
            "best_accuracy": max(accs),
            "trend": round(accs[-1] - accs[0], 1) if len(accs) > 3 else 0,
        }

    def get_benchmark_report(self) -> str:
        lines = []
        streak = self.data.get("current_streak", 0)
        best = self.data.get("best_streak", 0)
        lines.append(f"🔥 Текущая серия: {streak} | Лучшая: {best}")

        if self.data.get("milestones"):
            lines.append(f"🏅 Достижений: {len(self.data['milestones'])}")

        by_drill = {}
        for d in self.data.get("drills", []):
            did = d.get("drill_id", "unknown")
            by_drill.setdefault(did, []).append(d.get("accuracy", 0))
        if by_drill:
            best_drill = max(by_drill, key=lambda k: sum(by_drill[k]) / len(by_drill[k]))
            avg = sum(by_drill[best_drill]) / len(by_drill[best_drill])
            drill_name = DRILLS.get(best_drill, {}).get("name", best_drill)
            lines.append(f"💪 Лучшее упражнение: {drill_name} ({avg:.0f}%)")

        return "\n".join(lines)

    def get_weakest_drill(self) -> Optional[str]:
        by_drill = {}
        for d in self.data.get("drills", []):
            did = d.get("drill_id", "unknown")
            by_drill.setdefault(did, []).append(d.get("accuracy", 0))
        if not by_drill:
            return None
        worst = min(by_drill, key=lambda k: sum(by_drill[k]) / len(by_drill[k]))
        return DRILLS.get(worst, {}).get("name", worst)
