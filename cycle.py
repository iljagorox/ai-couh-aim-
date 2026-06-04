# -*- coding: utf-8 -*-
import time
import json
from pathlib import Path
from datetime import datetime

import pyautogui
from screen_sensor import ScreenSensor
from core import Core


class ProcessingCycle:
    def __init__(self, config_path="config.json"):
        self.core = Core(config_path, skip_model_check=True)
        self.screen_sensor = self.core.screen_sensor
        self.cfg = self.core.cfg
        self.cycle_count = 0
        self.max_cycles = self.cfg.get("cycle_max_iterations", 100)
        self.interval = self.cfg.get("cycle_interval_sec", 1.0)

    def step(self) -> dict:
        result = {"cycle": self.cycle_count, "timestamp": time.time()}

        context = self.core.build_screen_context()
        result["scene"] = context.description[:200]
        result["confidence"] = context.confidence
        result["window"] = context.active_window.get("title", "")[:60]

        if self.core.executor and self.core.planner:
            cmd = self.core.planner.plan("observe", context.as_prompt_text())
            result["command"] = cmd
            if cmd not in ("DONE", "WAIT:"):
                ok = self.core.executor.execute(cmd)
                result["success"] = ok

        self.cycle_count += 1
        return result

    def run(self):
        print(f"[Cycle] Starting main loop ({self.max_cycles} cycles, {self.interval}s interval)")
        while self.cycle_count < self.max_cycles:
            result = self.step()
            print(f"[Cycle #{result['cycle']}] scene={result.get('scene','')[:40]} cmd={result.get('command','none')}")
            time.sleep(self.interval)


if __name__ == "__main__":
    cycle = ProcessingCycle()
    cycle.run()
