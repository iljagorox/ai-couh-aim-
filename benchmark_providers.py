# -*- coding: utf-8 -*-
"""
Плагичная система бенчмарков — любой может добавить свой провайдер.
Формат провайдера:
{
    "id": str,
    "name": str,
    "url": str,
    "ranks": [(rank_name, emoji), ...],  # от низшего к высшему
    "scenarios": {scenario_name: [score_per_rank...], ...},
    "aliases": {normalized: canonical_name, ...},  # опционально
}
"""

import re

PROVIDERS = []


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _build_aliases(scenarios: dict) -> dict:
    aliases = {}
    for name in scenarios:
        key = _normalize(name)
        aliases[key] = name
    return aliases


def register(provider: dict):
    provider.setdefault("aliases", _build_aliases(provider["scenarios"]))
    PROVIDERS.append(provider)
    return provider


def find_match(raw_text: str, provider_id: str = None):
    """
    Ищет сценарий среди провайдеров.
    Возвращает (provider, canonical_name, thresholds) или None.
    """
    cleaned = _normalize(raw_text)
    providers = [p for p in PROVIDERS if provider_id is None or p["id"] == provider_id]
    for p in providers:
        for alias_key, can_name in p["aliases"].items():
            if alias_key in cleaned or cleaned in alias_key:
                thresholds = p["scenarios"].get(can_name)
                if thresholds:
                    return (p, can_name, thresholds)
    return None


def rank_for_score(thresholds: list, ranks: list, score: float) -> dict:
    result = {"rank": None, "emoji": None, "rank_index": -1,
              "next_rank": None, "next_emoji": None, "needed": 0, "above_max": False}
    for i, thresh in enumerate(thresholds):
        if score < thresh:
            if i > 0:
                result["rank"] = ranks[i - 1][0]
                result["emoji"] = ranks[i - 1][1]
                result["rank_index"] = i - 1
            result["next_rank"] = ranks[i][0]
            result["next_emoji"] = ranks[i][1]
            result["needed"] = int(thresh - score)
            return result
    result["rank"] = ranks[-1][0]
    result["emoji"] = ranks[-1][1]
    result["rank_index"] = len(ranks) - 1
    result["above_max"] = True
    return result
    return {
        "rank": ranks[-1][0],
        "emoji": ranks[-1][1],
        "rank_index": len(ranks) - 1,
        "next_rank": None,
        "next_emoji": None,
        "needed": 0,
        "above_max": True,
    }


# ─── ПРОВАЙДЕРЫ ────────────────────────────────────────────────

