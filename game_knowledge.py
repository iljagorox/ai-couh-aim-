# -*- coding: utf-8 -*-

GAME_KNOWLEDGE = {
    "Auto Detect": {
        "aliases": [],
        "summary": "определи игру или тренажер по кадру",
        "focus": "смотри на прицел, цель, движение и промахи",
    },
    "Aim Lab": {
        "aliases": ["aim lab", "aimlab", "gridshot", "spidershot", "microshot"],
        "summary": "тренажер аима с короткими сценариями",
        "focus": "плавность, путь к цели, клик по центру, лишние движения",
    },
    "KovaaK": {
        "aliases": ["kovaak", "kovaaks", "kovaak's"],
        "summary": "тренажер трекинга, фликов и target switching",
        "focus": "темп, трекинг, контроль ускорения, возврат в центр",
    },
    "CS2": {
        "aliases": ["cs2", "counter-strike", "csgo", "counter strike"],
        "summary": "тактический шутер с низким TTK",
        "focus": "pre-aim, уровень головы, counter-strafe, дисциплина углов",
    },
    "Valorant": {
        "aliases": ["valorant", "valo"],
        "summary": "тактический шутер с агентами и точной стрельбой",
        "focus": "head level, микро-коррекция, peeking, reset отдачи",
    },
    "Osu": {
        "aliases": ["osu", "osu!", "mania", "taiko"],
        "summary": "ритм-игра на точность курсора и тайминг",
        "focus": "чтение паттерна, путь курсора, тайминг клика, стабильный ритм",
    },
    "Overwatch": {
        "aliases": ["overwatch", "ow", "ow2", "overwatch 2"],
        "summary": "геройский шутер с разными стилями аима",
        "focus": "tracking, flick, projectile lead, позиционирование",
    },
    "FragPunk": {
        "aliases": ["fragpunk", "frag punk"],
        "summary": "шутер с карточными механиками и быстрыми перестрелками",
        "focus": "flick, реакция, tracking, игра от углов",
    },
    "Marvel Rivals": {
        "aliases": ["marvel rivals", "marvel"],
        "summary": "геройский PvP-шутер с суперспособностями",
        "focus": "tracking, target switching, позиционирование, увороты",
    },
    "Deadlock": {
        "aliases": ["deadlock"],
        "summary": "шутер-стратегия с видом от третьего лица",
        "focus": "tracking, flick, прицеливание в движении, game sense",
    },
    "Payday 2": {
        "aliases": ["payday", "payday 2", "pd2"],
        "summary": "кооперативный шутер с врагами на разных дистанциях",
        "focus": "flick, headshot tracking, контроль отдачи, ситуационная стрельба",
    },
    "3D Aim Trainer": {
        "aliases": ["3d aim", "3d aim trainer", "3daim"],
        "summary": "3D-тренажер аима с разными режимами",
        "focus": "tracking в 3D-пространстве, flick, реакция",
    },
    "Aimbeast": {
        "aliases": ["aimbeast", "aim beast"],
        "summary": "тренажер аима с кастомными сценариями и картами",
        "focus": "smoothness, flick, target switching, custom паттерны",
    },
    "Furry Aim Trainer": {
        "aliases": ["furry aim", "furry aim trainer"],
        "summary": "аим тренажер с аниме-стилистикой",
        "focus": "tracking, flick, реакция, сценарии на скорость",
    },
}


def infer_game_profile(task_text, screen_desc, selected_profile="Auto Detect"):
    if selected_profile != "Auto Detect":
        return selected_profile
    haystack = f"{task_text} {screen_desc}".lower()
    for profile, info in GAME_KNOWLEDGE.items():
        for alias in info.get("aliases", []):
            if alias in haystack:
                return profile
    return "Auto Detect"


def profile_context(profile_name):
    info = GAME_KNOWLEDGE.get(profile_name, GAME_KNOWLEDGE["Auto Detect"])
    return f"Профиль: {profile_name}. {info['summary']}. Фокус: {info['focus']}."
