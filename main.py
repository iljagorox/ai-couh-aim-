# -*- coding: utf-8 -*-
import sys
import io
import os
import traceback


def _safe_utf8_stdio():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            if stream and hasattr(stream, "buffer") and not stream.closed:
                buffer = stream.detach()
                setattr(sys, name, io.TextIOWrapper(buffer, encoding="utf-8", errors="replace"))
            elif not stream or stream.closed:
                os.makedirs("logs", exist_ok=True)
                fallback = open(f"logs/{name}.log", "a", encoding="utf-8", errors="replace")
                setattr(sys, name, fallback)
        except Exception:
            try:
                setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
            except Exception:
                pass


_safe_utf8_stdio()

try:
    from log import setup as _log_setup
    _log_setup()
except Exception:
    pass


def _write_startup_error(exc):
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/startup_error.log", "w", encoding="utf-8") as f:
            f.write("Не удалось запустить SENTINEL AI.\n")
            f.write(f"{type(exc).__name__}: {exc}\n\n")
            f.write(traceback.format_exc())
    except Exception:
        pass


def _show_missing_dependency_error(exc):
    missing = getattr(exc, "name", "unknown")
    try:
        print("Не удалось запустить СЕНТИНЕЛ ИИ.")
        print(f"Не хватает Python-пакета: {missing}")
        print("\nУстановите зависимости:")
        print("  py -m pip install -r requirements.txt")
        input("Нажмите Enter для выхода...")
    except Exception:
        pass

if __name__ == "__main__":
    try:
        from gui import SentinelGUI
    except ModuleNotFoundError as exc:
        _write_startup_error(exc)
        _show_missing_dependency_error(exc)
        sys.exit(1)
    except Exception as exc:
        _write_startup_error(exc)
        print(f"Не удалось открыть GUI: {exc}")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

    try:
        app = SentinelGUI()
        app.mainloop()
    except Exception as exc:
        _write_startup_error(exc)
        print(f"Критическая ошибка SENTINEL AI: {exc}")
        input("Нажмите Enter для выхода...")