register({
    "id": "viscose_easier",
    "name": "Viscose Easier",
    "url": "https://discord.gg/rawinput",
    "ranks": [
        ("Lemming", "🐭"), ("Hare", "🐇"), ("Ermine", "🦊"),
        ("Penguin", "🐧"), ("Fox", "🦊"), ("Mammoth", "🦣"),
        ("Orca", "🐋"), ("Seal", "🦭"),
    ],
    "scenarios": {
        "WhisphereRawControl Larger + Slowed":        [5500, 6700, 7800, 8700, 9600, 10500, 11400, 12500],
        "Whisphere 80%":                              [6300, 7700, 9000, 10000, 11000, 12000, 13000, 14500],
        "Smoothbot Invincible Goated 75%":            [1800, 2250, 2650, 2900, 3150, 3400, 3650, 4000],
        "Leaptrack Goated 60% Larger":                [850, 1200, 1500, 1700, 1900, 2100, 2250, 2450],
        "Controlsphere rAim Easy 90%":                [6100, 6950, 7700, 8400, 9100, 9800, 10500, 11500],
        "VT Controlsphere Intermediate S5 80%":       [1850, 2300, 2700, 3000, 3300, 3600, 3850, 4100],
        "Air Angelic 4 Voltaic Easy 80% (Good Version)": [1050, 1600, 2000, 2400, 2700, 3000, 3300, 3600],
        "Cloverrawcontrol Easy 80% Speed":            [3900, 4550, 5200, 5700, 6200, 6700, 7200, 7700],
        "Controlsphere Far, Far Larger 90%":          [7600, 8150, 8700, 9200, 9800, 10200, 10900, 11500],
        "PGTI Voltaic Easy 80%":                      [350, 550, 850, 1100, 1350, 1600, 1900, 2250],
        "Air CELESTIAL No UFO Easy Slowed":           [820, 835, 850, 861, 870, 878, 884, 890],
        "Whisphere Small & Slow 55%":                 [6000, 7500, 9000, 10000, 10750, 11500, 12250, 13500],
        "Air Voltaic Invincible 7 Easy 80%":          [750, 1200, 1600, 1900, 2200, 2500, 2800, 3200],
        "Controlsphere OW Long Strafes 90%":          [5400, 6100, 6700, 7200, 7600, 8000, 8300, 8700],
        "Flicker Plaza rAim Easy Less Blinks":        [858, 871, 883, 890, 895, 900, 904, 909],
        "Polarized Hell Easy 40% Slower":             [750, 1100, 1400, 1600, 1800, 2000, 2150, 2500],
        "Air Pure Intermediate Slower No UFO":        [860, 874, 886, 893, 901, 907, 911, 916],
        "Air Voltaic Easy Invincible 4 80%":          [1100, 1600, 2100, 2450, 2800, 3150, 3400, 3800],
        "Pokeball Frenzy Auto TE Wide":               [650, 950, 1250, 1500, 1750, 2000, 2300, 2700],
        "1w3ts Reload Larger":                        [36, 43, 50, 58, 70, 82, 92, 102],
        "voxTargetSwitch 2 Large":                    [67, 78, 87, 95, 103, 110, 117, 123],
        "BeanTS Larger":                              [65, 78, 90, 100, 110, 120, 130, 142],
        "FloatTS Angelic Easy Larger":                [65, 74, 81, 88, 95, 101, 106, 111],
        "WaldoTS Novice":                             [65, 78, 90, 100, 110, 120, 130, 140],
        "devTS Goated NR Static 5Bot":                [350, 400, 450, 500, 550, 600, 640, 680],
        "domiSwitch Easy Slower":                     [3200, 3700, 4200, 4600, 5000, 5400, 5800, 6300],
        "tamTargetSwitch Smooth Easy":                [7, 11, 15, 18, 21, 24, 26, 28],
        "1wall5targets_pasu slow":                    [76, 88, 100, 110, 120, 130, 140, 150],
        "B180 Voltaic Easy 92%":                      [26, 38, 50, 58, 65, 72, 78, 87],
        "Controlsphere Click Easy":                   [15, 21, 27, 33, 39, 45, 50, 55],
        "Popcorn MV Novice":                          [50, 100, 150, 190, 230, 270, 300, 330],
        "Pasu Angelic 20% Larger 80% Speed":          [51, 58, 65, 72, 78, 84, 90, 97],
        "1w2ts Pasu Perfected Easy":                  [58, 69, 80, 87, 93, 99, 105, 110],
        "1w3ts Pasu Perfected Micro Goated Larger 80%": [600, 700, 800, 900, 1000, 1100, 1200, 1300],
        "Floating Heads Timing 400% Larger":          [400, 700, 1000, 1350, 1700, 2050, 2400, 2750],
        "voxTargetSwitch Click":                      [49, 59, 67, 74, 81, 88, 94, 100],
    },
})

