# -*- coding: utf-8 -*-
import random
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

TILE_WALL = 0
TILE_FLOOR = 1
TILE_WATER = 2
TILE_GRASS = 3
TILE_DOOR = 4
TILE_VOID = 5
TILE_ROAD = 6
TILE_WINDOW = 7

TILE_CHARS = {
    TILE_WALL: '█',
    TILE_FLOOR: '·',
    TILE_WATER: '≈',
    TILE_GRASS: '"',
    TILE_DOOR: '+',
    TILE_VOID: ' ',
    TILE_ROAD: '░',
    TILE_WINDOW: '▓',
}

TILE_COLORS = {
    TILE_WALL: ('#667788', '#1a1a2e'),
    TILE_FLOOR: ('#445566', '#16213e'),
    TILE_WATER: ('#00aaff', '#003366'),
    TILE_GRASS: ('#44aa55', '#113322'),
    TILE_DOOR: ('#ddaa44', '#443311'),
    TILE_VOID: ('#000000', '#000000'),
    TILE_ROAD: ('#555555', '#222222'),
    TILE_WINDOW: ('#aaddff', '#223344'),
}

TILE_SOLID = {TILE_WALL, TILE_VOID}

ENTITY_COLORS = {
    'player': '#00ff88', 'human': '#58a6ff', 'enemy': '#ff0044', 'beast': '#ff6600',
    'ghost': '#8844ee', 'droid': '#aaddff', 'merchant': '#ffaa00', 'guard': '#ff4444',
    'animal': '#66cc55', 'robot': '#88aacc', 'drone': '#00ccff', 'turret': '#ff2200',
}

SPRITE_DB = {}

def _reg(kind, mood, lines):
    SPRITE_DB.setdefault(kind, {})[mood] = lines

# === HUMAN ===
_reg('human', 'neutral', [
    '  █████  █████  ', ' ██░ ░██ ██░ ░██ ', ' ██░ ░██ ██░ ░██ ',
    ' ███████████████', ' ██░░█░░█░░██', '   ██   ██   ',
    '  ██     ██  ', ' ████   ████ ',
])
_reg('human', 'happy', [
    '  █████████████  ', ' ██░ ░██ ██░ ░██ ', ' ██░ ░██ ██░ ░██ ',
    ' ███████████████', ' ██░░█░░█░░██', '   ██   ██   ',
    '  ██     ██  ', ' ████   ████ ',
])
_reg('human', 'angry', [
    '  █████████████  ', ' ██▼ ▼██ ██▼ ▼██ ', ' ██▼ ▼██ ██▼ ▼██ ',
    ' ███████████████', ' ██░░█░░█░░██', '   ██   ██   ',
    '  ██ ▄▄ ██  ', ' ████▀▀████ ',
])
_reg('human', 'combat', [
    '  █████████████  ', ' ██✖ ✖██ ██✖ ✖██ ', ' ██✖ ✖██ ██✖ ✖██ ',
    ' ███████████████', ' ██░░█░░█░░██', '  ███ ▄ ███  ',
    '  ██     ██  ', ' ████   ████ ',
])

# === GUARD ===
_reg('guard', 'neutral', [
    ' ▄████████████▄ ', ' ██▄ ▄██ ██▄ ▄██ ', ' ██▄ ▄██ ██▄ ▄██ ',
    ' ███████████████', '  ██████████  ', '  ██░░░░░██  ',
    ' ███     ███ ', '██ ██   ██ ██',
])
_reg('guard', 'combat', [
    ' ▄████████████▄ ', ' ██✖ ✖██ ██✖ ✖██ ', ' ██✖ ✖██ ██✖ ✖██ ',
    ' ███████████████', '  ██████████  ', ' ███░░░░░███ ',
    '███       ███', '██ ██   ██ ██',
])

# === ENEMY ===
_reg('enemy', 'neutral', [
    '  █████████████  ', ' ██░ ░██ ██░ ░██ ', ' ██░ ░██ ██░ ░██ ',
    ' ███████████████', ' ██░░░█░░░██', '   ██▄ ▄██   ',
    '  █████████  ', ' ███     ███ ',
])
_reg('enemy', 'angry', [
    '  █████████████  ', ' ██▼▼▼██ ██▼▼▼██ ', ' ██▼▼▼██ ██▼▼▼██ ',
    ' ███████████████', ' ██░░░█░░░██', '   ██▄ ▄██   ',
    '  █████████  ', ' ███     ███ ',
])
_reg('enemy', 'combat', [
    '  █████████████  ', ' ██✖✖✖██ ██✖✖✖██ ', ' ██✖✖✖██ ██✖✖✖██ ',
    ' ███████████████', '   ███████   ', '  ██▄▄▄▄▄██  ',
    ' ██       ██', '██         ██',
])

# === MERCHANT ===
_reg('merchant', 'neutral', [
    '  ▄████████▄  ', ' ██░ ░██ ██░ ░██ ', ' ██░ ░██ ██░ ░██ ',
    ' ███████████████', '  ██░█░█░██  ', '  ██ ▀▀▀ ██  ',
    ' █████████████', '██ ▄▄▄▄▄▄▄ ██',
])
_reg('merchant', 'happy', [
    '  ▄████████▄  ', ' ██^ ^██ ██^ ^██ ', ' ██^ ^██ ██^ ^██ ',
    ' ███████████████', '  ██░█░█░██  ', '  ██ ▀▀▀ ██  ',
    ' █████████████', '██ ▄▄▄▄▄▄▄ ██',
])

# === DRONE ===
_reg('drone', 'neutral', [
    '   ▄▄▄▄▄▄▄   ', ' ▄███████████▄ ', ' ███████████████ ',
    ' ██▀▀▀▀▀▀▀██', '  ██▄▄▄▄▄██  ', ' ██  ███  ██ ',
    '█       █', '█       █',
])
_reg('drone', 'combat', [
    '   ▄▄▄▄▄▄▄   ', ' ▄███████████▄ ', ' ███████████████ ',
    ' ██✖✖✖✖✖██', '  ██▄▄▄▄▄██  ', ' ██  ███  ██ ',
    '█  █   █  █', '█ █     █ █',
])

# === BEAST ===
_reg('beast', 'neutral', [
    '   ▄▄▄▄▄▄▄   ', '  █████████  ', ' ██░ ░██ ██░ ░██ ',
    ' ███████████████', '  █████████  ', ' ██ ▄▄▄ ██ ',
    '██  █ █  ██', ' █       █ ',
])
_reg('beast', 'combat', [
    '   ▄▄▄▄▄▄▄   ', '  █████████  ', ' ██▼ ▼██ ██▼ ▼██ ',
    ' ███████████████', '  █████████  ', ' ██▄▄▄▄▄██ ',
    '██  █ █  ██', ' █       █ ',
])

# === GHOST ===
_reg('ghost', 'neutral', [
    '    █████    ', '   ██░ ░██   ', '   ██░ ░██   ',
    '  █████████  ', '  █████████  ', '  ██ ▄▄▄ ██  ',
    ' ██ █   █ ██', '██ █     █ ██',
])
_reg('ghost', 'combat', [
    '   ▄█████▄   ', '  ██✖ ✖██  ', '  ██✖ ✖██  ',
    ' ███████████ ', ' ███████████ ', ' ██▄▄▄▄▄██ ',
    '██ █     █ ██', '█  █     █  █',
])

# === DROID (robot) ===
_reg('droid', 'neutral', [
    '  ▄██████▄  ', ' ████  ████ ', ' ██▀▀  ▀▀██ ',
    ' ██████████ ', '  ██ ▄▄ ██  ', '  ██ ▀▀ ██  ',
    ' ██      ██', '██  ████  ██',
])

# === TURRET ===
_reg('turret', 'combat', [
    '   ▄▄▄▄▄▄▄   ', '  █████████  ', '  ██✖✖✖██  ',
    ' ███████████ ', ' ███████████ ', ' ██ ▄▄▄ ██ ',
    '████     ████', ' ██       ██ ',
])

# === WOLF ===
_reg('wolf', 'neutral', [
    '   ▄▄▄▄▄▄▄   ', '  █████████  ', ' ██░ ░██ ██░ ░██ ',
    ' ███████████████', '  █████████  ', '   ██▄▄▄██   ',
    '  ██     ██  ', ' █  █   █  █ ',
])
_reg('wolf', 'angry', [
    '   ▄▄▄▄▄▄▄   ', '  █████████  ', ' ██▼ ▼██ ██▼ ▼██ ',
    ' ███████████████', '  █████████  ', '  ███▄▄▄███  ',
    ' ██       ██', '█   █   █   █',
])
_reg('wolf', 'attack', [
    '  ▄▄▄▄▄▄▄▄▄  ', ' █████████████ ', ' ██✖✖██ ██✖✖██ ',
    ' ███████████████', '  ███████████  ', '  ██▄▄▄▄▄██  ',
    ' ██       ██', '█   █   █   █',
])

