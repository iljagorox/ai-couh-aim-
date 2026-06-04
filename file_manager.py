from pathlib import Path
from typing import Optional, List, Dict, Any
import json


class FileManager:
    def read_file(self, path: str) -> Optional[str]:
        p = Path(path)
        if not p.exists():
            return None
        try:
            return p.read_text(encoding='utf-8', errors='replace')[:5000]
        except Exception:
            return None

    def write_file(self, path: str, content: str) -> bool:
        try:
            Path(path).write_text(content, encoding='utf-8')
            return True
        except Exception:
            return False

    def file_exists(self, path: str) -> bool:
        return Path(path).exists()

    def list_directory(self, path: str) -> List[str]:
        p = Path(path)
        if not p.is_dir():
            return []
        return [f.name for f in p.iterdir()][:50]

    def find_files_by_pattern(self, directory: str, pattern: str) -> List[str]:
        p = Path(directory)
        if not p.is_dir():
            return []
        return [str(f) for f in p.rglob(pattern)][:50]

    def find_aim_stats_files(self, base_dir: str = None) -> List[str]:
        if base_dir is None:
            base_dir = str(Path.home() / "Documents")
        results = []
        for ext in ("*.csv", "*.json", "*.txt"):
            results.extend(self.find_files_by_pattern(base_dir, ext))
        aim_keywords = ("aim", "kovaak", "aimlab", "aimlabs", "stats", "training", "practice")
        return [f for f in results if any(kw in f.lower() for kw in aim_keywords)]

    def read_json(self, path: str) -> Optional[Dict[str, Any]]:
        p = Path(path)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            return None

    def write_json(self, path: str, data: Dict[str, Any]) -> bool:
        try:
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            return True
        except Exception:
            return False
