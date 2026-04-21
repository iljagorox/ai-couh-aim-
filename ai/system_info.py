# -*- coding: utf-8 -*-
import os
import subprocess
import winreg
from pathlib import Path
from typing import Dict, List, Optional

class SystemInfo:
    def __init__(self):
        self._cache = {}
        self._scan_system()

    def _scan_system(self):
        self.installed_apps = {}
        self.browsers = {}
        self._scan_browsers()
        self._cache['context'] = self._build_context()

    def _scan_browsers(self):
        paths = {
            'chrome': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            'firefox': r'C:\Program Files\Mozilla Firefox\firefox.exe',
            'edge': r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        }
        for name, path in paths.items():
            if os.path.exists(path):
                self.browsers[name] = path

    def _build_context(self):
        browsers = ', '.join(self.browsers.keys()) or 'не найдены'
        return f"Windows. Браузеры: {browsers}."

    def get_system_context_for_planner(self) -> str:
        return self._cache['context']

    def get_available_browsers(self):
        return list(self.browsers.keys())