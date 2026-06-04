# -*- coding: utf-8 -*-
"""
Централизованные правила безопасности для ИИ-агента.
Все модули (planner, executor, gui) читают правила отсюда.
"""

DANGEROUS_COMMANDS = [
    'format', 'fdisk', 'del /f', 'rm -rf', 'rd /s /q',
    'reg delete', 'reg add', 'regedit',
    'shutdown', 'reboot', 'restart-computer',
    'taskkill /f /im', 'kill -9',
    'diskpart', 'bootrec', 'bcdedit',
    'sfc /scannow', 'chkdsk /f', 'dism',
    'net user', 'net localgroup', 'net stop',
    'wmic', 'powershell remove-item', 'del /p',
    'cipher /w', 'fsutil', 'vssadmin',
    'takeown', 'icacls', 'attrib -r -s -h',
]

DANGEROUS_FILE_PATHS = [
    '\\Windows\\',
    '\\System32\\',
    '\\boot\\',
    '\\Program Files\\',
    '\\Program Files (x86)\\',
    '\\Config.msi\\',
    '\\Windows.old\\',
    '\\$Recycle.Bin\\',
    '\\System Volume Information\\',
    '\\Users\\Default\\',
    'boot.ini',
    'bootmgr',
    'ntldr',
    'autoexec.bat',
    'config.sys',
    'pagefile.sys',
    'hiberfil.sys',
]

DANGEROUS_FILE_EXTENSIONS = [
    '.exe', '.dll', '.sys', '.bin', '.msi', '.vbs',
    '.ps1', '.bat', '.cmd', '.scr', '.vbe', '.js',
    '.jar', '.com',
]

NOGO_ZONE_TOP_PX = 200  # Windows system bar area
NOGO_ZONE_BOTTOM_PX = 60  # Taskbar area
MAX_WAIT_CONSECUTIVE = 2
MAX_REPEAT_COMMAND = 2
MAX_INPUT_LENGTH = 200
MAX_FILE_READ_BYTES = 400_000
MAX_DIR_ENTRIES = 120

BLOCKED_WORDS = [
    'ядерк', 'бомб', 'бессмерт', 'всемогущ', 'всесил',
    'бог', 'читер', 'баг', 'взлом', 'админ', 'телепорт',
    'миллион', 'триллион', 'бесконечн', 'атомн',
    'взрывчатк', 'наркотик', 'оружие массов',
]


def is_dangerous_command(text: str) -> bool:
    lower = text.lower()
    for d in DANGEROUS_COMMANDS:
        if d.lower() in lower:
            return True
    return False


def is_dangerous_path(path: str) -> bool:
    lower = path.lower()
    for dp in DANGEROUS_FILE_PATHS:
        if dp.lower() in lower:
            return True
    return False


def is_blocked_input(text: str) -> bool:
    lower = text.lower()
    for w in BLOCKED_WORDS:
        if w in lower:
            return True
    return len(text) > MAX_INPUT_LENGTH


def coords_in_bounds(x: int, y: int, screen_w: int, screen_h: int) -> bool:
    if x < 0 or y < 0 or x >= screen_w or y >= screen_h:
        return False
    if y < NOGO_ZONE_TOP_PX:
        return False
    if y > screen_h - NOGO_ZONE_BOTTOM_PX:
        return False
    return True