register({
    "id": "viscose_medium",
    "name": "Viscose Medium",
    "url": "https://discord.gg/rawinput",
    "ranks": [
        ("Cinnabar", "🟠"), ("Vermillion", "🔴"), ("Saffron", "🟡"),
        ("Celadon", "🟢"), ("Cerulean", "🔵"), ("Lavender", "🟣"),
        ("Indigo", "🟤"), ("Fuchsia", "🩷"),
    ],
    "scenarios": {
        "WhisphereRawControl":                        [5300, 6700, 7600, 8800, 10000, 10900, 11800, 13000],
        "Whisphere":                                  [5750, 8250, 10750, 13250, 15250, 17250, 19250, 20500],
        "Smoothbot Invincible Goated":                [1700, 2200, 2750, 3250, 3800, 4300, 4650, 5000],
        "Leaptrack Goated 75% Slightly Larger":       [1400, 1750, 2000, 2250, 2500, 2750, 3000, 3275],
        "Controlsphere rAim Easy":                    [7400, 8500, 9600, 10700, 11900, 13100, 14300, 15100],
        "VT Controlsphere Novice S5 Hard":            [2100, 2500, 2950, 3250, 3550, 3800, 4100, 4400],
        "Air Angelic 4 Voltaic Easy":                 [1900, 2300, 2650, 3000, 3400, 3750, 4100, 4450],
        "Cloverrawcontrol Easy":                      [5000, 6100, 7000, 8100, 9200, 10100, 10900, 11700],
        "Controlsphere Far Larger":                   [7800, 8600, 9300, 10000, 10800, 11700, 12700, 13600],
        "PGTI Voltaic Easy":                          [800, 1100, 1400, 1700, 2000, 2300, 2750, 3200],
        "Air CELESTIAL No UFO Easy":                  [825, 840, 855, 865, 881, 890, 902, 908],
        "Whisphere Small & Slow 75%":                 [5500, 7500, 9500, 11500, 13500, 15500, 17500, 19000],
        "Ground Plaza Sparky v3":                     [862, 872, 882, 888, 894, 900, 905, 909],
        "Controlsphere OW":                           [4800, 5700, 6400, 7300, 8100, 8900, 9800, 10500],
        "Flicker Plaza rAim Easy":                    [860, 870, 881, 891, 900, 908, 913, 917],
        "Polarized Hell Easy 20% Slower":             [1600, 1850, 2100, 2350, 2600, 2850, 3150, 3350],
        "Air Pure Intermediate":                      [847, 862, 876, 886, 895, 902, 906, 910],
        "Air Voltaic Easy Invincible 4":              [1800, 2150, 2500, 2950, 3350, 3750, 4150, 4450],
        "Pokeball Frenzy Auto TE Wide":               [1950, 2250, 2550, 2850, 3150, 3400, 3600, 3800],
        "1w3ts Reload":                               [66, 76, 86, 96, 106, 116, 126, 135],
        "voxTargetSwitch 2":                          [78, 88, 98, 107, 116, 123, 130, 136],
        "BeanTS":                                     [88, 103, 115, 127, 136, 143, 149, 156],
        "FloatTS Angelic Easy":                       [70, 79, 86, 93, 100, 107, 115, 123],
        "WaldoTS Intermediate":                       [108, 117, 126, 135, 144, 153, 162, 170],
        "devTS Goated NR Static 5Bot":                [600, 650, 705, 760, 810, 840, 870, 900],
        "domiSwitch Easy":                            [4200, 4700, 5200, 5700, 6150, 6600, 7100, 7600],
        "tamTargetSwitch Smooth Easy":                [22, 26, 29, 32, 34, 36, 38, 41],
        "1wall5targets_pasu Reload":                  [70, 85, 100, 115, 130, 142, 155, 165],
        "VT Bounceshot Intermediate":                 [550, 640, 720, 780, 850, 900, 980, 1060],
        "Controlsphere Click":                        [27, 33, 39, 45, 50, 56, 61, 67],
        "Popcorn MV Intermediate":                    [150, 190, 240, 280, 330, 380, 430, 480],
        "Pasu Angelic 20% Larger":                    [72, 79, 85, 90, 96, 103, 110, 115],
        "1w2ts Pasu Perfected":                       [60, 70, 80, 88, 96, 101, 107, 112],
        "1w3ts Pasu Perfected Micro Goated Larger":   [900, 1000, 1100, 1200, 1300, 1400, 1500, 1600],
        "Floating Heads Timing 400% Larger":          [1950, 2300, 2650, 3000, 3350, 3650, 3900, 4200],
        "voxTargetClick 20% Small":                   [62, 72, 80, 87, 95, 102, 108, 116],
    },
})