# === BEAR ===
_reg('bear', 'neutral', [
    '  ▄▄▄▄▄▄▄▄▄  ', ' █████████████ ', ' ██░ ░██ ██░ ░██ ',
    ' █████████████████', '  ███████████  ', '   ██▄▄▄██   ',
    '  █████████  ', ' █         █ ',
])
_reg('bear', 'angry', [
    '  ▄▄▄▄▄▄▄▄▄  ', ' █████████████ ', ' ██▼ ▼██ ██▼ ▼██ ',
    ' █████████████████', '  ███████████  ', '  ███▄▄▄███  ',
    ' ██       ██', '██  █   █  ██',
])
_reg('bear', 'attack', [
    ' ▄▄▄▄▄▄▄▄▄▄▄ ', ' ███████████████ ', ' ██✖✖██ ██✖✖██ ',
    ' ██████████████████', '  █████████████  ', '   ███▄▄▄███   ',
    ' ██▄▄▄▄▄▄▄██', '██ █     █ ██',
])

# === ZOMBIE ===
_reg('zombie', 'neutral', [
    '  ▄████████▄  ', ' ██░ ░██ ██░ ░██ ', ' ██░ ░██ ██░ ░██ ',
    ' ███████████████', ' ██░░░░░██░░░░░██', '  ██▄▄▄▄▄██  ',
    ' █████████████', '██  █████  ██',
])
_reg('zombie', 'angry', [
    '  ▄████████▄  ', ' ██▼▼▼██ ██▼▼▼██ ', ' ██▼▼▼██ ██▼▼▼██ ',
    ' ███████████████', ' ███████████████', '  █████████  ',
    ' ██▄▄▄▄▄▄▄██', '██         ██',
])
_reg('zombie', 'attack', [
    '  ▄████████▄  ', ' ██✖✖✖██ ██✖✖✖██ ', ' ██✖✖✖██ ██✖✖✖██ ',
    ' ████████████████', ' ██░░░███░░░██', '  █████████  ',
    ' ███     ███', '██  █████  ██',
])

# === SPIDER ===
_reg('spider', 'neutral', [
    '   █   █   ', '  ███ ███  ', ' ███████████ ',
    '  █████████  ', '  ██░ ░██  ', ' ███████████ ',
    '█ █  ███  █ █', ' █  █████  █ ',
])
_reg('spider', 'angry', [
    '   █   █   ', '  ███ ███  ', ' ███████████ ',
    '  █████████  ', '  ██▼▼▼██  ', ' ███████████ ',
    '█ █ █████ █ █', ' █  █████  █ ',
])
_reg('spider', 'attack', [
    '   █   █   ', '  ███████  ', ' ███████████ ',
    ' ████████████', '  ██✖✖✖██  ', ' ███████████ ',
    '█ █ █████ █ █', ' █ █     █ █ ',
])

# === GHOST (creature) ===
_reg('ghost_creature', 'neutral', [
    '    █████    ', '   ██░ ░██   ', '   ██░ ░██   ',
    '  █████████  ', '  █████████  ', '  ████▄████  ',
    ' ███     ███', '██  █████  ██',
])
_reg('ghost_creature', 'attack', [
    '   ▄█████▄   ', '  ██✖ ✖██  ', '  ██✖ ✖██  ',
    ' ███████████ ', ' ███████████ ', ' ███▄▄▄▄▄███ ',
    '███     ███', '█   █████   █',
])

# === RAT ===
_reg('rat', 'neutral', [
    '   ▄▄▄▄▄   ', '  ███████  ', ' ██░ ░██ ██░ ░██ ',
    ' █████████████', '  ██▄▄▄██  ',
    ' ██     ██', '█  █████  █',
])
_reg('rat', 'attack', [
    '   ▄▄▄▄▄   ', '  ███████  ', ' ██▼▼▼██ ██▼▼▼██ ',
    ' █████████████', '  ███▄▄▄███  ',
    ' ██     ██', '██ █   █ ██',
])

def _build_sprite_from_db(kind: str, mood: str, color: str) -> Tuple[List[str], List[str]]:
    lines = SPRITE_DB.get(kind, {}).get(mood)
    if not lines:
        lines = SPRITE_DB.get(kind, {}).get('neutral', [])
    if not lines:
        for k in SPRITE_DB:
            if mood in SPRITE_DB[k]:
                lines = SPRITE_DB[k][mood]
                break
    if not lines:
        lines = SPRITE_DB.get('human', {}).get('neutral', [' @ '])
    return lines

SPRITE_CHAR_MAP = {
    '█': '#5588bb', '▓': '#6699cc', '▒': '#77aadd', '░': '#88bbee',
    '▄': '#446699', '▀': '#5588bb', '▬': '#6699cc',
    '╱': '#88ccff', '╲': '#88ccff', '║': '#6699cc',
    '▼': '#ff4444', '✖': '#ff0000', '^': '#ffdd44',
    '●': '#ffaa00', '○': '#ffcc44', '◉': '#ff8800',
    ':': '#88aacc', '.': '#99bbdd', ',': '#aaccee',
    '@': '#00ff88', 'P': '#58a6ff', 'E': '#ff0044',
    'B': '#ff6600', 'G': '#8844ee', 'D': '#aaddff',
    'M': '#ffaa00', 'R': '#88aacc', 'd': '#00ccff',
    'T': '#ff2200',
}

SPRITE_WALK = {
    'human': [
        ['  █████  █████  ', ' ██░ ░██ ██░ ░██ ', ' ██░ ░██ ██░ ░██ ', ' ███████████████', ' ██░░█░░█░░██', '  ██ ██ ██  ', ' ████ ████ '],
        [' █████ ██████  ', ' ██░ ░██ ██░ ░██ ', ' ██░ ░██ ██░ ░██ ', ' ███████████████', ' ██░░█░░█░░█░', '  ██ ██ ███ ', ' ████ █████ '],
    ],
    'enemy': [
        ['  █████  █████  ', ' ███░███ ███░███ ', ' ███████████████', '  ██░██░██░██ ', '  ███████████ ', '   ██   ██   ', '  ████ ████  '],
        [' █████  █████  ', ' ███░███ ███░███ ', ' ███████████████', ' ██░██░██░██  ', ' ███████████  ', '  ██   ██   ', ' ████ ████  '],
    ],
    'wolf': [
        ['   ▄▄▄▄▄▄▄   ', '  █████████  ', ' ██░ ░██ ██░ ░██ ', ' ███████████████', '  █████████  ', '   ██▄▄▄██   ', '  ██     ██  '],
        ['   ▄▄▄▄▄▄▄   ', '  █████████  ', ' ██░ ░██ ██░ ░██ ', ' ███████████████', '  █████████  ', '   ██ ███   ', ' ██     ██  '],
    ],
    'bear': [
        ['  ▄▄▄▄▄▄▄▄▄  ', ' █████████████ ', ' ██░ ░██ ██░ ░██ ', ' █████████████████', '  ███████████  ', '   ██▄▄▄██   ', '  █████████  '],
        ['  ▄▄▄▄▄▄▄▄▄  ', ' █████████████ ', ' ██░ ░██ ██░ ░██ ', ' █████████████████', '  ███████████  ', '  ███ ███   ', ' █████████  '],
    ],
    'zombie': [
        ['  ▄████████▄  ', ' ██░ ░██ ██░ ░██ ', ' ██░ ░██ ██░ ░██ ', ' ███████████████', ' ██░░░░░██░░░░░██', '  ██▄▄▄▄▄██  ', ' █████████████'],
        ['  ▄████████▄  ', ' ██░ ░██ ██░ ░██ ', ' ██░ ░██ ██░ ░██ ', ' ███████████████', ' ██░░░░░██░░░░░██', '  ██▄▄▄▄▄██  ', '   █████████ '],
    ],
    'spider': [
        ['   █   █   ', '  ███ ███  ', ' ███████████ ', '  █████████  ', '  ██░ ░██  ', ' ███████████ ', '█ █  ███  █ █'],
        ['   █   █   ', '  ███ ███  ', ' ███████████ ', '  █████████  ', '  ██░ ░██  ', ' ███████████ ', '█ █  ███  █ █'],
    ],
    'ghost_creature': [
        ['    █████    ', '   ██░ ░██   ', '   ██░ ░██   ', '  █████████  ', '  █████████  ', '  ████▄████  ', ' ███     ███'],
        ['    █████    ', '   ██░ ░██   ', '   ██░ ░██   ', '  █████████  ', '  █████████  ', '  █████████  ', '███     ███'],
    ],
    'rat': [
        ['   ▄▄▄▄▄   ', '  ███████  ', ' ██░ ░██ ██░ ░██ ', ' █████████████', '  ██▄▄▄██  ', ' ██     ██'],
        ['   ▄▄▄▄▄   ', '  ███████  ', ' ██░ ░██ ██░ ░██ ', ' █████████████', '  ███████  ', '██     ██'],
    ],
}

SPRITE_CLOSE = {}

def _reg_close(kind, mood, lines):
    SPRITE_CLOSE.setdefault(kind, {})[mood] = lines

