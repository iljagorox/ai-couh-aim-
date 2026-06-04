# -*- coding: utf-8 -*-
import threading
import time
from datetime import datetime

class NightCustodian:
    """Фоновый процесс для периодического уплотнения памяти и анализа сна."""
    def __init__(self, memory_store, core, log_callback=None):
        self.memory = memory_store
        self.core = core
        self.log = log_callback or print
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log("[NightCustodian] Запущен.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self.log("[NightCustodian] Остановлен.")

    def _run(self):
        last_compact = 0.0
        last_sleep_analysis = 0.0
        while self._running:
            time.sleep(30)
            now = time.time()
            # Каждые 4 часа – компакт
            if now - last_compact > 14400:
                last_compact = now
                if self.memory:
                    self.memory.compact(keep_last=80, reason="night_custodian")
                    self.log("[NightCustodian] Выполнен компакт памяти.")
            # Каждые 15 минут – анализ сна, если есть буфер кадров
            if now - last_sleep_analysis > 900:
                last_sleep_analysis = now
                if self.core and hasattr(self.core, 'frame_buffer') and self.core.frame_buffer:
                    buffer = list(self.core.frame_buffer)
                    if len(buffer) > 10:
                        result = self.memory.auto_sleep_analysis(buffer) if self.memory else {}
                        if result.get('insights'):
                            for ins in result['insights']:
                                self.log(f"[Sleep] {ins}")