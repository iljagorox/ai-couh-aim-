# -*- coding: utf-8 -*-
"""
Формулы детекции игры и персонажа по пикселям/HUD.
Каждая формула — функция, которая принимает numpy array (кадр) и возвращает
{"game": str, "character": str, "confidence": float}
"""

import re
import numpy as np

# ─── HUD ZONES (относительные координаты, 0..1) ──────────────────
# Каждая игра имеет свой fingerprint по расположению элементов UI

HUD_FINGERPRINTS = {
    "CS2": {
        "hp_bar":       {"pos": (0.02, 0.92, 0.20, 0.96), "color": (50, 255, 50)},
        "ammo":         {"pos": (0.72, 0.92, 0.88, 0.98), "type": "text"},
        "radar":        {"pos": (0.01, 0.68, 0.14, 0.88)},
        "money":        {"pos": (0.02, 0.85, 0.12, 0.91), "type": "text"},
        "crosshair":    {"style": "static", "gap": 2},
        "density":      {"hud_pixels": 0.03, "hud_region": "corners"},
    },
    "Overwatch": {
        "hp_bar":       {"pos": (0.40, 0.06, 0.60, 0.10), "type": "layered"},
        "abilities":    {"pos": (0.30, 0.88, 0.70, 0.98)},
        "ult":          {"pos": (0.42, 0.82, 0.58, 0.87)},
        "killfeed":     {"pos": (0.60, 0.05, 0.95, 0.30)},
        "crosshair":    {"style": "dot", "size": 2},
        "density":      {"hud_pixels": 0.08, "hud_region": "bottom_center"},
    },
    "TF2": {
        "hp_bar":       {"pos": (0.35, 0.90, 0.50, 0.96), "color": (200, 200, 20)},
        "ammo":         {"pos": (0.55, 0.90, 0.70, 0.96)},
        "class_icon":   {"pos": (0.02, 0.02, 0.08, 0.10)},
        "ubercharge":   {"pos": (0.40, 0.85, 0.60, 0.90), "type": "medic_only"},
        "crosshair":    {"style": "small_cross"},
        "density":      {"hud_pixels": 0.05},
    },
    "Marvel Rivals": {
        "hp_bar":       {"pos": (0.35, 0.90, 0.55, 0.96), "color": (50, 200, 50)},
        "abilities":    {"pos": (0.25, 0.82, 0.75, 0.90)},
        "team_hp":      {"pos": (0.35, 0.02, 0.65, 0.08)},
        "ult":          {"pos": (0.40, 0.78, 0.60, 0.82)},
        "density":      {"hud_pixels": 0.10},
    },
    "Deadlock": {
        "hp_bar":       {"pos": (0.10, 0.88, 0.40, 0.96), "color": (50, 200, 50)},
        "stamina":      {"pos": (0.10, 0.84, 0.30, 0.88)},
        "souls":        {"pos": (0.45, 0.02, 0.55, 0.06), "type": "text"},
        "abilities":    {"pos": (0.35, 0.90, 0.70, 0.98)},
        "third_person": True,
        "density":      {"hud_pixels": 0.07},
    },
    "FragPunk": {
        "hp_bar":       {"pos": (0.35, 0.90, 0.50, 0.96), "color": (50, 200, 50)},
        "cards":        {"pos": (0.05, 0.75, 0.25, 0.85)},
        "abilities":    {"pos": (0.25, 0.85, 0.75, 0.95)},
        "density":      {"hud_pixels": 0.09},
    },
    "Payday 2": {
        "hp_bar":       {"pos": (0.02, 0.88, 0.15, 0.96), "color": (50, 200, 50)},
        "armor":        {"pos": (0.02, 0.82, 0.15, 0.88)},
        "ammo":         {"pos": (0.65, 0.90, 0.80, 0.96)},
        "density":      {"hud_pixels": 0.04},
    },
    "KovaaK": {
        "score":        {"pos": (0.40, 0.05, 0.60, 0.12), "type": "large_text"},
        "scenario":     {"pos": (0.35, 0.15, 0.65, 0.20), "type": "text"},
        "timer":        {"pos": (0.45, 0.80, 0.55, 0.85), "type": "text"},
        "crosshair":    {"style": "none"},
        "density":      {"hud_pixels": 0.02},
    },
    "3D Aim Trainer": {
        "score":        {"pos": (0.40, 0.10, 0.60, 0.18), "type": "large_text"},
        "accuracy":     {"pos": (0.40, 0.20, 0.60, 0.25), "type": "text"},
        "crosshair":    {"style": "dot"},
        "density":      {"hud_pixels": 0.03},
    },
    "Aimbeast": {
        "score":        {"pos": (0.35, 0.08, 0.65, 0.18), "type": "text"},
        "timer":        {"pos": (0.45, 0.82, 0.55, 0.88), "type": "text"},
        "density":      {"hud_pixels": 0.02},
    },
}