_reg_close('human', 'neutral', [
    '     ▄█████████████▄     ',
    '    ██░ ░██ ██░ ░███    ',
    '   ██░ ░██ ██░ ░██ ██   ',
    '   ███████████████████   ',
    '   ██░░░░░█░░█░░░░░██   ',
    '   ██░░░░░█░░█░░░░░██   ',
    '   ██░░░░░█░░█░░░░░██   ',
    '   ███████████████████   ',
    '     ███████████████     ',
    '    ████  █████  ████    ',
    '   ███  ███████  ███   ',
    '   ██  █████████  ██   ',
    '   ██ ███████████ ██   ',
    '   ██ ███████████ ██   ',
    '    ███████████████    ',
    '    ████       ████    ',
    '   █████       █████   ',
    '   ██████     ██████   ',
    '  ████████   ████████  ',
    '  █████████ █████████  ',
    ' █████████████████████ ',
    ' █████████████████████ ',
    '██   █████████████   ██',
    '██  ███████████████  ██',
])
_reg_close('human', 'happy', [
    '     ▄█████████████▄     ',
    '    ██^ ^██ ██^ ^███    ',
    '   ██^ ^██ ██^ ^██ ██   ',
    '   ███████████████████   ',
    '   ██░░░░░█░░█░░░░░██   ',
    '   ██░░░░░█░░█░░░░░██   ',
    '   ██░░░░░█░░█░░░░░██   ',
    '   ███████████████████   ',
    '     ███████████████     ',
    '    ████████████████    ',
    '   █████  ███  █████   ',
    '   ████         ████   ',
    '   ███           ███   ',
    '   ███  ███████  ███   ',
    '    ██ █████████ ██    ',
    '    ██ █████████ ██    ',
    '   ██   █████   ██   ',
    '   ██  ███████  ██   ',
    '  ██  █████████  ██  ',
    '  ██ ███████████ ██  ',
    ' ██  █████████  ██ ',
    ' ██ ███████████ ██ ',
    '██  █████████  ██',
    '██ ███████████ ██',
])
_reg_close('human', 'angry', [
    '     ▄█████████████▄     ',
    '    ██▼▼▼██ ██▼▼▼███    ',
    '   ██▼▼▼██ ██▼▼▼██ ██   ',
    '   ███████████████████   ',
    '   ███████████████████   ',
    '   ████░░░█░░█░░░████   ',
    '   ████░░░█░░█░░░████   ',
    '   ███████████████████   ',
    '     ███████████████     ',
    '    ████████████████    ',
    '   █████         █████   ',
    '   ████  █████  ████   ',
    '   ███  ███████  ███   ',
    '   ██  █████████  ██   ',
    '   ██ ███████████ ██   ',
    '   ██ ███████████ ██   ',
    '   ██ ███     ███ ██   ',
    '    ██ ██     ██ ██    ',
    '   ██  ██     ██  ██   ',
    '  ███  ██     ██  ███  ',
    '  █████       ██████  ',
    ' █████████████████████ ',
    '██                   ██',
    '██                   ██',
])
_reg_close('human', 'scared', [
    '     ▄█████████████▄     ',
    '    ██O O██ ██O O███    ',
    '   ██O O██ ██O O██ ██   ',
    '   ███████████████████   ',
    '   ██░░░░░█░░█░░░░░██   ',
    '   ██░░░░░█░░█░░░░░██   ',
    '   ██░░░░░█░░█░░░░░██   ',
    '   ███████████████████   ',
    '     ███████████████     ',
    '    ████  █████  ████    ',
    '   ███  ███████  ███   ',
    '   ██  █████████  ██   ',
    '   ██ ███     ███ ██   ',
    '   ██ ██  ███  ██ ██   ',
    '   ██     ███     ██   ',
    '    ██   █████   ██    ',
    '   ██   ███████   ██   ',
    '   █████       █████   ',
    '  █████  █████ █████  ',
    '  ████   █████  ████  ',
    ' █████  █████  █████ ',
    ' █████ ███████ █████ ',
    '██  ███████████  ██',
    '██  ███████████  ██',
])

_reg_close('enemy', 'neutral', [
    '    ▄██████████████▄    ',
    '   ███░ ░██ ███░ ░███   ',
    '  ███░ ░██ ███░ ░██ ██  ',
    '  ████████████████████  ',
    '  █████░░░█░░█░░░████  ',
    '  █████░░░█░░█░░░████  ',
    '  ███░░░░░░░░░░░░░███  ',
    '  ████████████████████  ',
    '    ████████████████    ',
    '   ████  █████  ████   ',
    '   ███  ███████  ███   ',
    '   ██  █████████  ██   ',
    '   ██ ███████████ ██   ',
    '   ██ ████   ████ ██   ',
    '   ██ ███  █  ███ ██   ',
    '    ██ ██     ██ ██    ',
    '   ██  ██     ██  ██   ',
    '  ██   ██     ██   ██  ',
    '  ██  ███     ███  ██  ',
    ' ██   ████   ████  ██ ',
    ' ████████████████████ ',
    ' ████████████████████ ',
    '██  ███████████████  ██',
    '██  ███████████████  ██',
])
_reg_close('enemy', 'angry', [
    '    ▄██████████████▄    ',
    '   ███▼▼▼██ ███▼▼▼███   ',
    '  ███▼▼▼██ ███▼▼▼██ ██  ',
    '  ████████████████████  ',
    '  █████░░░█░░█░░░████  ',
    '  █████░░░█░░█░░░████  ',
    '  ███░░░░░░░░░░░░░███  ',
    '  ████████████████████  ',
    '    ████████████████    ',
    '   █████████████████   ',
    '  ████  █████████  ████  ',
    '  ███  ███████████  ███  ',
    '  ██  █████████████  ██  ',
    '  ██ ███████████████ ██  ',
    '  ██ ███████████████ ██  ',
    '  ██ ████     ████ ██  ',
    '   ██ ██       ██ ██   ',
    '  ██  ██       ██  ██  ',
    '  ██  ██       ██  ██  ',
    ' ███  ██       ██  ███ ',
    ' ██████       ███████ ',
    '██████████████████████',
    '██                   ██',
    '██                   ██',
])

_reg_close('wolf', 'neutral', [
    '     ▄▄▄▄▄▄▄▄▄▄▄▄▄     ',
    '    █████████████████    ',
    '   ████░ ░███ ████░ ░██   ',
    '   ████░ ░███ ████░ ░██   ',
    '   ████████████████████   ',
    '   ████████████████████   ',
    '    ██░░░░░░░░░░░░░██    ',
    '    █████████████████    ',
    '      █████████████      ',
    '     ████  █████  ████     ',
    '    ███   ███████   ███    ',
    '   ███   █████████   ███   ',
    '   ██   ███████████   ██   ',
    '   ██  █████████████  ██   ',
    '   ██  █████████████  ██   ',
    '   ██  █████   █████  ██   ',
    '    ██ ████     ████ ██    ',
    '    ██ ████     ████ ██    ',
    '   ██  ███       ███  ██   ',
    '   ██  ██         ██  ██   ',
    '  ███ ███         ███ ███  ',
    '  ███████         ███████  ',
    ' ██   ██           ██   ██ ',
    ' ██   ██           ██   ██ ',
])
_reg_close('wolf', 'angry', [
    '     ▄▄▄▄▄▄▄▄▄▄▄▄▄     ',
    '    █████████████████    ',
    '   ████▼▼▼███ ████▼▼▼██   ',
    '   ████▼▼▼███ ████▼▼▼██   ',
    '   ████████████████████   ',
    '   ████████████████████   ',
    '    ██░░░░░░░░░░░░░██    ',
    '   ███████████████████   ',
    '     █████████████████     ',
    '    ███████████████████    ',
    '   █████  ███████  █████   ',
    '   ████  █████████  ████   ',
    '   ███  ███████████  ███   ',
    '   ██  █████████████  ██   ',
    '   █████████████████████   ',
    '   █████████████████████   ',
    '   ████████     ████████   ',
    '    ██████       ██████    ',
    '   ██████       ███████   ',
    '   █████         █████   ',
    '  █████           █████  ',
    '  ██████         ██████  ',
    ' ██  ████       ████  ██ ',
    ' ██   ██         ██   ██ ',
])

_reg_close('zombie', 'neutral', [
    '   ▄████████████████▄   ',
    '  ████░ ░███ ████░ ░███  ',
    ' ████░ ░███ ████░ ░██ ██ ',
    ' ████████████████████████ ',
    ' ██████░░░░░░░░░░░██████ ',
    ' ██████░░░░░░░░░░░██████ ',
    '  █████░░░░░░░░░░░█████  ',
    '  █████████████████████  ',
    '    █████████████████    ',
    '   █████  █████  █████   ',
    '   ████  ███████  ████   ',
    '   ███  █████████  ███   ',
    '   ██  ███████████  ██   ',
    '   ██  ███████████  ██   ',
    '   ███ ████   ████ ███   ',
    '    ██ ███     ███ ██    ',
    '   ██  ██       ██  ██   ',
    '   ██  ██       ██  ██   ',
    '   ██ ███       ███ ██   ',
    '   █████         █████   ',
    '  █████           █████  ',
    '  █████████████████████  ',
    '  █████████████████████  ',
    '██  █████████████████  ██',
])