register({
    "id": "viscose_hard",
    "name": "Viscose Hard",
    "url": "https://discord.gg/rawinput",
    "ranks": [
        ("Wool", "🐑"), ("Linen", "👕"), ("Velvet", "🟣"),
        ("Chiffon", "🩻"), ("Satin", "✨"), ("Silk", "👑"),
    ],
    "scenarios": {
        "WhisphereRawControl 30% Small":              [7100, 7700, 8300, 8900, 9900, 11000],
        "Whisphere Small & Slow":                     [14000, 15250, 16500, 18000, 19500, 20500],
        "SmoothBot Invincible Goated Smaller":        [2700, 3200, 3450, 3850, 4200, 4450],
        "Leaptrack Goated 80%":                       [2500, 2625, 2750, 2850, 3000, 3200],
        "Controlsphere rAim":                         [9100, 9850, 10700, 11300, 11900, 12350],
        "VT Controlsphere Intermediate Hard":         [2850, 3200, 3500, 3800, 4000, 4200],
        "Air Angelic 4 Voltaic":                      [3300, 3650, 3850, 4100, 4225, 4350],
        "Cloverrawcontrol":                           [7000, 7650, 8200, 8650, 9200, 10100],
        "Controlsphere Far":                          [8600, 9200, 9800, 10600, 11200, 12000],
        "PGTI Voltaic":                               [1350, 1650, 1900, 2150, 2400, 2700],
        "Air CELESTIAL":                              [867, 875, 885, 890, 894, 897],
        "Whisphere Extra Small & Slow":               [8500, 10300, 11000, 12500, 13500, 14500],
        "Ground Plaza Sparky v3 Thin":                [881, 886, 891, 895, 898, 901],
        "Controlsphere OW 150%":                      [6900, 7600, 8100, 8525, 8950, 9500],
        "Flicker Plaza":                              [890, 896, 901, 905, 910, 914],
        "Polarized Hell 20% Slower":                  [2550, 2700, 2850, 3000, 3150, 3300],
        "Air Pure":                                   [884, 890, 895, 900, 905, 909],
        "Air Voltaic Invincible 4":                   [2800, 3150, 3450, 3700, 3900, 4100],
        "Pokeball Frenzy Auto TE Wide":               [3550, 3725, 3850, 4000, 4100, 4200],
        "1w2ts Reload":                               [106, 114, 121, 127, 133, 138],
        "voxTargetSwitch 2 20% Smaller":              [103, 111, 116, 121, 127, 133],
        "BeanTS 30% Smaller":                         [119, 127, 134, 139, 143, 147],
        "FloatTS Angelic":                            [94, 100, 105, 110, 114, 118],
        "WaldoTS":                                    [145, 153, 160, 166, 173, 178],
        "devTS Goated NR Static Small 5Bot":          [750, 775, 800, 825, 850, 870],
        "domiSwitch":                                 [5550, 5950, 6250, 6550, 6850, 7200],
        "tamTargetSwitch Smooth":                     [32, 35, 37, 39, 42, 45],
        "Pasu Reload Goated":                         [110, 120, 130, 140, 150, 160],
        "VT Bounceshot Advanced":                     [730, 790, 850, 910, 950, 1000],
        "Controlsphere Click Smaller":                [39, 45, 51, 56, 60, 64],
        "Popcorn MV Advanced":                        [290, 330, 370, 420, 460, 500],
        "Pasu Angelic":                               [87, 94, 102, 110, 118, 125],
        "1w2ts Pasu Perfected 30% Smaller":           [75, 82, 87, 93, 98, 103],
        "1w3ts Pasu Perfected Micro Goated":          [1100, 1200, 1300, 1400, 1500, 1560],
        "Floating Heads Timing 400% Fixed":           [3200, 3484, 3648, 3848, 4048, 4248],
        "VoxTargetSwitch Click Small":                [90, 96, 101, 106, 111, 115],
    },
})

# ═══ Voltaic Season 5 (основные сценарии) ═══