# ─── CHARACTER HP FORMULAS ───────────────────────────────────────

TF2_CLASSES = {
    "Scout":    {"hp": 125, "speed": 1.33, "weapon_hint": "scattergun"},
    "Soldier":  {"hp": 200, "speed": 0.80, "weapon_hint": "rocket_launcher"},
    "Pyro":     {"hp": 175, "speed": 1.00, "weapon_hint": "flamethrower"},
    "Demoman":  {"hp": 175, "speed": 0.93, "weapon_hint": "grenade_launcher"},
    "Heavy":    {"hp": 300, "speed": 0.77, "weapon_hint": "minigun"},
    "Engineer": {"hp": 125, "speed": 1.00, "weapon_hint": "shotgun"},
    "Medic":    {"hp": 150, "speed": 1.07, "weapon_hint": "medigun"},
    "Sniper":   {"hp": 125, "speed": 1.00, "weapon_hint": "sniper_rifle"},
    "Spy":      {"hp": 125, "speed": 1.07, "weapon_hint": "revolver"},
}

OVERWATCH_HEROES = {
    "Tracer":       {"hp": 150, "class": "dps", "speed": "high"},
    "Soldier: 76":  {"hp": 200, "class": "dps", "speed": "medium"},
    "Cassidy":      {"hp": 200, "class": "dps", "speed": "medium"},
    "Pharah":       {"hp": 200, "class": "dps", "speed": "low"},
    "Reaper":       {"hp": 250, "class": "dps", "speed": "medium"},
    "Sombra":       {"hp": 200, "class": "dps", "speed": "high"},
    "Genji":        {"hp": 200, "class": "dps", "speed": "high"},
    "Hanzo":        {"hp": 200, "class": "dps", "speed": "medium"},
    "Widowmaker":   {"hp": 200, "class": "dps", "speed": "medium"},
    "Junkrat":      {"hp": 200, "class": "dps", "speed": "medium"},
    "Mei":          {"hp": 250, "class": "dps", "speed": "medium"},
    "Bastion":      {"hp": 300, "class": "dps", "speed": "low"},
    "Ashe":         {"hp": 200, "class": "dps", "speed": "medium"},
    "Echo":         {"hp": 200, "class": "dps", "speed": "high"},
    "Sojourn":      {"hp": 200, "class": "dps", "speed": "high"},
    "Venture":      {"hp": 275, "class": "dps", "speed": "high"},
    "Reinhardt":    {"hp": 625, "class": "tank", "armor": 250},
    "Zarya":        {"hp": 475, "class": "tank", "shield": 225},
    "Winston":      {"hp": 550, "class": "tank", "armor": 150},
    "D.Va":         {"hp": 700, "class": "tank", "armor": 300},
    "Orisa":        {"hp": 650, "class": "tank", "armor": 300},
    "Sigma":        {"hp": 600, "class": "tank", "shield": 200},
    "Wrecking Ball": {"hp": 700, "class": "tank", "shield": 200},
    "Ramattra":     {"hp": 600, "class": "tank", "armor": 150},
    "Mauga":        {"hp": 700, "class": "tank", "armor": 300},
    "Junker Queen": {"hp": 500, "class": "tank", "armor": 200},
    "Ana":          {"hp": 200, "class": "support", "speed": "medium"},
    "Mercy":        {"hp": 200, "class": "support", "speed": "medium"},
    "Lucio":        {"hp": 150, "class": "support", "speed": "high"},
    "Zenyatta":     {"hp": 200, "class": "support", "speed": "low", "shield": 50},
    "Brigitte":     {"hp": 250, "class": "support", "armor": 50},
    "Moira":        {"hp": 200, "class": "support", "speed": "medium"},
    "Baptiste":     {"hp": 200, "class": "support", "speed": "medium"},
    "Kiriko":       {"hp": 200, "class": "support", "speed": "medium"},
    "Lifeweaver":   {"hp": 225, "class": "support", "speed": "medium"},
    "Illari":       {"hp": 200, "class": "support", "speed": "medium"},
    "Jun0":         {"hp": 200, "class": "support", "speed": "high"},
}