_reg_close('bear', 'neutral', [
    '   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄   ',
    '  █████████████████████  ',
    ' █████░ ░████ █████░ ░███ ',
    ' █████░ ░████ █████░ ░███ ',
    ' █████████████████████████ ',
    ' █████████████████████████ ',
    '  ██░░░░░░░░░░░░░░░░░██  ',
    '  █████████████████████  ',
    '    █████████████████    ',
    '   ████  █████████  ████   ',
    '   ███  ███████████  ███   ',
    '   ██  █████████████  ██   ',
    '   ██  █████████████  ██   ',
    '   ██ ███████████████ ██   ',
    '   ██ ███████████████ ██   ',
    '   ██ ███████████████ ██   ',
    '   █████████████████████   ',
    '   █████████████████████   ',
    '   █████████████████████   ',
    '  ██████         ██████  ',
    '  █████           █████  ',
    ' ██████           ███████ ',
    '██   ██           ██   ██',
    '██   ██           ██   ██',
])

_reg_close('spider', 'neutral', [
    '  █        █        █  ',
    ' ███      ███      ███ ',
    ' █████   █████   █████ ',
    ' ███████████████████████ ',
    '  █████████████████████  ',
    '   ███████████████████   ',
    '    ██░░░░░░░░░░░░░██    ',
    '   ███████████████████   ',
    '   ████░ ░███ ████░ ░██   ',
    '   ████░ ░███ ████░ ░██   ',
    '   ████████████████████   ',
    '   ████████████████████   ',
    '    █████████████████    ',
    '    ████   █████████    ',
    '   ████    ███████████   ',
    '  █████    ████████████  ',
    '  ██████   ████████████  ',
    ' ███████   █████████████ ',
    ' █████████ █████████████ ',
    '██  █████████████████  ██',
    '██  █████████████████  ██',
    ' ██ █████       █████ ██ ',
    '   ██ ██         ██ ██   ',
    '   ██ ██         ██ ██   ',
])

_reg_close('ghost_creature', 'neutral', [
    '     ▄██████████████▄     ',
    '    █████░ ░██ █████    ',
    '   █████░ ░██ ███████   ',
    '   █████░ ░██ ███████   ',
    '   ███████████████████   ',
    '   ███████████████████   ',
    '    ███░░░░░░░░░░░███    ',
    '    █████████████████    ',
    '      █████████████      ',
    '     ███████████████     ',
    '    █████████████████    ',
    '   ███████████████████   ',
    '   ███████████████████   ',
    '   ███████████████████   ',
    '   ███████████████████   ',
    '   ███████████████████   ',
    '   ███████████████████   ',
    '   ███████████████████   ',
    '   █████  ███████████   ',
    '   ███████████████████   ',
    '   ███████████████████   ',
    '    █████████████████    ',
    '    ████  █████  ████    ',
    '   █████  █████  █████   ',
])

_reg_close('rat', 'neutral', [
    '   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄   ',
    '  ███████████████████  ',
    ' ███░ ░██ ███░ ░██ ███ ',
    ' ███░ ░██ ███░ ░██ ███ ',
    ' █████████████████████ ',
    ' █████████████████████ ',
    '  ██░░░░░░░░░░░░░░░██  ',
    '  ███████████████████  ',
    '   █████████████████   ',
    '   █████████████████   ',
    '    ██  ███████  ██    ',
    '    ██  ███████  ██    ',
    '   ██  █████████  ██   ',
    '   ██  █████████  ██   ',
    '   ███ █████████ ███   ',
    '   █████████████████   ',
    '  ██████       ██████  ',
    '  █████         █████  ',
    '  ████           ████  ',
    ' █████           █████ ',
    ' █████           █████ ',
    ' █████           █████ ',
    '██  ██           ██  ██',
    '██  ██           ██  ██',
])

SPRITE_ATTACK = {
    'human': [
        ['  ▄▄██████▄▄  ', ' ██✖ ░██ ██✖ ░██ ', ' ██✖ ░██ ██✖ ░██ ', ' ███████████████', '  ██░░█░░█░░██ ', '  ████ █ ████  ', ' █████   █████ '],
        ['  ▄▄██████▄▄  ', ' ██✖ ░██ ██✖ ░██ ', ' ██✖ ░██ ██✖ ░██ ', ' ███████████████', '  ██░░█░░█░░██ ', ' █████ █ █████ ', '███       ███'],
    ],
    'enemy': [
        ['  ▄▄██████▄▄  ', ' ██✖✖██ ██✖✖██ ', ' ██✖✖██ ██✖✖██ ', ' ███████████████', '  ███████████  ', ' ███  █  ███ ', '██   █   ██'],
        ['  ▄▄██████▄▄  ', ' ██✖✖██ ██✖✖██ ', ' ██✖✖██ ██✖✖██ ', ' ███████████████', '  ███████████  ', '███  █  ███', '██       ██'],
    ],
    'guard': [
        [' ▄████████████▄ ', ' ██✖✖██ ██✖✖██ ', ' ██✖✖██ ██✖✖██ ', ' ███████████████', '  ██████████  ', '  ██▄▄▄▄▄██  ', '███     ███'],
        [' ▄████████████▄ ', ' ██✖✖██ ██✖✖██ ', ' ██✖✖██ ██✖✖██ ', ' ███████████████', '  ██████████  ', ' ███▄▄▄▄▄███ ', '██       ██'],
    ],
    'wolf': [
        ['  ▄▄▄▄▄▄▄▄▄  ', ' █████████████ ', ' ██✖✖██ ██✖✖██ ', ' ███████████████', '  ███████████  ', '  ██▄▄▄▄▄██  ', ' ██       ██'],
        ['  ▄▄▄▄▄▄▄▄▄  ', ' █████████████ ', ' ██✖✖██ ██✖✖██ ', ' ███████████████', '  ███████████  ', ' ██▄▄▄▄▄██ ', '██       ██'],
    ],
    'bear': [
        [' ▄▄▄▄▄▄▄▄▄▄▄ ', ' ███████████████ ', ' ██✖✖██ ██✖✖██ ', ' ██████████████████', '  █████████████  ', '   ██▄▄▄███   ', '██▄▄▄▄▄▄▄██'],
        [' ▄▄▄▄▄▄▄▄▄▄▄ ', ' ███████████████ ', ' ██✖✖██ ██✖✖██ ', ' ██████████████████', '  █████████████  ', '  ██▄▄▄▄▄██  ', '██▄▄▄▄▄▄▄██'],
    ],
    'zombie': [
        ['  ▄████████▄  ', ' ██✖✖✖██ ██✖✖✖██ ', ' ██✖✖✖██ ██✖✖✖██ ', ' ████████████████', ' ██░░░███░░░██', '  █████████  ', ' ███     ███'],
        ['  ▄████████▄  ', ' ██✖✖✖██ ██✖✖✖██ ', ' ██✖✖✖██ ██✖✖✖██ ', ' ████████████████', ' ██░░░███░░░██', ' ████████████', '██  █████  ██'],
    ],
    'spider': [
        ['   █   █   ', '  ███████  ', ' ███████████ ', ' ████████████', '  ██✖✖✖██  ', ' ███████████ ', '█ █ █████ █ █'],
        ['   █   █   ', '  ███████  ', ' ███████████ ', ' ████████████', '  ██✖✖✖██  ', ' ███████████ ', '█ █     █ █'],
    ],
    'ghost_creature': [
        ['   ▄█████▄   ', '  ██✖ ✖██  ', '  ██✖ ✖██  ', ' ███████████ ', ' ███████████ ', ' ███▄▄▄▄▄███ ', '███     ███'],
        ['   ▄█████▄   ', '  ██✖ ✖██  ', '  ██✖ ✖██  ', ' ███████████ ', ' ███████████ ', ' ███████████ ', '███     ███'],
    ],
    'rat': [
        ['   ▄▄▄▄▄   ', '  ███████  ', ' ██▼▼▼██ ██▼▼▼██ ', ' █████████████', '  ███▄▄▄███  ', ' ██     ██'],
        ['   ▄▄▄▄▄   ', '  ███████  ', ' ██▼▼▼██ ██▼▼▼██ ', ' █████████████', '  █████████  ', '██     ██'],
    ],
}

