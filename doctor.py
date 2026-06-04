#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SENTINEL AI — diagnostic tool.

Usage:
  python doctor.py          # full check
  python doctor.py --quick  # skip slow checks (no model query)
"""
import subprocess
import sys
import os
import importlib
import json
from pathlib import Path

BASE = Path(__file__).parent
GREEN = "[OK]"
RED = "[FAIL]"
YELLOW = "[WARN]"
CYAN = ""
BOLD = ""
RESET = ""

def ok(msg):
    print(f"  {GREEN} {msg}")

def fail(msg):
    print(f"  {RED} {msg}")

def warn(msg):
    print(f"  {YELLOW} {msg}")

def section(title):
    print(f"\n--- {title} ---")


def check_python():
    section("Python")
    v = sys.version_info
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
    if v.major < 3 or (v.major == 3 and v.minor < 9):
        fail("Python 3.9+ required")


def check_config():
    section("Configuration")
    path = BASE / "config.json"
    if not path.exists():
        fail("config.json not found")
        return {}
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        ok(f"config.json loaded ({len(cfg)} keys)")
        model = cfg.get("brain_model", "")
        if model:
            ok(f"Brain model: {model}")
        else:
            warn("brain_model not set in config")
        if cfg.get("low_memory_mode"):
            ok(f"Low memory mode: ON")
        return cfg
    except Exception as e:
        fail(f"config.json parse error: {e}")
        return {}


def check_dependencies():
    section("Dependencies")
    required = [
        "customtkinter", "ollama", "pyautogui", "PIL", "numpy",
        "psutil", "cv2", "pygetwindow", "win32gui",
    ]
    optional = ["dxcam", "GPUtil", "pynvml", "faster_whisper", "torch"]
    for mod in required:
        try:
            m = importlib.import_module(mod.replace("-", "_").replace(".", ""))
            ver = getattr(m, "__version__", "?")
            ok(f"{mod} ({ver})")
        except ImportError:
            fail(f"{mod} not installed")
    for mod in optional:
        try:
            importlib.import_module(mod.replace("-", "_").replace(".", ""))
            ok(f"{mod} (optional)")
        except ImportError:
            warn(f"{mod} (optional, not installed)")


def check_ollama(quick=False):
    section("Ollama")
    try:
        res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
            ok(f"Ollama is running ({len(lines) - 1 if len(lines) > 1 else 0} models)")
            if lines:
                for line in lines[1:]:
                    parts = line.split()
                    if parts:
                        print(f"       {parts[0]}")
        else:
            fail(f"ollama list returned code {res.returncode}")
    except FileNotFoundError:
        fail("ollama not found in PATH")
    except subprocess.TimeoutExpired:
        fail("ollama list timed out (8s)")
    except Exception as e:
        fail(f"ollama error: {e}")


def check_model_available(cfg, quick=False):
    if quick:
        return
    section("Model check")
    model = cfg.get("brain_model", "")
    if not model:
        warn("No brain_model configured, skipping")
        return
    try:
        res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            installed = set()
            for line in res.stdout.splitlines()[1:]:
                parts = line.split()
                if parts:
                    installed.add(parts[0])
            if model in installed:
                ok(f"Model '{model}' is installed in Ollama")
            else:
                fail(f"Model '{model}' NOT found in Ollama")
                warn(f"Install with: ollama pull {model}")
    except Exception as e:
        warn(f"Cannot check model availability: {e}")


def check_files():
    section("Project files")
    expected = [
        "main.py", "gui.py", "core.py", "planner.py", "executor.py",
        "smart_pilot.py", "screen_sensor.py", "aim_coach.py", "memory.py",
        "neural_saga.py", "voice_translator.py", "night_custodian.py",
        "system_info.py", "immutable_truths.py", "game_knowledge.py",
        "file_manager.py", "AgentToolbox.py", "config.json", "requirements.txt",
        "doctor.py",
    ]
    for f in expected:
        if (BASE / f).exists():
            ok(f"{f}")
        else:
            fail(f"{f} MISSING")

    tests = BASE / "tests"
    if tests.is_dir():
        count = len(list(tests.glob("test_*.py")))
        ok(f"tests/ directory with {count} test files")
    else:
        warn("tests/ directory not found")


def check_syntax():
    section("Syntax check")
    files = sorted(BASE.glob("*.py"))
    errors = 0
    for f in files:
        try:
            compile(f.read_text(encoding="utf-8"), f.name, "exec")
            ok(f.name)
        except SyntaxError as e:
            fail(f.name + ": " + str(e))
            errors += 1
    if errors:
        fail(f"{errors} file(s) with syntax errors")
    else:
        ok(f"All {len(files)} .py files pass syntax check")


def run():
    quick = "--quick" in sys.argv
    print("SENTINEL AI -- Diagnostic Tool")
    print(f"  Python: {sys.executable}")
    print(f"  CWD:    {Path.cwd()}")
    print(f"  Root:   {BASE}")

    cfg = check_config()
    check_python()
    check_dependencies()
    check_ollama(quick)
    check_model_available(cfg, quick)
    check_files()
    check_syntax()

    print("\n--- done ---\n")
    return 0


if __name__ == "__main__":
    sys.exit(run())