MARVEL_RIVALS_HEROES = {
    "Iron Man":     {"hp": 250, "class": "dps"},
    "Spider-Man":   {"hp": 250, "class": "dps"},
    "Black Panther":{"hp": 300, "class": "dps"},
    "Storm":        {"hp": 300, "class": "dps"},
    "Wolverine":    {"hp": 350, "class": "dps"},
    "Hela":         {"hp": 275, "class": "dps"},
    "Magik":        {"hp": 300, "class": "dps"},
    "Namor":        {"hp": 300, "class": "dps"},
    "Star-Lord":    {"hp": 300, "class": "dps"},
    "Scarlet Witch":{"hp": 300, "class": "dps"},
    "Hawkeye":      {"hp": 250, "class": "dps"},
    "The Punisher": {"hp": 300, "class": "dps"},
    "Winter Soldier":{"hp": 300, "class": "dps"},
    "Psylocke":     {"hp": 275, "class": "dps"},
    "Black Widow":  {"hp": 275, "class": "dps"},
    "Mister Fantastic":{"hp": 400, "class": "dps"},
    "Human Torch":  {"hp": 250, "class": "dps"},
    "Squirrel Girl": {"hp": 300, "class": "dps"},
    "Moon Knight":  {"hp": 300, "class": "dps"},
    "Hulk":         {"hp": 750, "class": "tank"},
    "Thor":         {"hp": 600, "class": "tank"},
    "Venom":        {"hp": 700, "class": "tank"},
    "Groot":        {"hp": 750, "class": "tank"},
    "Doctor Strange":{"hp": 650, "class": "tank"},
    "Captain America": {"hp": 650, "class": "tank"},
    "Magneto":      {"hp": 600, "class": "tank"},
    "Peni Parker":  {"hp": 650, "class": "tank"},
    "Thing":        {"hp": 700, "class": "tank"},
    "Luna Snow":    {"hp": 250, "class": "support"},
    "Mantis":       {"hp": 275, "class": "support"},
    "Adam Warlock": {"hp": 300, "class": "support"},
    "Jeff":         {"hp": 250, "class": "support"},
    "Loki":         {"hp": 300, "class": "support"},
    "Rocket Raccoon":{"hp": 300, "class": "support"},
    "Cloak & Dagger":{"hp": 300, "class": "support"},
    "Invisible Woman":{"hp": 300, "class": "support"},
    "Susan Storm":  {"hp": 300, "class": "support"},
    "Dagger":       {"hp": 300, "class": "support"},
}


def identify_hud(frame: np.ndarray) -> dict:
    """
    Сканирует кадр, определяет игру по HUD fingerprint.
    Сравнивает плотность пикселей в зонах + цвета.
    """
    if frame is None:
        return {"game": "unknown", "confidence": 0.0}
    h, w = frame.shape[:2]
    results = []

    for game_name, hud in HUD_FINGERPRINTS.items():
        score = 0.0
        checks = 0

        for zone_name, zone in hud.items():
            if zone_name == "density":
                checks += 1
                continue
            if "pos" not in zone:
                continue
            x1 = int(zone["pos"][0] * w)
            y1 = int(zone["pos"][1] * h)
            x2 = int(zone["pos"][2] * w)
            y2 = int(zone["pos"][3] * h)
            if x2 <= x1 or y2 <= y1:
                continue
            checks += 1
            region = frame[y1:y2, x1:x2]
            if region.size == 0:
                continue
            brightness = float(np.mean(region))
            has_content = brightness > 20
            if has_content:
                score += 1.0

        for zone_name, zone in hud.items():
            if "color" in zone:
                checks += 1
                x1 = int(zone["pos"][0] * w)
                y1 = int(zone["pos"][1] * h)
                x2 = int(zone["pos"][2] * w)
                y2 = int(zone["pos"][3] * h)
                if x2 <= x1 or y2 <= y1:
                    continue
                region = frame[y1:y2, x1:x2]
                if region.size == 0:
                    continue
                r, g, b = zone["color"]
                tol = 50
                mask = (
                    (region[:, :, 0] > r - tol) & (region[:, :, 0] < r + tol) &
                    (region[:, :, 1] > g - tol) & (region[:, :, 1] < g + tol) &
                    (region[:, :, 2] > b - tol) & (region[:, :, 2] < b + tol)
                )
                ratio = float(np.sum(mask)) / float(region.size) * 100
                if ratio > 5:
                    score += 1.5  # цвет совпал — сильный сигнал

        if checks > 0:
            confidence = score / checks
            results.append((game_name, confidence))

    results.sort(key=lambda x: -x[1])
    if not results or results[0][1] < 0.15:
        return {"game": "unknown", "confidence": 0.0}
    return {"game": results[0][0], "confidence": round(results[0][1], 3)}


