# -*- coding: utf-8 -*-
import sys

def _show_missing_dependency_error(exc):
    missing = getattr(exc, "name", "unknown")
    print("Не удалось запустить СЕНТИНЕЛ ИИ.")
    print(f"Не хватает Python-пакета: {missing}")
    print("\nУстановите зависимости:")
    print("  py -m pip install -r requirements.txt")
    input("Нажмите Enter для выхода...")

if __name__ == "__main__":
    try:
        from gui import SentinelGUI
    except ModuleNotFoundError as exc:
        _show_missing_dependency_error(exc)
        sys.exit(1)

    app = SentinelGUI()
    app.mainloop()