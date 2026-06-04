# -*- coding: utf-8 -*-
"""
Карта сценариев между тренажёрами:
Aim Lab → KovaaK's → Aimbeast → 3D Aim → Furry Aim
Сводит разные названия к одному Skill ID + категории.
"""

SKILL_CATEGORIES = {
    "clicking_speed": {
        "name": "Click Timing / Speed",
        "emoji": "🖱️",
    },
    "clicking_precision": {
        "name": "Click Timing / Precision",
        "emoji": "🎯",
    },
    "tracking_smoothness": {
        "name": "Tracking / Smoothness",
        "emoji": "📈",
    },
    "tracking_reactive": {
        "name": "Tracking / Reactive",
        "emoji": "⚡",
    },
    "tracking_control": {
        "name": "Tracking / Control",
        "emoji": "🎚️",
    },
    "switching_speed": {
        "name": "Target Switching / Speed",
        "emoji": "🔄",
    },
    "switching_stability": {
        "name": "Target Switching / Stability",
        "emoji": "🎯",
    },
    "switching_micro": {
        "name": "Target Switching / Micro",
        "emoji": "🔬",
    },
    "precision": {
        "name": "Precision",
        "emoji": "💎",
    },
    "reaction": {
        "name": "Reaction Time",
        "emoji": "⚡",
    },
    "movement": {
        "name": "Movement Aim",
        "emoji": "🏃",
    },
}

