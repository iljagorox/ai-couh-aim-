# -*- coding: utf-8 -*-
import os

GAME_KNOWLEDGE = {
    "Auto Detect": {"aliases": [], "summary": "Определи игру по сцене", "focus": "Советуй по аиму"},
    "Aim Lab": {"aliases": ["aim lab", "aimlab"], "summary": "Тренажер аима", "focus": "Плавность, клики"},
    "KovaaK": {"aliases": ["kovaak"], "summary": "Тренажер", "focus": "Темп, трекинг"},
    "CS2": {"aliases": ["cs2", "csgo"], "summary": "Тактический шутер", "focus": "Пре-аим, остановка"},
    "Valorant": {"aliases": ["valorant"], "summary": "Тактический шутер", "focus": "Head level, микро-коррекция"},
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
    return f"Профиль: {profile_name}. {info['summary']} Фокус: {info['focus']}"