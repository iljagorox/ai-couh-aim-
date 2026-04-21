# -*- coding: utf-8 -*-
import os
import time
import threading
import hashlib
from pathlib import Path
from typing import Set, Dict, Any, Optional

class NightCustodian:
    def __init__(self, memory_store, core=None, log_callback=None,
                 screenshots_dir="screenshots", max_screenshots=20):
        self.memory = memory_store
        self.core = core
        self.log = log_callback or print
        self.screenshots_dir = screenshots_dir
        self.max_screenshots = max_screenshots
        self.running = False
        self.interval = 300

        self.analyzed_hashes: Set[str] = set()
        self.ui_knowledge: Dict[str, Any] = {}
        self.last_analysis_time = 0.0

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()
        self.log("🌙 Ночной смотритель активирован (с анализом скриншотов)")

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                # 1. Сначала анализируем НОВЫЕ скриншоты, чтобы не потерять данные
                self._analyze_new_screenshots()
                # 2. Затем чистим старые
                self._clean_screenshots()
                # 3. Компактизируем память
                if hasattr(self.memory, 'compact'):
                    self.memory.compact(keep_last=50)
            except Exception as e:
                self.log(f"⚠️ Ошибка в цикле смотрителя: {e}")
            time.sleep(self.interval)

    def _clean_screenshots(self):
        """Удаляет скриншоты сверх лимита."""
        if not os.path.exists(self.screenshots_dir):
            return
        try:
            files = sorted(
                Path(self.screenshots_dir).glob("*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for old in files[self.max_screenshots:]:
                try:
                    old.unlink()
                    self.log(f"🧹 Удалён {old.name}")
                    # Удаляем хеш из кеша, если был
                    h = self._file_hash(old)
                    self.analyzed_hashes.discard(h)
                except PermissionError:
                    self.log(f"⚠️ Нет прав на удаление {old.name}")
                except OSError as e:
                    self.log(f"⚠️ Ошибка удаления {old.name}: {e}")
        except Exception as e:
            self.log(f"❌ Ошибка при очистке скриншотов: {e}")

    def _file_hash(self, filepath: Path) -> str:
        """MD5 хеш файла."""
        try:
            with open(filepath, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def _analyze_new_screenshots(self):
        """Анализирует все скриншоты, которые ещё не обработаны."""
        if not os.path.exists(self.screenshots_dir):
            return
        if not self.core:
            self.log("⚠️ Нет core для анализа скриншотов")
            return
        if not hasattr(self.core, 'analyze_screenshot'):
            self.log("❌ core.analyze_screenshot не реализован")
            return

        files = sorted(
            Path(self.screenshots_dir).glob("*.png"),
            key=lambda p: p.stat().st_mtime
        )
        new_count = 0
        for filepath in files:
            try:
                file_hash = self._file_hash(filepath)
                if not file_hash or file_hash in self.analyzed_hashes:
                    continue

                self.log(f"🔍 Анализ {filepath.name}...")
                analysis = self.core.analyze_screenshot(str(filepath))
                if analysis and not analysis.get('error'):
                    self._store_knowledge(filepath, analysis)
                self.analyzed_hashes.add(file_hash)
                new_count += 1
            except Exception as e:
                self.log(f"⚠️ Ошибка анализа {filepath.name}: {e}")

        if new_count > 0:
            self.log(f"📊 Проанализировано {new_count} новых скриншотов")
            self.last_analysis_time = time.time()

    def _store_knowledge(self, screenshot_path: Path, analysis: Dict[str, Any]):
        """Сохраняет извлечённые знания."""
        filename = screenshot_path.name
        self.ui_knowledge[filename] = analysis

        # Если память умеет запоминать UI-элементы
        if hasattr(self.memory, 'remember_ui_elements'):
            self.memory.remember_ui_elements(analysis.get('elements', []))
            self.log(f"💾 Знания из {filename} сохранены в память")

        # Кешируем координаты кнопок
        for elem in analysis.get('elements', []):
            if elem.get('type') == 'button' and elem.get('text'):
                btn_name = elem['text'].lower().replace(' ', '_')
                self.ui_knowledge[f"btn_{btn_name}"] = elem.get('bbox', [])
                self.log(f"📍 Запомнена кнопка '{elem['text']}': {elem.get('bbox')}")

    def get_cached_position(self, element_description: str) -> Optional[tuple]:
        """Быстрый доступ к координатам известного элемента."""
        return self.ui_knowledge.get(element_description)

    def force_analysis(self):
        """Принудительный анализ всех скриншотов сейчас."""
        self._analyze_new_screenshots()