# Каждый сценарий: {skill_id, aliases=[по-русски, описания]}
SCENARIO_MAP = {
    # ─── CLICKING / SPEED ───────────────────────────────────────
    "clicking_speed_gridshot": {
        "skill": "clicking_speed",
        "name": "Gridshot / Static Click Speed",
        "descr": "Быстрые клики по статичным целям. База всего кликинга.",
        "game_specific": {
            "Aim Lab": ["Gridshot", "Gridshot Ultimate", "Gridshot Precision"],
            "KovaaK": ["1w6ts", "1w4ts", "1w2ts", "1w3ts Reload", "1w3ts Reload Larger"],
            "Aimbeast": ["Pokeball Frenzy", "Pokeball Frenzy Auto TE", "Pokeball Frenzy Auto TE Wide"],
            "3D Aim Trainer": ["Speed Click", "Rapid Fire", "Quick Click"],
            "Furry Aim Trainer": ["Furry Rush", "Fast Paw", "Quick Shot"],
        },
    },
    "clicking_speed_pasu": {
        "skill": "clicking_speed",
        "name": "Pasu / Dynamic Click Speed",
        "descr": "Клики по движущимся / появляющимся целям с предсказанием.",
        "game_specific": {
            "Aim Lab": ["Spidershot", "Spidershot Ultimate", "Detection Shot"],
            "KovaaK": ["1wall5targets_pasu", "1wall5targets_pasu Reload", "Pasu Reload Goated",
                       "1w2ts Pasu Perfected", "1w2ts Pasu Perfected Easy",
                       "1w3ts Pasu Perfected Micro Goated", "1w3ts Pasu Perfected Micro Goated Larger 80%",
                       "Pasu Angelic", "Pasu Angelic 20% Larger", "Pasu Angelic 20% Larger 80% Speed",
                       "1w2ts Pasu Perfected 30% Smaller", "Floating Heads Timing"],
            "Aimbeast": ["Floating Heads", "Floating Heads Timing 400% Larger", "Floating Heads Timing 400% Fixed"],
            "3D Aim Trainer": ["Flick Shot", "Moving Target", "Precision Flick"],
            "Furry Aim Trainer": ["Floating Paw", "Paw Pasu"],
        },
    },
    "clicking_precision_popcorn": {
        "skill": "clicking_precision",
        "name": "Popcorn / Small Targets",
        "descr": "Мелкие цели, высокий точность, минимальный допуск.",
        "game_specific": {
            "Aim Lab": ["Microshot", "Microshot Precision", "Lineshot"],
            "KovaaK": ["Popcorn", "Popcorn MV Novice", "Popcorn MV Intermediate", "Popcorn MV Advanced",
                       "1wall2targets_pasu", "B180 Voltaic Easy 92%",
                       "VT Bounceshot Intermediate", "VT Bounceshot Advanced",
                       "voxTargetSwitch Click", "voxTargetSwitch Click Small", "voxTargetClick 20% Small"],
            "Aimbeast": ["Bounce Shot", "Precision Pop", "Click Fest"],
            "3D Aim Trainer": ["Precision Click", "Micro Target"],
            "Furry Aim Trainer": ["Tiny Target", "Furry Precision"],
        },
    },
    # ─── TRACKING ───────────────────────────────────────────────
    "tracking_smoothness_whisphere": {
        "skill": "tracking_smoothness",
        "name": "Whisphere / Smooth Tracking",
        "descr": "Плавное ведение цели. Контроль дрожи и микро-коррекций.",
        "game_specific": {
            "Aim Lab": ["Spheretrack", "Spheretrack 90", "Spherespeed"],
            "KovaaK": ["Whisphere", "Whisphere 80%", "Whisphere Small & Slow", "Whisphere Small & Slow 75%",
                       "Whisphere Small & Slow 55%", "Whisphere Extra Small & Slow",
                       "WhisphereRawControl", "WhisphereRawControl Larger + Slowed",
                       "WhisphereRawControl 30% Small", "Cloverrawcontrol", "Cloverrawcontrol Easy",
                       "Cloverrawcontrol Easy 80% Speed", "Controlsphere Far", "Controlsphere Far Larger",
                       "Controlsphere Far, Far Larger 90%", "Controlsphere Click", "Controlsphere Click Easy",
                       "Controlsphere Click Smaller"],
            "Aimbeast": ["Smooth Sphere", "Precision Track", "Control Track"],
            "3D Aim Trainer": ["Smooth Track", "Sphere Follow", "Circle Track"],
            "Furry Aim Trainer": ["Paw Track", "Furry Sphere"],
        },
    },
    "tracking_control_air": {
        "skill": "tracking_control",
        "name": "Air / Vertical Tracking",
        "descr": "Отслеживание цели в воздухе / по вертикали.",
        "game_specific": {
            "Aim Lab": ["Circletrack", "Circletrack Ultimate", "Straferun"],
            "KovaaK": ["Air Voltaic", "Air Voltaic Easy Invincible 4", "Air Voltaic Easy Invincible 4 80%",
                       "Air Voltaic Invincible 4", "Air Voltaic Invincible 7 Easy 80%",
                       "Air Angelic 4 Voltaic", "Air Angelic 4 Voltaic Easy", "Air Angelic 4 Voltaic Easy 80% (Good Version)",
                       "Air CELESTIAL", "Air CELESTIAL No UFO Easy", "Air CELESTIAL No UFO Easy Slowed",
                       "Air Pure", "Air Pure Intermediate", "Air Pure Intermediate Slower No UFO"],
            "Aimbeast": ["Air Track", "Sky Target", "Float Track"],
            "3D Aim Trainer": ["Vertical Track", "Air Target", "Flight Track"],
            "Furry Aim Trainer": ["Furry Fly", "Air Paw"],
        },
    },
    "tracking_reactive_groundplaza": {
        "skill": "tracking_reactive",
        "name": "Ground Plaza / Reactive Tracking",
        "descr": "Реактивное сопровождение с резкими сменами направления.",
        "game_specific": {
            "Aim Lab": ["Straferun", "Strafetrack"],
            "KovaaK": ["Ground Plaza Sparky v3", "Ground Plaza Sparky v3 Thin",
                       "Controlsphere OW", "Controlsphere OW 150%", "Controlsphere OW Long Strafes 90%",
                       "Controlsphere rAim", "Controlsphere rAim Easy", "Controlsphere rAim Easy 90%",
                       "PGTI Voltaic", "PGTI Voltaic Easy", "PGTI Voltaic Easy 80%",
                       "Flicker Plaza", "Flicker Plaza rAim Easy", "Flicker Plaza rAim Easy Less Blinks",
                       "Polarized Hell Easy", "Polarized Hell 20% Slower", "Polarized Hell Easy 20% Slower",
                       "Polarized Hell Easy 40% Slower"],
            "Aimbeast": ["Reactive Track", "Hell Run", "Chaos Track"],
            "3D Aim Trainer": ["Reactive Tracking", "Strafing Target", "Zigzag Track"],
            "Furry Aim Trainer": ["Furry Run", "Reactive Paw"],
        },
    },
    "tracking_smoothbot": {
        "skill": "tracking_smoothness",
        "name": "Smoothbot / Smoothness",
        "descr": "Плавность ведения. Классика измерения smoothness.",
        "game_specific": {
            "Aim Lab": ["Smoothsphere", "Smoothsphere 90"],
            "KovaaK": ["Smoothbot Invincible Goated", "Smoothbot Invincible Goated 75%",
                       "SmoothBot Invincible Goated Smaller",
                       "Leaptrack Goated 60% Larger", "Leaptrack Goated 75% Slightly Larger",
                       "Leaptrack Goated 80%"],
            "Aimbeast": ["Smooth Beast", "Silk Track"],
            "3D Aim Trainer": ["Smooth Track", "Precision Track"],
            "Furry Aim Trainer": ["Furry Smooth", "Silk Paw"],
        },
    },
    # ─── TARGET SWITCHING ───────────────────────────────────────
    "switching_speed_vox": {
        "skill": "switching_speed",
        "name": "voxTargetSwitch / Speed Switching",
        "descr": "Быстрое переключение между несколькими целями.",
        "game_specific": {
            "Aim Lab": ["Switchtrack", "Switchtrack Speed", "Multitarget"],
            "KovaaK": ["voxTargetSwitch 2", "voxTargetSwitch 2 Large", "voxTargetSwitch 2 20% Smaller",
                       "1w3ts Reload", "1w3ts Reload Larger", "1w2ts Reload",
                       "BeanTS", "BeanTS Larger", "BeanTS 30% Smaller",
                       "FloatTS Angelic", "FloatTS Angelic Easy", "FloatTS Angelic Easy Larger",
                       "WaldoTS", "WaldoTS Novice", "WaldoTS Intermediate",
                       "devTS Goated NR Static 5Bot", "devTS Goated NR Static Small 5Bot"],
            "Aimbeast": ["Switch Frenzy", "Multi Target", "Rapid Switch"],
            "3D Aim Trainer": ["Target Switch", "Multi Flick", "Speed Switch"],
            "Furry Aim Trainer": ["Paw Switch", "Furry Flick"],
        },
    },
    "switching_stability_domi": {
        "skill": "switching_stability",
        "name": "domiSwitch / Stability Switching",
        "descr": "Контролируемое переключение с акцентом на стабильность.",
        "game_specific": {
            "Aim Lab": ["Circuitswitch", "Circuitswitch Stability"],
            "KovaaK": ["domiSwitch", "domiSwitch Easy", "domiSwitch Easy Slower",
                       "tamTargetSwitch Smooth", "tamTargetSwitch Smooth Easy",
                       "VT Controlsphere", "VT Controlsphere Intermediate S5 80%",
                       "VT Controlsphere Novice S5 Hard", "VT Controlsphere Intermediate Hard"],
            "Aimbeast": ["Stable Switch", "Control Flick"],
            "3D Aim Trainer": ["Stability Switch", "Controlled Switch"],
            "Furry Aim Trainer": ["Stable Paw", "Furry Control"],
        },
    },
    # ─── REACTION ───────────────────────────────────────────────
    "reaction": {
        "skill": "reaction",
        "name": "Reaction Time",
        "descr": "Скорость реакции на появление цели.",
        "game_specific": {
            "Aim Lab": ["Reactionshot", "Reactionshot Ultimate", "Reaction Test"],
            "KovaaK": ["VT Bounceshot", "VT Bounceshot Intermediate", "VT Bounceshot Advanced"],
            "Aimbeast": ["Reaction King", "Quick Reflex"],
            "3D Aim Trainer": ["Reaction Test", "Reflex Shot"],
            "Furry Aim Trainer": ["Furry Reflex", "Quick Paw"],
        },
    },
}

