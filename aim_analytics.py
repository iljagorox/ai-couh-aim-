# -*- coding: utf-8 -*-
import json, math, time
from collections import deque
from datetime import datetime


class AimAnalytics:
    def __init__(self, history_file="aim_analytics.json"):
        self.history_file = history_file
        self.data = {
            "sessions": [],
            "drills": [],
            "trends": [],
            "weaknesses": {},
            "strengths": {},
            "improvement_rate": [],
            "daily_stats": {},
            "prescription": "",
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

    def record_session(self, metrics: dict, profile: str, duration: float):
        now = datetime.now().isoformat(timespec="seconds")
        entry = {
            "timestamp": now,
            "profile": profile,
            "metrics": metrics,
            "duration": duration,
        }
        self.data.setdefault("sessions", []).append(entry)
        self.data["sessions"] = self.data["sessions"][-200:]

        date_key = now[:10]
        self.data.setdefault("daily_stats", {}).setdefault(date_key, {"count": 0, "metrics": []})
        ds = self.data["daily_stats"][date_key]
        ds["count"] += 1
        ds["metrics"].append(metrics)
        ds["metrics"] = ds["metrics"][-50:]

        self._update_trends(metrics)
        self._update_weaknesses_strengths(metrics)
        self.save()

    def _update_trends(self, metrics: dict):
        acc = metrics.get("accuracy")
        if acc is not None:
            self.data.setdefault("trends", []).append({
                "time": datetime.now().isoformat(),
                "accuracy": acc,
            })
            self.data["trends"] = self.data["trends"][-100:]

    def _update_weaknesses_strengths(self, metrics: dict):
        acc = metrics.get("accuracy", 0)
        if acc < 30:
            self.data["weaknesses"]["accuracy"] = self.data["weaknesses"].get("accuracy", 0) + 1
        elif acc > 70:
            self.data["strengths"]["accuracy"] = self.data["strengths"].get("accuracy", 0) + 1

        kills = metrics.get("kills", 0)
        if kills > 0 and kills < 3:
            self.data["weaknesses"]["kills_per_session"] = self.data["weaknesses"].get("kills_per_session", 0) + 1
        elif kills > 15:
            self.data["strengths"]["kills_per_session"] = self.data["strengths"].get("kills_per_session", 0) + 1

    def get_trend(self, metric: str = "accuracy", window: int = 10) -> float:
        vals = [t.get(metric, 0) for t in self.data.get("trends", [])[-window:] if t.get(metric) is not None]
        if len(vals) < 3:
            return 0.0
        half = len(vals) // 2
        first_half = sum(vals[:half]) / half
        second_half = sum(vals[half:]) / (len(vals) - half)
        return second_half - first_half

    def get_weakness_analysis(self) -> str:
        w = self.data.get("weaknesses", {})
        if not w:
            return "Недостаточно данных для анализа слабых сторон."
        sorted_w = sorted(w.items(), key=lambda x: -x[1])
        lines = []
        for k, v in sorted_w[:3]:
            lines.append(f"  • {k}: отмечено {v} раз")
        return "\n".join(lines)

    def get_improvement_rate(self, profile: str) -> float:
        sessions = [s for s in self.data.get("sessions", []) if s.get("profile") == profile]
        if len(sessions) < 4:
            return 0.0
        accs = [s.get("metrics", {}).get("accuracy", 0) for s in sessions if s.get("metrics", {}).get("accuracy")]
        if len(accs) < 4:
            return 0.0
        half = len(accs) // 2
        early = sum(accs[:half]) / half
        late = sum(accs[half:]) / (len(accs) - half)
        return late - early

    def generate_prescription(self) -> str:
        w = self.data.get("weaknesses", {})
        if not w:
            return "Продолжай в том же духе. Данных для рецепта пока мало."

        worst = max(w, key=w.get)
        suggestions = {
            "accuracy": "Сфокусируйся на плавном наведении: 10 мин smoothness tracking в Aim Lab",
            "kills_per_session": "Работай над target switching: 5 мин grid shot, 5 мин 180 flick",
            "reaction": "Тренируй реакцию: 5 мин micro-flick, 5 мин small targets",
            "tracking": "Добавь 10 мин tracking: вертикаль + горизонталь",
        }
        drill = suggestions.get(worst, f"Удели внимание {worst}: 5 мин целенаправленной тренировки")
        return f"Слабость: {worst}. {drill}"

    def get_summary(self) -> str:
        lines = []
        acc_trend = self.get_trend("accuracy", 15)
        if acc_trend > 3:
            lines.append(f"📈 Точность растёт: +{acc_trend:.1f}% за последние 15 замеров")
        elif acc_trend < -3:
            lines.append(f"📉 Точность падает: {acc_trend:.1f}% — возможно усталость")

        impr = self.get_improvement_rate(self.data.get("sessions", [{}])[-1].get("profile", "")) if self.data.get("sessions") else 0
        if impr > 5:
            lines.append(f"🏆 Прогресс: +{impr:.1f}% от первых сессий к последним")
        elif impr < -5:
            lines.append(f"⚠️ Регресс: {impr:.1f}% — попробуй сменить режим тренировки")

        w = self.get_weakness_analysis()
        if w:
            lines.append("🔍 Зоны роста:\n" + w)

        rx = self.generate_prescription()
        lines.append("💊 Рецепт:\n" + rx)

        return "\n\n".join(lines) if lines else "Собери больше данных для анализа."
