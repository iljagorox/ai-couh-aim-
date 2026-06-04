# -*- coding: utf-8 -*-
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from collections import Counter


class MemoryStore:
    def __init__(self, path="sentinel_memory.json", limit=200):
        self.path = path
        self.limit = int(limit or 200)
        base = Path(path)
        self.archive_path = str(base.with_suffix(".archive.jsonl"))
        self.data = {
            "facts": [],
            "task_history": [],
            "command_history": [],
            "aim_notes": [],
            "aim_frames": [],
            "aim_qa": [],
            "insights": [],
            "dialog_history": [],
            "benchmark_events": [],
            "visual_snapshots": [],
            "sleep_reports": [],
            "compression_history": [],
            "knowledge_summary": {
                "created": datetime.now().isoformat(timespec="seconds"),
                "last_updated": "",
                "total_archived_items": 0,
                "task_patterns": {},
                "aim_patterns": {},
                "stable_insights": [],
            },
            "stats": {
                "aim_questions": 0,
                "aim_answers": 0,
                "aim_auto_advices": 0,
                "aim_sessions_started": 0,
                "aim_manual_notes": 0,
            },
            "aim_aggregates": {},
        }
        self._lock = threading.Lock()
        self._dirty = False
        self._save_thread = None
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            with self._lock:
                for key, val in loaded.items():
                    self.data[key] = val
                self._ensure_defaults()
        except (FileNotFoundError, json.JSONDecodeError):
            self._ensure_defaults()

    def _ensure_defaults(self):
        for key in ("facts", "task_history", "command_history", "aim_notes", "aim_frames", "aim_qa", "insights", "dialog_history", "benchmark_events", "visual_snapshots", "sleep_reports", "compression_history"):
            self.data.setdefault(key, [])
        self.data.setdefault("aim_aggregates", {})
        self.data.setdefault("stats", {})
        self.data.setdefault("knowledge_summary", {})
        ks = self.data["knowledge_summary"]
        ks.setdefault("created", datetime.now().isoformat(timespec="seconds"))
        ks.setdefault("last_updated", "")
        ks.setdefault("total_archived_items", 0)
        ks.setdefault("task_patterns", {})
        ks.setdefault("aim_patterns", {})
        ks.setdefault("stable_insights", [])
        ks.setdefault("visual_snapshot_count", 0)

    def _save_async(self):
        time.sleep(0.4)
        with self._lock:
            if not self._dirty:
                return
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
                self._dirty = False
            except Exception as e:
                print(f"[Memory] Ошибка сохранения: {e}")
            self._save_thread = None

    def save(self):
        with self._lock:
            self._dirty = True
            if self._save_thread is None or not self._save_thread.is_alive():
                self._save_thread = threading.Thread(target=self._save_async, daemon=True)
                self._save_thread.start()

    def save_now(self):
        with self._lock:
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2)
                self._dirty = False
            except Exception as e:
                print(f"[Memory] Ошибка сохранения: {e}")

    def _archive_items(self, key: str, items: list, reason: str):
        if not items:
            return 0
        path = Path(self.archive_path)
        if path.parent and str(path.parent) not in ("", "."):
            path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now().isoformat(timespec="seconds")
        with open(path, "a", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps({
                    "archived_at": now,
                    "reason": reason,
                    "key": key,
                    "item": item,
                }, ensure_ascii=False) + "\n")
        ks = self.data.setdefault("knowledge_summary", {})
        ks["total_archived_items"] = int(ks.get("total_archived_items", 0)) + len(items)
        return len(items)

    def _trim(self, key):
        items = self.data.get(key, [])
        if len(items) > self.limit:
            old = items[:-self.limit]
            self._update_summary_from_items(key, old)
            self._archive_items(key, old, "auto_trim")
            self.data[key] = items[-self.limit:]

    def _append(self, key, payload):
        payload["timestamp"] = datetime.now().isoformat(timespec="seconds")
        items = self.data.setdefault(key, [])
        if key in ("facts", "aim_notes", "insights", "dialog_history"):
            text_field = {
                "facts": "text",
                "aim_notes": "advice",
                "insights": "insight",
                "dialog_history": "content",
            }.get(key, "text")
            new_text = payload.get(text_field, "")
            for item in items:
                if item.get(text_field) == new_text:
                    item["timestamp"] = payload["timestamp"]
                    self.save()
                    return
        items.append(payload)
        self._trim(key)
        self.save()

    def add_dialog_message(self, role: str, content: str):
        self._append("dialog_history", {"role": role, "content": content})

    def get_recent_dialog(self, count: int = 10) -> list:
        items = self.data.get("dialog_history", [])
        return items[-count:] if items else []

    def remember_fact(self, text, source="system"):
        if not text or source in ("runtime",):
            return
        self._append("facts", {"text": text, "source": source})

    def remember_task(self, task, outcome, last_command=""):
        if not task:
            return
        self._append("task_history", {"task": task, "outcome": outcome, "last_command": last_command})

    def remember_command(self, task, command, executed, screen_desc=""):
        if not command:
            return
        self._append("command_history", {
            "task": task,
            "command": command,
            "executed": executed,
            "screen_desc": self._compress_screen_desc(screen_desc),
        })

    def _compress_screen_desc(self, text: str, limit: int = 420) -> str:
        if not text:
            return ""
        keep = []
        for line in str(text).splitlines():
            low = line.lower()
            if any(key in low for key in ("screen_context", "active_window", "scene:", "window:", "motion:", "crosshair:", "result:", "hint:", "error:", "ui tree error")):
                keep.append(line.strip())
        compact = "\n".join(x for x in keep if x)
        return (compact or str(text))[:limit]

    def remember_agent_event(self, task: str, phase: str, summary: str, visual_ref: dict = None):
        if not task and not summary:
            return
        self._append("task_history", {
            "task": (task or "")[:500],
            "outcome": (summary or "")[:800],
            "last_command": phase[:120],
            "visual_ref": visual_ref or {},
            "kind": "agent_event",
        })

    def remember_aim_note(self, screen_desc, advice):
        if not advice:
            return
        self._append("aim_notes", {"screen_desc": screen_desc[:700], "advice": advice, "kind": "auto_screen"})
        self.bump_stat("aim_auto_advices")

    def remember_aim_observation(self, screen_desc: str, advice: str, profile: str = ""):
        if not advice:
            return
        self._append("aim_notes", {
            "screen_desc": self._compress_screen_desc(screen_desc, limit=520),
            "advice": advice[:500],
            "profile": profile[:120],
            "kind": "screen_sensor",
        })

    def remember_aim_frame(self, frame: dict):
        if not isinstance(frame, dict):
            return
        compact = {
            "profile": frame.get("profile", "Auto Detect")[:120],
            "scene": frame.get("scene", "unknown"),
            "confidence": frame.get("confidence", 0.0),
            "motion": frame.get("motion", "unknown"),
            "motion_value": frame.get("motion_value", 0.0),
            "center_activity": frame.get("center_activity", 0.0),
            "crosshair": bool(frame.get("crosshair", False)),
            "result_screen": bool(frame.get("result_screen", False)),
            "enemy_count": int(frame.get("enemy_count", 0) or 0),
            "enemy_boxes": frame.get("enemy_boxes", [])[:12],
            "advice": frame.get("advice", "")[:400],
        }
        self._append("aim_frames", compact)
        agg = self.data.setdefault("aim_aggregates", {}).setdefault(compact["profile"], {
            "frames": 0, "result_screens": 0, "motion_high": 0, "enemy_frames": 0,
        })
        agg["frames"] = int(agg.get("frames", 0) or 0) + 1
        if compact["result_screen"]:
            agg["result_screens"] = int(agg.get("result_screens", 0) or 0) + 1
        if compact["motion"] == "high":
            agg["motion_high"] = int(agg.get("motion_high", 0) or 0) + 1
        if compact["enemy_count"] > 0:
            agg["enemy_frames"] = int(agg.get("enemy_frames", 0) or 0) + 1
        self.save()

    def remember_visual_snapshot(self, snapshot: dict):
        if not isinstance(snapshot, dict) or not snapshot.get("full"):
            return
        compact = {
            "reason": snapshot.get("reason", "")[:80],
            "full": snapshot.get("full", ""),
            "window": snapshot.get("window", {}),
            "screen_hash": snapshot.get("screen_hash", ""),
            "tiles": snapshot.get("tiles", [])[:12],
            "summary": snapshot.get("summary", "")[:900],
        }
        self._append("visual_snapshots", compact)
        self.data["visual_snapshots"] = self.data["visual_snapshots"][-40:]
        ks = self.data.setdefault("knowledge_summary", {})
        ks["last_visual_snapshot"] = compact
        ks["visual_snapshot_count"] = int(ks.get("visual_snapshot_count", 0) or 0) + 1

    def remember_benchmark_event(self, event: dict):
        if not isinstance(event, dict):
            return
        self._append("benchmark_events", event)
        game = event.get("game") or "Auto Detect"
        agg = self.data.setdefault("aim_aggregates", {}).setdefault(game, {"events": 0, "result_screens": 0, "motion_high": 0})
        agg["events"] = int(agg.get("events", 0)) + 1
        if event.get("result_screen"):
            agg["result_screens"] = int(agg.get("result_screens", 0)) + 1
        if event.get("motion") == "high":
            agg["motion_high"] = int(agg.get("motion_high", 0)) + 1
        self.save()

    def remember_aim_qa(self, question: str, answer: str, profile: str = ""):
        q = (question or "").strip()
        a = (answer or "").strip()
        if not q or not a:
            return
        payload = {"question": q[:2000], "answer": a[:4500], "profile": profile[:120]}
        items = self.data.setdefault("aim_qa", [])
        for it in items:
            if it.get("question", "").strip() == q:
                it["answer"] = payload["answer"]
                it["profile"] = payload["profile"]
                it["timestamp"] = datetime.now().isoformat(timespec="seconds")
                self.save()
                return
        payload["timestamp"] = datetime.now().isoformat(timespec="seconds")
        items.append(payload)
        self._trim("aim_qa")
        self.save()

    def remember_insight(self, text, source="aim", confidence=0.5):
        if not text:
            return
        self._append("insights", {"insight": text, "source": source, "confidence": confidence})

    def recent_summary(self, key, count=5):
        items = self.data.get(key, [])
        return items[-count:] if items else []

    def get_insights(self, count=10):
        items = self.data.get("insights", [])
        return [item.get("insight", "") for item in items[-count:][::-1]]

    def get_aim_qa_pairs(self, count=8):
        items = self.data.get("aim_qa", [])
        return items[-count:] if items else []

    def bump_stat(self, key, amount=1):
        stats = self.data.setdefault("stats", {})
        stats[key] = int(stats.get(key, 0)) + amount
        self.save()

    def get_aim_stats(self):
        stats = self.data.setdefault("stats", {})
        return {
            "aim_questions": int(stats.get("aim_questions", 0)),
            "aim_answers": int(stats.get("aim_answers", 0)),
            "aim_auto_advices": int(stats.get("aim_auto_advices", 0)),
            "aim_sessions_started": int(stats.get("aim_sessions_started", 0)),
            "aim_manual_notes": int(stats.get("aim_manual_notes", 0)),
        }

    def aim_rank_guess(self):
        stats = self.get_aim_stats()
        activity = stats["aim_auto_advices"] + stats["aim_answers"] * 2 + stats["aim_questions"] * 2 + stats["aim_sessions_started"] * 3
        if activity < 6: return "Железо"
        if activity < 14: return "Бронза"
        if activity < 24: return "Серебро"
        if activity < 36: return "Золото"
        if activity < 48: return "Платина"
        return "Алмаз+"

    def _update_summary_from_items(self, key: str, items: list):
        if not items:
            return
        ks = self.data.setdefault("knowledge_summary", {})
        ks["last_updated"] = datetime.now().isoformat(timespec="seconds")
        if key == "command_history":
            cmds = Counter((it.get("command", "").split(":", 1)[0] or "UNKNOWN") for it in items if isinstance(it, dict))
            patt = ks.setdefault("task_patterns", {})
            for k, v in cmds.items():
                patt[k] = int(patt.get(k, 0)) + int(v)
        elif key == "aim_notes":
            adv = Counter()
            for it in items:
                if not isinstance(it, dict):
                    continue
                text = (it.get("advice") or "").lower()
                for word in ("резк", "плав", "центр", "прицел", "результат", "точность"):
                    if word in text:
                        adv[word] += 1
            patt = ks.setdefault("aim_patterns", {})
            for k, v in adv.items():
                patt[k] = int(patt.get(k, 0)) + int(v)
        elif key == "insights":
            stable = ks.setdefault("stable_insights", [])
            for it in items[-20:]:
                text = it.get("insight") if isinstance(it, dict) else ""
                if text and text not in stable:
                    stable.append(text[:240])
            ks["stable_insights"] = stable[-80:]

    def compact(self, keep_last=50, preserve_archive=True, reason="manual_compact"):
        keep_last = max(10, int(keep_last or 50))
        archived_total = 0
        keys = ("facts", "task_history", "command_history", "aim_notes", "aim_frames", "aim_qa", "insights", "dialog_history", "benchmark_events", "visual_snapshots")
        for key in keys:
            items = self.data.get(key, [])
            if len(items) > keep_last:
                old, new = items[:-keep_last], items[-keep_last:]
                self._update_summary_from_items(key, old)
                if preserve_archive:
                    archived_total += self._archive_items(key, old, reason)
                self.data[key] = new
        rec = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "reason": reason,
            "keep_last": keep_last,
            "archived_items": archived_total,
            "archive_path": self.archive_path,
        }
        self.data.setdefault("compression_history", []).append(rec)
        self.data["compression_history"] = self.data["compression_history"][-80:]
        self.prune_runtime_context()
        self.save_now()
        return rec

    def prune_runtime_context(self):
        limits = {
            "command_history": 90,
            "task_history": 80,
            "aim_notes": 80,
            "aim_frames": 160,
            "visual_snapshots": 40,
            "dialog_history": 80,
            "benchmark_events": 80,
        }
        for key, limit in limits.items():
            items = self.data.get(key, [])
            if len(items) > limit:
                old = items[:-limit]
                self._update_summary_from_items(key, old)
                self._archive_items(key, old, "prune_runtime_context")
                self.data[key] = items[-limit:]
        for cmd in self.data.get("command_history", []):
            if isinstance(cmd, dict):
                cmd["screen_desc"] = self._compress_screen_desc(cmd.get("screen_desc", ""))
        for note in self.data.get("aim_notes", []):
            if isinstance(note, dict):
                note["screen_desc"] = self._compress_screen_desc(note.get("screen_desc", ""), limit=520)
        ks = self.data.setdefault("knowledge_summary", {})
        stable = ks.get("stable_insights", [])
        ks["stable_insights"] = stable[-50:] if isinstance(stable, list) else []
        self.save_now()

    def sleep_compact(self, keep_last=80):
        report = self.build_sleep_report()
        self.data.setdefault("sleep_reports", []).append(report)
        self.data["sleep_reports"] = self.data["sleep_reports"][-60:]
        rec = self.compact(keep_last=keep_last, preserve_archive=True, reason="sleep_compact")
        return {"report": report, "compact": rec}

    def build_sleep_report(self):
        now = datetime.now().isoformat(timespec="seconds")
        recent_cmds = self.data.get("command_history", [])[-80:]
        recent_aim = self.data.get("aim_notes", [])[-80:]
        recent_aim_frames = self.data.get("aim_frames", [])[-120:]
        recent_bench = self.data.get("benchmark_events", [])[-30:]
        recent_visual = self.data.get("visual_snapshots", [])[-12:]
        cmd_counter = Counter((x.get("command", "").split(":", 1)[0] or "UNKNOWN") for x in recent_cmds if isinstance(x, dict))
        fail_count = sum(1 for x in recent_cmds if isinstance(x, dict) and not x.get("executed", True))
        aim_words = Counter()
        for item in recent_aim:
            txt = (item.get("advice", "") if isinstance(item, dict) else "").lower()
            for word in ("резк", "плав", "центр", "прицел", "результат", "точность", "темп"):
                if word in txt:
                    aim_words[word] += 1
        lines = []
        if cmd_counter:
            lines.append("Команды чаще всего: " + ", ".join(f"{k}={v}" for k, v in cmd_counter.most_common(5)))
        if fail_count:
            lines.append(f"Провалов команд за свежий период: {fail_count}")
        if aim_words:
            lines.append("Aim-паттерны: " + ", ".join(f"{k}={v}" for k, v in aim_words.most_common(5)))
        if recent_aim_frames:
            enemy_frames = sum(1 for x in recent_aim_frames if isinstance(x, dict) and x.get("enemy_count", 0) > 0)
            high_motion = sum(1 for x in recent_aim_frames if isinstance(x, dict) and x.get("motion") == "high")
            result_frames = sum(1 for x in recent_aim_frames if isinstance(x, dict) and x.get("result_screen"))
            lines.append(f"Aim-кадры: {len(recent_aim_frames)}, с врагами {enemy_frames}, резких {high_motion}, результатов {result_frames}")
        if recent_bench:
            lines.append(f"Benchmark/result событий сохранено: {len(recent_bench)}")
        if recent_visual:
            last_visual = recent_visual[-1]
            lines.append(f"Визуальная память: {len(recent_visual)} свежих снимков, последний: {last_visual.get('summary','')[:120]}")
        stuck = [x for x in recent_cmds if isinstance(x, dict) and not x.get("executed", True)]
        if stuck:
            last_task = stuck[-1].get("task", "")
            if last_task:
                lines.append(f"Вопрос после сна: какой другой путь выбрать для «{last_task[:70]}»?")
        if not lines:
            lines.append("Новых данных мало; память сохранена без выводов.")
        return {"timestamp": now, "summary": lines, "recent_counts": {"commands": len(recent_cmds), "aim": len(recent_aim), "aim_frames": len(recent_aim_frames), "benchmarks": len(recent_bench), "visual": len(recent_visual)}}

    def build_context_text(self, max_chars=2200):
        ks = self.data.get("knowledge_summary", {})
        out = ["MEMORY_CONTEXT:"]
        stable = ks.get("stable_insights", [])[-8:]
        if stable:
            out.append("Устойчивые выводы: " + "; ".join(stable))
        patt = ks.get("aim_patterns", {})
        if patt:
            out.append("Aim-паттерны: " + ", ".join(f"{k}={v}" for k, v in sorted(patt.items(), key=lambda x: -x[1])[:6]))
        recent = self.get_insights(5)
        if recent:
            out.append("Свежие инсайты: " + "; ".join(recent))
        visual = ks.get("last_visual_snapshot")
        if visual:
            out.append("Последняя визуальная карта: " + visual.get("summary", "")[:300])
        text = "\n".join(out)
        return text[:max_chars]

    def ui_aim_summary(self, lines_each=3):
        out = []
        for i in self.get_insights(count=lines_each):
            if i:
                out.append(f"🧠 {i[:160]}{'…' if len(i) > 160 else ''}")
        ks = self.data.get("knowledge_summary", {})
        archived = int(ks.get("total_archived_items", 0) or 0)
        if archived:
            out.append(f"🗄 Архивировано без потери: {archived} записей → {self.archive_path}")
        last_sleep = self.data.get("sleep_reports", [])[-1:] or []
        if last_sleep:
            for line in last_sleep[0].get("summary", [])[:3]:
                out.append(f"🌙 {line}")
        qa = self.get_aim_qa_pairs(1)
        if qa:
            q = qa[-1]
            out.append(f"❓ {q.get('question', '')[:100]}…")
            out.append(f"💬 {q.get('answer', '')[:120]}…")
        return out or ["Память коуча пуста."]

    def update_aim_aggregates(self, game: str, vision_out: str):
        import re
        agg = self.data.setdefault("aim_aggregates", {})
        game_agg = agg.setdefault(game, {"sessions_count": 0, "accuracy_trend": [], "score_trend": [], "hs_trend": []})
        game_agg["sessions_count"] += 1
        acc_match = re.search(r'(?:acc|accuracy|точность)[:\s]+(\d+\.?\d*)\s*%', vision_out, re.I)
        score_match = re.search(r'(?:score|сч[её]т)[:\s]+(\d+)', vision_out, re.I)
        hs_match = re.search(r'(?:hs|headshots?)[:\s]+(\d+\.?\d*)\s*%?', vision_out, re.I)
        if acc_match:
            acc = float(acc_match.group(1))
            game_agg["accuracy_trend"].append(acc)
            game_agg["accuracy_trend"] = game_agg["accuracy_trend"][-20:]
            game_agg["avg_accuracy"] = round(sum(game_agg["accuracy_trend"]) / len(game_agg["accuracy_trend"]), 1)
        if score_match:
            score = int(score_match.group(1))
            game_agg["score_trend"].append(score)
            game_agg["score_trend"] = game_agg["score_trend"][-20:]
            game_agg["best_score"] = max(game_agg["score_trend"])
        if hs_match:
            hs = float(hs_match.group(1))
            game_agg["hs_trend"].append(hs)
            game_agg["hs_trend"] = game_agg["hs_trend"][-20:]
            game_agg["avg_hs"] = round(sum(game_agg["hs_trend"]) / len(game_agg["hs_trend"]), 1)
        self.save()

    def get_aim_aggregates(self) -> dict:
        return self.data.get("aim_aggregates", {})

    def auto_sleep_analysis(self, frame_buffer: list) -> dict:
        if not frame_buffer:
            return {"insights": []}
        scenes = {}
        enemy_counts = []
        motion_vals = []
        for state in frame_buffer[-50:]:
            scene = getattr(state, 'scene', 'unknown')
            scenes[scene] = scenes.get(scene, 0) + 1
            enemy_counts.append(len(getattr(state, 'enemies', [])))
            motion_vals.append(getattr(state, 'motion_value', 0.0))
        dominant = max(scenes.items(), key=lambda x: x[1])[0] if scenes else "unknown"
        avg_enemies = sum(enemy_counts) / max(1, len(enemy_counts))
        avg_motion = sum(motion_vals) / max(1, len(motion_vals)) if motion_vals else 0.0

        insights = []
        if avg_enemies > 0:
            insights.append(f"В среднем {avg_enemies:.1f} врагов на кадр, сцена: {dominant}")
        else:
            insights.append("Враги не обнаружены — возможно, пауза или меню.")
        insights.append(f"Среднее движение: {avg_motion:.3f} (0=статично, 1=активно)")

        self.data["knowledge_summary"]["last_sleep_analysis"] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "dominant_scene": dominant,
            "avg_enemies": round(avg_enemies, 2),
            "avg_motion": round(avg_motion, 3),
            "insights": insights
        }
        self.save()
        return {"insights": insights, "dominant_scene": dominant, "avg_enemies": avg_enemies, "avg_motion": avg_motion}