@dataclass
class Entity:
    eid: int
    name: str
    kind: str
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    speed: float = 2.0
    hp: int = 100
    max_hp: int = 100
    size: int = 1
    faction: str = 'neutral'
    ascii_char: str = '?'
    color: str = '#ffffff'
    destination: Optional[Tuple[float, float]] = None
    dest_speed: float = 0.0
    ai_state: str = 'idle'
    ai_target: Optional[int] = None
    patrol_points: List[Tuple[float, float]] = field(default_factory=list)
    patrol_idx: int = 0
    alive: bool = True
    mood: str = 'neutral'
    move_frame: int = 0
    last_x: float = 0.0
    last_y: float = 0.0
    thoughts: str = ''
    title: str = ''
    state: str = 'idle'
    state_timer: float = 0.0
    emotion: str = 'neutral'
    emotion_timer: float = 0.0
    target_eid: Optional[int] = None
    attack_cooldown: float = 0.0
    attack_range: float = 1.5
    attack_damage: float = 12.0
    death_timer: float = 0.0
    level: int = 1
    traits: List[str] = field(default_factory=list)
    genre: str = 'rpg'
    xp_reward: int = 10
    strength: int = 5
    agility: int = 5
    perception: int = 5
    intelligence: int = 5
    charisma: int = 5
    aggression: int = 5
    fear: int = 5
    loyalty: int = 5

    def __post_init__(self):
        if not self.color or self.color == '#ffffff':
            self.color = ENTITY_COLORS.get(self.kind, '#ffffff')
        self.last_x, self.last_y = self.x, self.y
        self.attack_damage = 8 + self.strength * 2 + self.level
        self.attack_range = 1.0 + self.agility * 0.05
        self.speed = 1.0 + self.agility * 0.08

    def is_moving(self) -> bool:
        return abs(self.vx) > 0.05 or abs(self.vy) > 0.05 or self.destination is not None

    def set_emotion(self, emotion: str, duration: float = 3.0):
        self.emotion = emotion
        self.emotion_timer = duration

    def set_state(self, state: str, duration: float = 0.0):
        self.state = state
        self.state_timer = duration

    def dodge_chance(self) -> float:
        return min(0.5, self.agility * 0.04)

    def crit_chance(self) -> float:
        return min(0.3, self.agility * 0.025)

    def view_range(self, daylight: float, weather: str) -> float:
        base = 10.0 + self.perception * 1.5
        if daylight < 0.3:
            base *= 0.3
        elif daylight < 0.5:
            base *= 0.6
        if weather in ('fog',):
            base *= 0.4
        elif weather in ('rain', 'drizzle'):
            base *= 0.7
        return max(3.0, base)

    def xp_mult(self) -> float:
        return 1.0 + self.intelligence * 0.05

    def persuasion_difficulty(self) -> float:
        return max(0.1, self.loyalty * 0.1 - self.fear * 0.05)

    def sprite_lines(self) -> List[str]:
        if self.state == 'attack' and self.kind in SPRITE_ATTACK:
            idx = (self.move_frame // 4) % len(SPRITE_ATTACK[self.kind])
            return SPRITE_ATTACK[self.kind][idx]
        if self.is_moving() and self.kind in SPRITE_WALK:
            walk = SPRITE_WALK[self.kind]
            idx = (self.move_frame // 4) % len(walk)
            if idx < len(walk) and walk[idx]:
                return walk[idx]
        mood = self.emotion if self.emotion in SPRITE_DB.get(self.kind, {}) else 'neutral'
        base = _build_sprite_from_db(self.kind, mood, self.color)
        return base

    def sprite_lines_close(self) -> List[str]:
        mood = self.emotion if self.emotion in SPRITE_CLOSE.get(self.kind, {}) else 'neutral'
        close = SPRITE_CLOSE.get(self.kind, {}).get(mood)
        if close:
            return close
        return self.sprite_lines()

    def sprite_frame(self, height: int, frame: int, accent: str = '') -> List[List[Tuple[str, str]]]:
        if height > 10:
            lines = self.sprite_lines_close()
            if not lines:
                lines = self.sprite_lines()
        else:
            lines = self.sprite_lines()
        if not lines:
            return [[(self.ascii_char or '@', self.color)]]
        max_w = max(len(l) for l in lines)
        num_lines = len(lines)
        if height <= 3:
            idx = int((frame // 6) % num_lines)
            line = lines[idx] if idx < len(lines) else lines[0]
            center = len(line) // 2
            ch = line[center] if center < len(line) else '@'
            col = SPRITE_CHAR_MAP.get(ch, self.color)
            return [[(ch, col)]]
        if height <= 6:
            mid = num_lines // 2
            lines = [lines[0], lines[mid]] if height <= 4 else [lines[0], lines[mid], lines[-1]]
            num_lines = len(lines)
        result_rows = []
        for i in range(height):
            src_idx = int((i / height) * num_lines)
            src_idx = min(src_idx, num_lines - 1)
            src_line = lines[src_idx] if src_idx < len(lines) else lines[-1]
            if not src_line:
                src_line = ' @ '
            row = []
            for ci in range(len(src_line)):
                ch = src_line[ci]
                fallback = accent or self.color
                col = SPRITE_CHAR_MAP.get(ch, fallback)
                if ch == ' ':
                    col = '#000000'
                row.append((ch, col))
            result_rows.append(row)
        return result_rows


@dataclass
class WorldObject:
    x: float
    y: float
    kind: str
    char: str
    color: str
    block_move: bool = True
    description: str = ''
    hp: int = 1


WEATHERS = ['clear', 'rain', 'fog', 'drizzle', 'overcast']

class SagaWorld:
    def __init__(self, width: int = 200, height: int = 150, seed: int = 0):
        self.width = width
        self.height = height
        self.grid: List[List[int]] = [[TILE_VOID for _ in range(width)] for _ in range(height)]
        self.entities: Dict[int, Entity] = {}
        self.objects: List[WorldObject] = []
        self._next_eid = 1
        self.player_eid: Optional[int] = None
        self.tick_time = 0.0
        self.daylight = 1.0
        self.seed = seed or random.randint(100000, 999999)
        self.weather = 'clear'
        self.day_speed = 0.001
        self.weather_timer = 0.0

    def update_cycle(self, dt: float):
        self.tick_time += dt
        self.daylight = 0.5 + 0.5 * math.sin(self.tick_time * self.day_speed)
        if self.daylight < 0.15:
            self.daylight = 0.15
        self.weather_timer += dt
        if self.weather_timer > random.uniform(30, 90):
            self.weather = random.choice(WEATHERS)
            self.weather_timer = 0.0

    def new_eid(self) -> int:
        eid = self._next_eid
        self._next_eid += 1
        return eid

    def add_entity(self, entity: Entity):
        self.entities[entity.eid] = entity

    def remove_entity(self, eid: int):
        self.entities.pop(eid, None)

    def get_player(self) -> Optional[Entity]:
        if self.player_eid:
            return self.entities.get(self.player_eid)
        return None

    def is_solid(self, x: float, y: float) -> bool:
        tx, ty = int(x), int(y)
        if tx < 0 or ty < 0 or tx >= self.width or ty >= self.height:
            return True
        if self.grid[ty][tx] in TILE_SOLID:
            return True
        for obj in self.objects:
            if obj.block_move and int(obj.x) == tx and int(obj.y) == ty:
                return True
        return False

    def find_nearest_entity(self, x: float, y: float, kinds: set, max_dist: float = 50) -> Optional[Entity]:
        best, best_dist = None, max_dist
        for e in self.entities.values():
            if not e.alive:
                continue
            if e.kind not in kinds:
                continue
            d = math.hypot(e.x - x, e.y - y)
            if d < best_dist:
                best_dist = d
                best = e
        return best

    def generate_dungeon(self, seed: int = 0):
        if seed:
            random.seed(seed)
        for y in range(self.height):
            for x in range(self.width):
                if x == 0 or y == 0 or x == self.width - 1 or y == self.height - 1:
                    self.grid[y][x] = TILE_WALL
                else:
                    self.grid[y][x] = TILE_WALL if random.random() < 0.45 else TILE_FLOOR
        for _ in range(5):
            self._smooth_map()
        rooms = self._carve_rooms(8)
        self._connect_rooms(rooms)
        return rooms

    def _smooth_map(self):
        new = [row[:] for row in self.grid]
        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                walls = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                            if self.grid[y + dy][x + dx] == TILE_WALL)
                new[y][x] = TILE_WALL if walls >= 5 else TILE_FLOOR
        self.grid = new

    def _carve_rooms(self, count: int) -> List[Tuple[int, int, int, int]]:
        rooms = []
        for _ in range(count * 3):
            rw, rh = random.randint(4, 10), random.randint(4, 8)
            rx = random.randint(2, self.width - rw - 2)
            ry = random.randint(2, self.height - rh - 2)
            overlap = any(
                rx < rx2 + 2 and rx + rw + 2 > rx2 and ry < ry2 + 2 and ry + rh + 2 > ry2
                for (rx2, ry2, rw2, rh2) in rooms
            )
            if not overlap:
                rooms.append((rx, ry, rw, rh))
                for dy in range(rh):
                    for dx in range(rw):
                        self.grid[ry + dy][rx + dx] = TILE_FLOOR
        return rooms

    def _connect_rooms(self, rooms: List[Tuple[int, int, int, int]]):
        for i in range(len(rooms) - 1):
            x1, y1 = rooms[i][0] + rooms[i][2] // 2, rooms[i][1] + rooms[i][3] // 2
            x2, y2 = rooms[i + 1][0] + rooms[i + 1][2] // 2, rooms[i + 1][1] + rooms[i + 1][3] // 2
            for x in range(min(x1, x2), max(x1, x2) + 1):
                if 0 < y1 < self.height - 1:
                    self.grid[y1][x] = TILE_FLOOR
                    if y1 > 0 and self.grid[y1 - 1][x] == TILE_WALL:
                        self.grid[y1 - 1][x] = TILE_WALL
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if 0 < x2 < self.width - 1:
                    self.grid[y][x2] = TILE_FLOOR
                    if x2 > 0 and self.grid[y][x2 - 1] == TILE_WALL:
                        self.grid[y][x2 - 1] = TILE_WALL

    def generate_city(self, seed: int = 0):
        if seed:
            random.seed(seed)
        for y in range(self.height):
            for x in range(self.width):
                if x == 0 or y == 0 or x == self.width - 1 or y == self.height - 1:
                    self.grid[y][x] = TILE_WALL
                else:
                    self.grid[y][x] = TILE_ROAD if random.random() < 0.15 else TILE_FLOOR
        for _ in range(4):
            self._grow_blocks()
        for _ in range(6):
            self._carve_plaza()

    def _grow_blocks(self):
        new = [row[:] for row in self.grid]
        for y in range(2, self.height - 2):
            for x in range(2, self.width - 2):
                roads = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                            if self.grid[y + dy][x + dx] == TILE_ROAD)
                if roads >= 2:
                    new[y][x] = TILE_ROAD
                elif roads == 0 and self.grid[y][x] != TILE_WALL:
                    neighbors = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                                    if self.grid[y + dy][x + dx] != TILE_VOID)
                    if neighbors >= 3:
                        new[y][x] = TILE_WALL
        self.grid = new

    def _carve_plaza(self):
        for _ in range(3):
            px, py = random.randint(5, self.width - 10), random.randint(5, self.height - 10)
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    if 0 < py + dy < self.height - 1 and 0 < px + dx < self.width - 1:
                        self.grid[py + dy][px + dx] = TILE_FLOOR


class SagaPhysics:
    def __init__(self, world: SagaWorld):
        self.world = world
        self.attack_effects: List[dict] = []
        self.pending_xp: List[Tuple[int, int]] = []  # (player_eid, xp_amount)

    def tick(self, dt: float):
        world = self.world
        for eid, entity in list(world.entities.items()):
            if not entity.alive:
                entity.death_timer -= dt
                if entity.death_timer <= 0:
                    world.remove_entity(eid)
                continue
            entity.state_timer -= dt
            entity.emotion_timer -= dt
            if entity.emotion_timer <= 0:
                entity.emotion = 'neutral'
            entity.attack_cooldown -= dt
            self._process_ai(entity, dt)
            self._move_entity(entity, dt)
            entity.last_x, entity.last_y = entity.x, entity.y
            if entity.is_moving():
                entity.move_frame += 1

    def _process_ai(self, entity: Entity, dt: float):
        world = self.world
        if entity.ai_state == 'patrol' and entity.patrol_points:
            target = entity.patrol_points[entity.patrol_idx]
            dx, dy = target[0] - entity.x, target[1] - entity.y
            dist = math.hypot(dx, dy)
            if dist < 0.5:
                entity.patrol_idx = (entity.patrol_idx + 1) % len(entity.patrol_points)
                entity.destination = entity.patrol_points[entity.patrol_idx]
            else:
                entity.destination = target
            entity.set_state('walk')
        elif entity.ai_state == 'follow' and entity.ai_target is not None:
            target_ent = world.entities.get(entity.ai_target)
            if target_ent and target_ent.alive:
                entity.destination = (target_ent.x - 1.5, target_ent.y)
                entity.set_state('walk')
        elif entity.ai_state == 'attack' and entity.ai_target is not None:
            target_ent = world.entities.get(entity.ai_target)
            if target_ent and target_ent.alive:
                dx, dy = target_ent.x - entity.x, target_ent.y - entity.y
                dist = math.hypot(dx, dy)
                if dist < entity.attack_range:
                    if entity.attack_cooldown <= 0:
                        entity.set_state('attack', 0.4)
                        entity.set_emotion('angry', 2.0)
                        entity.attack_cooldown = max(0.5, 2.0 - entity.agility * 0.08)
                        dmg = entity.attack_damage
                        if random.random() < target_ent.dodge_chance():
                            dmg = 0
                            entity.set_emotion('surprised', 1.0)
                            self.attack_effects.append({
                                'x': target_ent.x, 'y': target_ent.y,
                                'timer': 0.3, 'max_timer': 0.3,
                                'color': '#8888ff', 'ch': '°',
                            })
                        else:
                            if random.random() < entity.crit_chance():
                                dmg = int(dmg * 1.5)
                                target_ent.hp -= dmg
                                target_ent.set_emotion('scared', 2.0)
                                self.attack_effects.append({
                                    'x': target_ent.x, 'y': target_ent.y,
                                    'timer': 0.5, 'max_timer': 0.5,
                                    'color': '#ff8800', 'ch': '✦',
                                })
                            else:
                                target_ent.hp -= dmg
                                target_ent.set_emotion('scared', 1.5)
                                self.attack_effects.append({
                                    'x': target_ent.x, 'y': target_ent.y,
                                    'timer': 0.3, 'max_timer': 0.3,
                                    'color': '#ff4400', 'ch': '✖',
                                })
                        if target_ent.hp <= 0:
                            target_ent.alive = False
                            target_ent.death_timer = 1.5
                            target_ent.set_state('death', 1.5)
                            target_ent.set_emotion('sad', 2.0)
                            self.attack_effects.append({
                                'x': target_ent.x, 'y': target_ent.y,
                                'timer': 0.8, 'max_timer': 0.8,
                                'color': '#ff0000', 'ch': '✖',
                            })
                            self.pending_xp.append((entity.eid, target_ent.xp_reward))
                    entity.destination = None
                else:
                    entity.destination = (target_ent.x, target_ent.y)
                    entity.set_state('walk')
            else:
                entity.ai_state = 'idle'
                entity.destination = None
                entity.set_state('idle')
                entity.set_emotion('neutral')
        else:
            if entity.state == 'idle' and random.random() < 0.01:
                entity.set_emotion(random.choice(['neutral', 'happy', 'sad']), 4.0)
            entity.set_state('idle')

    def _move_entity(self, entity: Entity, dt: float):
        if entity.destination is None:
            entity.vx *= 0.85
            entity.vy *= 0.85
            if abs(entity.vx) < 0.01:
                entity.vx = 0.0
            if abs(entity.vy) < 0.01:
                entity.vy = 0.0
            entity.x += entity.vx * dt
            entity.y += entity.vy * dt
            return

        dx = entity.destination[0] - entity.x
        dy = entity.destination[1] - entity.y
        dist = math.hypot(dx, dy)
        if dist < 0.3:
            entity.x = entity.destination[0]
            entity.y = entity.destination[1]
            entity.vx = 0.0
            entity.vy = 0.0
            entity.destination = None
            return

        speed = entity.dest_speed if entity.dest_speed > 0 else entity.speed
        entity.vx = (dx / dist) * speed
        entity.vy = (dy / dist) * speed
        nx = entity.x + entity.vx * dt
        ny = entity.y + entity.vy * dt
        if not self.world.is_solid(nx, ny):
            entity.x = nx
            entity.y = ny
        elif not self.world.is_solid(nx, entity.y):
            entity.x = nx
        elif not self.world.is_solid(entity.x, ny):
            entity.y = ny


class Layer:
    def __init__(self, w: int, h: int, fill_char: str = ' '):
        self.chars = [[fill_char for _ in range(w)] for _ in range(h)]
        self.fg = [['#000000' for _ in range(w)] for _ in range(h)]
        self.bg = [['#000000' for _ in range(w)] for _ in range(h)]


class SagaRenderer:
    def __init__(self, world: SagaWorld):
        self.world = world
        self.view_w = 60
        self.view_h = 30

    def set_viewport(self, w: int, h: int):
        self.view_w = w
        self.view_h = h

    def get_viewport_center(self) -> Tuple[float, float]:
        player = self.world.get_player()
        if player:
            return player.x, player.y
        return self.world.width / 2, self.world.height / 2

    def render(self, cx: Optional[float] = None, cy: Optional[float] = None, zoom: float = 1.0) -> Layer:
        if cx is None or cy is None:
            cx, cy = self.get_viewport_center()
        vw, vh = self.view_w, self.view_h
        half_w, half_h = vw // 2, vh // 2
        tile_w = max(1, int(zoom))
        view_tiles_w = vw * tile_w
        view_tiles_h = vh * tile_h

        layer = Layer(vw, vh, ' ')

        start_x = int(cx) - view_tiles_w // 2
        start_y = int(cy) - view_tiles_h // 2

        for vy in range(vh):
            for vx in range(vw):
                wx = start_x + vx * tile_w
                wy = start_y + vy * tile_h
                if 0 <= wx < self.world.width and 0 <= wy < self.world.height:
                    tile = self.world.grid[wy][wx]
                    layer.chars[vy][vx] = TILE_CHARS.get(tile, '?')
                    fg, bg = TILE_COLORS.get(tile, ('#ffffff', '#000000'))
                    layer.fg[vy][vx] = fg
                    layer.bg[vy][vx] = bg

        for obj in self.world.objects:
            ox = int(obj.x) - start_x
            oy = int(obj.y) - start_y
            if 0 <= oy < vh and 0 <= ox < vw and tile_w == 1:
                layer.chars[oy][ox] = obj.char
                layer.fg[oy][ox] = obj.color

        for eid, entity in self.world.entities.items():
            if not entity.alive:
                continue
            ex = int(entity.x) - start_x
            ey = int(entity.y) - start_y
            if 0 <= ey < vh and 0 <= ex < vw and tile_w == 1:
                layer.chars[ey][ex] = entity.ascii_char
                layer.fg[ey][ex] = entity.color
                if entity.hp < entity.max_hp:
                    bar = '█' if entity.hp / entity.max_hp > 0.5 else '▓' if entity.hp / entity.max_hp > 0.25 else '▒'
                    if ex + 1 < vw:
                        layer.chars[ey][ex + 1] = bar
                        layer.fg[ey][ex + 1] = '#ff4444'
                if entity.faction == 'enemy' and ey + 1 < vh:
                    layer.bg[ey + 1][ex] = '#441111'

        day = self.world.daylight
        if day < 1.0:
            dark = int(40 * (1.0 - day))
            for vy in range(vh):
                for vx in range(vw):
                    dist_from_center = math.hypot(vx - vw // 2, vy - vh // 2) / (vw * 0.4)
                    shade = min(1.0, max(0.0, dist_from_center * 0.3 + 0.3 * (1.0 - day)))
                    if shade > 0.05:
                        r, g, b = int(layer.bg[vy][vx][1:3], 16), int(layer.bg[vy][vx][3:5], 16), int(layer.bg[vy][vx][5:7], 16)
                        r = max(0, r - int(40 * shade))
                        g = max(0, g - int(40 * shade))
                        b = max(0, b - int(40 * shade))
                        layer.bg[vy][vx] = f'#{r:02x}{g:02x}{b:02x}'

        return layer

    def render_scene(self, scene_chars: List[str], palette: Dict[str, str]) -> Layer:
        h = len(scene_chars)
        w = max(len(row) for row in scene_chars) if scene_chars else 0
        layer = Layer(w, h, ' ')
        for y, row in enumerate(scene_chars):
            for x, ch in enumerate(row):
                if x < len(row):
                    layer.chars[y][x] = ch
                    layer.fg[y][x] = palette.get(ch, palette.get('default', '#ffffff'))
                    layer.bg[y][x] = palette.get(f'bg_{ch}', '#000000')
        return layer


def generate_location_scene(world: SagaWorld, cx: float, cy: float, radius: int = 10) -> List[str]:
    scene = []
    for dy in range(-radius, radius + 1):
        line = ''
        for dx in range(-radius, radius + 1):
            wx, wy = int(cx + dx), int(cy + dy)
            if 0 <= wx < world.width and 0 <= wy < world.height:
                tile = world.grid[wy][wx]
                has_entity = any(
                    e.alive and int(e.x) == wx and int(e.y) == wy
                    for e in world.entities.values()
                )
                if has_entity:
                    line += '@'
                else:
                    line += TILE_CHARS.get(tile, ' ')
            else:
                line += ' '
        scene.append(line)
    return scene


PARTICLE_CHARS = ['·', '°', '✧', '✦', '~', '+', '*', '%']
WEATHER_CHARS = {'rain': '|', 'snow': '*', 'ash': ':'}


class FpsRenderer:
    def __init__(self, world: SagaWorld):
        self.world = world
        self.view_w = 80
        self.view_h = 40
        self.fov = 1.0472
        self.max_dist = 25.0
        self.player_angle = 0.0
        self.anim_frame = 0
        self.particles: List[dict] = []

    def set_viewport(self, w: int, h: int):
        self.view_w = w
        self.view_h = h

    def _get_tile(self, x: int, y: int) -> int:
        if 0 <= x < self.world.width and 0 <= y < self.world.height:
            return self.world.grid[y][x]
        return TILE_WALL

    def _cast_ray(self, ox: float, oy: float, angle: float) -> Tuple[float, int, int, float]:
        sin_a, cos_a = math.sin(angle), math.cos(angle)
        max_d = self.max_dist
        step = 0.05
        d = 0.0
        while d < max_d:
            d += step
            x, y = int(ox + cos_a * d), int(oy + sin_a * d)
            tile = self._get_tile(x, y)
            if tile in TILE_SOLID:
                corr = d * cos_a
                return d, tile, x, corr
        return max_d, TILE_VOID, 0, max_d

    def _find_entities_in_fov(self, ox: float, oy: float) -> List[Tuple[float, float, float, Entity]]:
        result = []
        for e in self.world.entities.values():
            if not e.alive:
                continue
            dx, dy = e.x - ox, e.y - oy
            dist = math.hypot(dx, dy)
            if dist < 0.5 or dist > self.max_dist:
                continue
            ang = math.atan2(dy, dx) - self.player_angle
            while ang > math.pi:
                ang -= 2 * math.pi
            while ang < -math.pi:
                ang += 2 * math.pi
            if abs(ang) < self.fov * 0.55:
                result.append((ang, dist, (dist * math.cos(ang)), e))
        result.sort(key=lambda r: r[2])
        return result

    def render(self, player_x: float, player_y: float, angle: float,
               weather: str = '', tick: float = 0.0, palette: dict = None,
               daylight: float = 0.5) -> Layer:
        if palette is None:
            palette = {'text': '#e6edf3', 'sub': '#8b949e', 'accent': '#ff1070',
                       'neon_cyan': '#00e5ff', 'danger': '#ff0044'}
        self.player_angle = angle
        self.anim_frame += 1
        vw, vh = self.view_w, self.view_h
        half_vw, half_vh = vw // 2, vh // 2
        layer = Layer(vw, vh)

        is_night = daylight < 0.35
        fog_factor = 1.0 if weather in ('clear', 'drizzle') else 0.6
        max_dist = self.max_dist * fog_factor
        head_bob = math.sin(tick * 6.0) * 1.5

        wall_colors = {
            TILE_WALL: '#667788', TILE_FLOOR: '#445566', TILE_DOOR: '#ddaa44',
            TILE_GRASS: '#44aa55', TILE_WATER: '#00aaff', TILE_ROAD: '#555555',
            TILE_WINDOW: '#aaddff',
        }
        depth_chars = ['█', '▓', '▒', '░', '·', ' ']

        for sx in range(vw):
            ray_angle = angle + (sx / vw - 0.5) * self.fov
            fish_corr = math.cos((sx / vw - 0.5) * self.fov)
            dist, tile_type, hit_x, hit_y = self._cast_ray(player_x, player_y, ray_angle)
            dist *= fish_corr
            if dist < 0.3:
                dist = 0.3
            proj_height = int(vh * 0.9 / max(dist, 0.3))
            proj_height = min(proj_height, vh - 2)
            wall_color = wall_colors.get(tile_type, '#888888')

            ceil_top = (vh - proj_height) // 2 - int(head_bob)
            ceil_bot = ceil_top + proj_height

            for sy in range(vh):
                if sy < ceil_top:
                    sky_bright = 1.0 - (ceil_top - sy) / max(ceil_top, 1)
                    if is_night:
                        sky_r, sky_g, sky_b = 2, 2, 15
                    elif daylight < 0.5:
                        sky_r, sky_g, sky_b = 15, 20, 45
                    else:
                        sky_r, sky_g, sky_b = 20, 60, 100
                    sky_r = int(sky_r * sky_bright)
                    sky_g = int(sky_g * sky_bright)
                    sky_b = int(sky_b * sky_bright)
                    layer.chars[sy][sx] = '·'
                    layer.fg[sy][sx] = f'#{sky_r:02x}{sky_g:02x}{sky_b:02x}'
                    layer.bg[sy][sx] = '#000000'
                    continue

                if sy >= ceil_bot:
                    if sy < vh - 4:
                        floor_dist = (sy - ceil_bot) / max(vh - ceil_bot, 1)
                        dark_floor = max(0.15, 1.0 - floor_dist * 0.8) * daylight
                        fr, fg, fb = 40, 45, 60
                        fr, fg, fb = int(fr * dark_floor), int(fg * dark_floor), int(fb * dark_floor)
                        checker = '░' if ((int(sx / 2) + int(sy / 2)) % 2) else ' '
                        layer.chars[sy][sx] = checker
                        layer.fg[sy][sx] = f'#{fr:02x}{fg:02x}{fb:02x}'
                        layer.bg[sy][sx] = '#000000'
                    else:
                        layer.chars[sy][sx] = ' '
                        layer.bg[sy][sx] = '#000000'
                    continue

                depth = sy - ceil_top
                shade_idx = min(len(depth_chars) - 1, int(depth / max(proj_height, 1) * len(depth_chars)))
                shade = depth_chars[shade_idx]
                dark = max(0.15, 1.0 - dist / max_dist)
                dark *= daylight
                if tile_type == TILE_WINDOW and is_night:
                    dark = 1.0
                    wall_color = '#ffcc44'
                dark = max(0.06, dark)
                r, g, b = int(wall_color[1:3], 16), int(wall_color[3:5], 16), int(wall_color[5:7], 16)
                r, g, b = int(r * dark), int(g * dark), int(b * dark)
                if dist < 1.5 and tile_type not in (TILE_WATER, TILE_GRASS):
                    shade = '█'
                    r, g, b = min(255, r + 40), min(255, g + 40), min(255, b + 40)
                layer.chars[sy][sx] = shade
                layer.fg[sy][sx] = f'#{r:02x}{g:02x}{b:02x}'
                layer.bg[sy][sx] = '#000000'

        entity_list = self._find_entities_in_fov(player_x, player_y)
        for ang, dist, depth, ent in entity_list[:6]:
            if dist < 0.5:
                continue
            screen_x = int((ang / self.fov + 0.5) * vw)
            fish_ent = math.cos(ang)
            dist_ent = dist * max(0.7, fish_ent) if fish_ent > 0 else dist
            ent_height = int(vh * 0.75 / max(dist_ent, 0.5))
            ent_height = min(ent_height, vh - 4)
            if screen_x < 0 or screen_x >= vw:
                continue
            ent_top = (vh - ent_height) // 2 - int(head_bob)
            sprite_grid = ent.sprite_frame(ent_height, self.anim_frame)
            sprite_h = len(sprite_grid)
            sprite_w = max(len(row) for row in sprite_grid) if sprite_grid else 1
            half_w = sprite_w // 2
            for sy in range(min(ent_height, sprite_h)):
                sy_abs = ent_top + sy
                if sy_abs < 0 or sy_abs >= vh:
                    continue
                row = sprite_grid[sy] if sy < len(sprite_grid) else sprite_grid[-1]
                for ci in range(min(len(row), vw - screen_x + half_w)):
                    sx_abs = screen_x - half_w + ci
                    if sx_abs < 0 or sx_abs >= vw:
                        continue
                    ch, col = row[ci]
                    if is_night:
                        try:
                            cr, cg, cb = int(col[1:3],16), int(col[3:5],16), int(col[5:7],16)
                            col = f'#{int(cr*0.5):02x}{int(cg*0.5):02x}{int(cb*0.5):02x}'
                        except Exception:
                            pass
                    if ch != ' ':
                        layer.chars[sy_abs][sx_abs] = ch
                        layer.fg[sy_abs][sx_abs] = col
                        if ent.faction == 'enemy':
                            layer.bg[sy_abs][sx_abs] = '#330000' if ent.state != 'death' else '#440000'
                        elif ent.faction == 'player':
                            layer.bg[sy_abs][sx_abs] = '#002200'

            emot_map = {'happy': '^_^', 'angry': '>_<', 'sad': 'u_u', 'scared': 'o_o', 'surprised': 'O_O', 'neutral': ''}
            emot_icon = emot_map.get(ent.emotion, '')
            if emot_icon and dist < 5.0:
                self._draw_entity_name(layer, screen_x - len(emot_icon)//2, ent_top - 1, emot_icon, '#ffcc00')
            elif dist < 4.0 and ent.title and ent.emotion == 'neutral':
                self._draw_entity_name(layer, screen_x - len(ent.title)//2, ent_top - 1, ent.title, ent.color if '#' in ent.color else '#ffffff')

            hp_bar = int(ent.hp / max(ent.max_hp, 1) * 6)
            if hp_bar > 0 and screen_x < vw - 7 and ent_top + sprite_h + 1 < vh:
                bar_y = ent_top + sprite_h + 1
                for bx in range(6):
                    sx_bar = screen_x - half_w + bx
                    if 0 <= sx_bar < vw and bar_y < vh:
                        layer.chars[bar_y][sx_bar] = '█' if bx < hp_bar else '░'
                        layer.fg[bar_y][sx_bar] = '#ff4444' if bx < hp_bar else '#333333'

            if ent.state == 'death' and not ent.alive:
                for sy in range(min(ent_height, 3)):
                    sy_abs = ent_top + sy + ent_height // 2
                    if 0 <= sy_abs < vh:
                        for ci in range(3):
                            sx_abs = screen_x - 1 + ci
                            if 0 <= sx_abs < vw:
                                layer.chars[sy_abs][sx_abs] = '✖'
                                layer.fg[sy_abs][sx_abs] = '#ff0000'

        self._update_particles(tick, palette, is_night, daylight)
        for p in self.particles[:]:
            px = int(half_vw + (p['x'] - player_x) * 2.0)
            py = int(half_vh + (p['y'] - player_y) * 2.0)
            if 0 <= py < vh and 0 <= px < vw:
                layer.chars[py][px] = p['ch']
                layer.fg[py][px] = p['color']

        if weather in ('rain', 'drizzle'):
            density = 0.008 if weather == 'rain' else 0.004
            rain_char = '/' if self.anim_frame % 12 < 6 else '|'
            for sy in range(vh):
                for sx in range(vw):
                    if random.random() < density:
                        layer.chars[sy][sx] = rain_char
                        layer.fg[sy][sx] = '#6699cc' if not is_night else '#446688'
                        layer.bg[sy][sx] = '#000022'
        elif weather == 'fog':
            for sy in range(vh):
                for sx in range(vw):
                    rv = random.random()
                    if rv < 0.003:
                        layer.chars[sy][sx] = '░'
                        layer.fg[sy][sx] = '#778899' if not is_night else '#334455'
                        layer.bg[sy][sx] = '#000000'

        return layer

    def _draw_entity_name(self, layer, sx: int, sy: int, name: str, color: str):
        for i, ch in enumerate(name[:12]):
            if sx + i >= layer.w:
                break
            if sy >= 0 and sy < layer.h:
                layer.chars[sy][sx + i] = ch
                layer.fg[sy][sx + i] = color
                layer.bg[sy][sx + i] = '#000000'

    def _update_particles(self, tick: float, palette: dict, is_night: bool = False, daylight: float = 0.5):
        spawn_rate = 0.15 if not is_night else 0.08
        if random.random() < spawn_rate:
            color = '#ffaa44'
            ch = random.choice(PARTICLE_CHARS)
            if is_night:
                color = random.choice(['#88ddff', '#aaffaa', '#ff88cc', '#88ffaa'])
                ch = random.choice(['✦', '·', '°', '✧', '~'])
            elif daylight < 0.5:
                color = random.choice(['#ffdd88', '#ff8844', '#ddaa44'])
            self.particles.append({
                'x': self.world.width * random.random(),
                'y': self.world.height * random.random(),
                'vx': random.uniform(-0.2, 0.2), 'vy': random.uniform(-0.1, -0.4),
                'life': random.uniform(1.0, 3.0), 'ch': ch,
                'color': color,
            })
        for p in self.particles[:]:
            p['x'] += p['vx'] * 0.1
            p['y'] += p['vy'] * 0.1
            p['life'] -= 0.05
            if p['life'] <= 0:
                self.particles.remove(p)


def build_world_from_json(data: dict) -> SagaWorld:
    w = data.get('width', 200)
    h = data.get('height', 150)
    world = SagaWorld(w, h)
    if 'grid' in data:
        for y in range(min(h, len(data['grid']))):
            for x in range(min(w, len(data['grid'][y]))):
                world.grid[y][x] = data['grid'][y][x]
    if 'daylight' in data:
        world.daylight = data['daylight']
    for ed in data.get('entities', []):
        ent = Entity(
            eid=world.new_eid(),
            name=ed.get('name', '?'),
            kind=ed.get('kind', 'human'),
            x=float(ed.get('x', 0)),
            y=float(ed.get('y', 0)),
            speed=float(ed.get('speed', 2.0)),
            hp=int(ed.get('hp', 100)),
            max_hp=int(ed.get('max_hp', 100)),
            faction=ed.get('faction', 'neutral'),
            ai_state=ed.get('ai_state', 'idle'),
            color=ed.get('color', ''),
            level=int(ed.get('level', 1)),
            traits=ed.get('traits', []),
            genre=ed.get('genre', 'rpg'),
            xp_reward=int(ed.get('xp_reward', 10)),
        )
        if ed.get('patrol_points'):
            ent.patrol_points = [(float(p['x']), float(p['y'])) for p in ed['patrol_points']]
        world.add_entity(ent)
    if 'player_eid' in data:
        world.player_eid = data['player_eid']
    return world
