# -*- coding: utf-8 -*-
import os


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

    def find_program(self, target):
        target = (target or "").strip().lower()
        browser_aliases = {
            "browser": "edge",
            "браузер": "edge",
            "chrome": "chrome",
            "google chrome": "chrome",
            "firefox": "firefox",
            "edge": "edge",
        }
        browser = browser_aliases.get(target)
        if browser and browser in self.browsers:
            return self.browsers[browser]
        return None