# Обратный индекс: (trainer, сценарий) -> skill_key
_FLAT = {}
for skill_key, entry in SCENARIO_MAP.items():
    for trainer, scenarios in entry.get("game_specific", {}).items():
        for sc in scenarios:
            key = (trainer.lower(), sc.lower())
            _FLAT[key] = (skill_key, entry)


def resolve(trainer: str, scenario: str) -> dict:
    """По тренажёру и сценарию возвращает skill_id + категорию + описание."""
    key = (trainer.lower(), scenario.lower())
    if key in _FLAT:
        skill_key, entry = _FLAT[key]
        cat = SKILL_CATEGORIES.get(entry["skill"], {})
        return {
            "skill_key": skill_key,
            "skill_name": entry["name"],
            "skill_descr": entry["descr"],
            "category_name": cat.get("name", ""),
            "category_emoji": cat.get("emoji", ""),
        }
    # fuzzy fallback: ищем частичное совпадение
    for (t, s), (sk, e) in _FLAT.items():
        if t == key[0] and (s in scenario.lower() or scenario.lower() in s):
            cat = SKILL_CATEGORIES.get(e["skill"], {})
            return {
                "skill_key": sk,
                "skill_name": e["name"],
                "skill_descr": e["descr"],
                "category_name": cat.get("name", ""),
                "category_emoji": cat.get("emoji", ""),
            }
    return {
        "skill_key": "unknown",
        "skill_name": "Unknown",
        "skill_descr": "",
        "category_name": "",
        "category_emoji": "❓",
    }


def all_for_trainer(trainer: str) -> dict:
    """Возвращает все сценарии для данного тренажёра."""
    trainer_lower = trainer.lower()
    result = {}
    for skill_key, entry in SCENARIO_MAP.items():
        scenarios = entry.get("game_specific", {}).get(trainer, [])
        if scenarios:
            cat = SKILL_CATEGORIES.get(entry["skill"], {})
            result[skill_key] = {
                "skill_name": entry["name"],
                "category_name": cat.get("name", ""),
                "category_emoji": cat.get("emoji", ""),
                "scenarios": scenarios,
            }
    return result


def same_skill(skill_key: str) -> list:
    """Возвращает все варианты одного скилла во всех тренажёрах."""
    entry = SCENARIO_MAP.get(skill_key)
    if not entry:
        return []
    result = []
    for trainer, scenarios in entry.get("game_specific", {}).items():
        for sc in scenarios:
            result.append({"trainer": trainer, "scenario": sc})
    return result
