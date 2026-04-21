# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import csv

class FileManager:
    def read_file(self, path: str) -> Optional[str]:
        p = Path(path)
        if not p.exists():
            return None
        try:
            return p.read_text(encoding='utf-8', errors='replace')[:5000]
        except:
            return None

    def list_directory(self, path: str) -> List[str]:
        p = Path(path)
        if not p.is_dir():
            return []
        return [f.name for f in p.iterdir()][:50]

    def find_aim_stats_files(self) -> List[str]:
        return []