register({
    "id": "voltaic_s5",
    "name": "Voltaic Season 5",
    "url": "https://voltaic.gg",
    "ranks": [
        ("Bronze", "🥉"), ("Silver", "🥈"), ("Gold", "🥇"),
        ("Platinum", "🪙"), ("Diamond", "💎"), ("Master", "🏆"),
        ("Grandmaster", "👑"),
    ],
    "scenarios": {
        "VT PlazaSparky S5":                          [520, 625, 730, 815, 865, 895, 920],
        "VT VoxTargetSwitch S5":                      [75, 88, 100, 110, 118, 123, 130],
        "VT 1w2ts Pasu S5":                           [60, 70, 80, 92, 105, 112, 120],
        "VT Smoothbot S5":                            [1500, 2000, 2500, 3000, 3500, 3900, 4300],
        "VT LGC3 S5":                                 [800, 1200, 1600, 2000, 2400, 2750, 3100],
        "VT Pasu S5":                                 [80, 95, 110, 130, 145, 155, 165],
        "VT B180 TI S5":                              [32, 40, 48, 55, 62, 68, 74],
        "VT Popcorn S5":                              [60, 90, 120, 155, 190, 220, 250],
        "VT GroundPlaza S5":                          [860, 870, 880, 888, 894, 900, 905],
        "VT Controlsphere S5":                        [25, 32, 40, 50, 58, 63, 70],
        "VT Air Angelic S5":                          [900, 1400, 1900, 2400, 2900, 3300, 3700],
        "VT 1w4ts S5":                                [55, 65, 75, 85, 95, 100, 105],
        "VT Aim 2 S5":                                [862, 872, 882, 892, 900, 906, 912],
        "VT Dodge TS S5":                             [72, 80, 88, 96, 103, 110, 116],
    },
})

# ═══ Riddler Benchmarks (KovaaK's) ═══
# Источник: https://docs.google.com/spreadsheets/d/1HULoNX_BBne-uFuMrL9yVHTZShPDZOFb/

register({
    "id": "riddler",
    "name": "Riddler",
    "url": "https://discord.gg/kovaaks",
    "ranks": [
        ("Tin", "🪣"), ("Iron", "🔩"), ("Steel", "⚙️"),
        ("Titanium", "⚔️"), ("Mithril", "🪄"), ("Adamant", "🛡️"),
        ("Runic", "✨"), ("Legendary", "👑"),
    ],
    "scenarios": {
        "Close Long Strafes Thin":                    [6000, 8000, 10000, 12000, 14000, 16000, 18000, 20000],
        "Air Voltaic No UFO":                         [2000, 3500, 5000, 6500, 8000, 9500, 11000, 13000],
        "Air Voltaic":                                [1200, 2500, 4000, 5500, 7000, 9000, 11000, 13000],
        "Pasu Reload":                                [35, 50, 65, 80, 95, 110, 125, 140],
        "1w4ts":                                      [35, 45, 55, 65, 75, 85, 95, 105],
        "1w2ts":                                      [40, 50, 60, 70, 80, 90, 100, 110],
        "B180":                                       [20, 30, 40, 50, 60, 70, 80, 90],
        "Popcorn":                                    [40, 65, 90, 120, 150, 180, 210, 240],
    },
})

# ═══ Raw Input Benchmarks ═══
register({
    "id": "rawinput",
    "name": "Raw Input",
    "url": "https://discord.gg/rawinput",
    "ranks": [
        ("Novice", "🌱"), ("Intermediate", "🔥"), ("Advanced", "💎"),
        ("Expert", "⭐"), ("Master", "👑"),
    ],
    "scenarios": {
        "Air Voltaic":                                [2000, 4500, 7000, 10000, 13000],
        "Smoothbot":                                  [1500, 2600, 3700, 4800, 6000],
        "Pasu":                                       [50, 70, 95, 120, 145],
        "B180":                                       [25, 40, 55, 70, 85],
        "1w4ts":                                      [40, 55, 70, 85, 100],
    },
})

# ═══ Viscose old benchmark (cleanup — удалить старый файл) ═══
