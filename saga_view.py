# -*- coding: utf-8 -*-
from typing import List, Tuple

def _q(hex_color: str, step: int = 0x33) -> str:
    if len(hex_color) != 7:
        return '#000'
    try:
        r = (int(hex_color[1:3], 16) // step) * step
        g = (int(hex_color[3:5], 16) // step) * step
        b = (int(hex_color[5:7], 16) // step) * step
        return f'#{r:02x}{g:02x}{b:02x}'
    except Exception:
        return '#000'

def layer_to_groups(layer) -> List[tuple]:
    """Convert Layer -> [(text, tag, fg, bg), ...] where tag='q{fg}_{bg}'"""
    h = len(layer.chars)
    w = len(layer.chars[0]) if h else 0
    groups = []
    for y in range(h):
        x = 0
        while x < w:
            fg = _q(layer.fg[y][x])
            bg = _q(layer.bg[y][x])
            tag = f'q{fg}_{bg}'
            xe = x + 1
            while xe < w and _q(layer.fg[y][xe]) == fg and _q(layer.bg[y][xe]) == bg:
                xe += 1
            groups.append((''.join(layer.chars[y][x:xe]), tag, fg, bg))
            x = xe
        groups.append(('\n', '_nl', '', ''))
    return groups