def identify_character(game: str, frame: np.ndarray, ocr_text: str = "") -> dict:
    """
    Определяет персонажа/класс по HP + HUD + OCR.
    Возвращает {"character": str, "confidence": float}
    """
    if game not in ("TF2", "Overwatch", "Marvel Rivals"):
        return {"character": "unknown", "confidence": 0.0}

    hp_value = _estimate_hp(frame, game)

    if game == "TF2":
        return _match_tf2_class(hp_value, ocr_text)
    elif game == "Overwatch":
        return _match_overwatch_hero(hp_value, ocr_text)
    elif game == "Marvel Rivals":
        return _match_marvel_hero(hp_value, ocr_text)
    return {"character": "unknown", "confidence": 0.0}


def _estimate_hp(frame: np.ndarray, game: str) -> int:
    """Пытается вытащить HP из health bar."""
    hud = HUD_FINGERPRINTS.get(game)
    if not hud or "hp_bar" not in hud:
        return 0
    h, w = frame.shape[:2]
    hp_zone = hud["hp_bar"]["pos"]
    x1 = int(hp_zone[0] * w)
    y1 = int(hp_zone[1] * h)
    x2 = int(hp_zone[2] * w)
    y2 = int(hp_zone[3] * h)
    if x2 <= x1 or y2 <= y1:
        return 0
    region = frame[y1:y2, x1:x2]
    if region.size == 0:
        return 0
    # Ищем самый яркий (заполненный) цвет в зоне HP
    gray = np.mean(region, axis=2)
    filled_pixels = np.sum(gray > 40)
    total_pixels = gray.size
    if total_pixels == 0:
        return 0
    ratio = filled_pixels / total_pixels
    max_hp = 0
    if game == "TF2":
        max_hp = 300  # Heavy max
    elif game == "Overwatch":
        max_hp = 700  # D.Va / Mauga max
    elif game == "Marvel Rivals":
        max_hp = 750  # Hulk / Groot max
    else:
        return 0
    return int(ratio * max_hp)


def _match_tf2_class(hp: int, ocr: str) -> dict:
    candidates = [(cls, info) for cls, info in TF2_CLASSES.items()
                  if abs(info["hp"] - hp) < 25]
    ocr_lower = ocr.lower()
    weapon_match = [(cls, info) for cls, info in TF2_CLASSES.items()
                    if info["weapon_hint"] in ocr_lower]

    if len(candidates) == 1:
        return {"character": candidates[0][0], "confidence": 0.8}
    if weapon_match:
        return {"character": weapon_match[0][0], "confidence": 0.7}
    if len(candidates) > 1:
        return {"character": candidates[0][0], "confidence": 0.4}
    return {"character": "unknown", "confidence": 0.0}


def _match_overwatch_hero(hp: int, ocr: str) -> dict:
    candidates = [(h, info) for h, info in OVERWATCH_HEROES.items()
                  if abs(info["hp"] - hp) < 25]
    ocr_lower = ocr.lower()
    name_match = [(h, info) for h, info in OVERWATCH_HEROES.items()
                  if h.lower() in ocr_lower]

    if len(candidates) == 1 and candidates[0][1]["hp"] == hp:
        return {"character": candidates[0][0], "confidence": 0.85}
    if name_match:
        return {"character": name_match[0][0], "confidence": 0.75}
    if len(candidates) == 1:
        return {"character": candidates[0][0], "confidence": 0.5}
    if candidates:
        return {"character": candidates[0][0], "confidence": 0.3}
    # fallback: класс по HP
    if hp > 400:
        return {"character": "tank", "confidence": 0.3}
    if hp < 180:
        return {"character": "squishy", "confidence": 0.2}
    return {"character": "unknown", "confidence": 0.0}


def _match_marvel_hero(hp: int, ocr: str) -> dict:
    candidates = [(h, info) for h, info in MARVEL_RIVALS_HEROES.items()
                  if abs(info["hp"] - hp) < 25]
    ocr_lower = ocr.lower()
    name_match = [(h, info) for h, info in MARVEL_RIVALS_HEROES.items()
                  if h.lower() in ocr_lower]

    if name_match:
        return {"character": name_match[0][0], "confidence": 0.8}
    if len(candidates) == 1:
        return {"character": candidates[0][0], "confidence": 0.6}
    if candidates:
        return {"character": candidates[0][0], "confidence": 0.3}
    if hp > 500:
        return {"character": "tank", "confidence": 0.3}
    return {"character": "unknown", "confidence": 0.0}


def identify_game_and_character(frame: np.ndarray, ocr_text: str = "") -> dict:
    """
    Главная функция: определяет игру и персонажа.
    Возвращает {"game": str, "character": str, "confidence": float}
    """
    hud_result = identify_hud(frame)
    game = hud_result["game"]
    confidence = hud_result["confidence"]
    char_result = identify_character(game, frame, ocr_text)
    return {
        "game": game,
        "character": char_result["character"],
        "confidence": round(confidence * 0.7 + char_result["confidence"] * 0.3, 3),
    }
