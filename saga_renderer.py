import re, random
from PIL import Image, ImageDraw

W, H = 1280, 720

_LAYER_ORDER = {"bg": 0, "far": 1, "mid": 2, "fg": 3, "overlay": 4}

class SceneRenderer:
    def __init__(self):
        self.w = W
        self.h = H

    def render(self, visual_text: str, out_w: int = W, out_h: int = H) -> Image.Image:
        img = Image.new("RGB", (out_w, out_h))
        draw = ImageDraw.Draw(img)
        layers = self._parse(visual_text)
        for layer_name in ["bg", "far", "mid", "fg", "overlay"]:
            items = layers.get(layer_name, [])
            for item in items:
                self._draw_item(draw, item, out_w, out_h)
        return img

    def _parse(self, text: str) -> dict:
        layers = {}
        current = None
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            low = line.lower()
            if low.startswith("bg:") or low.startswith("far:") or low.startswith("mid:") or low.startswith("fg:") or low.startswith("overlay:"):
                key = low.split(":")[0].strip()
                val = line[len(key) + 1:].strip()
                current = key
                if key == "bg":
                    layers["bg"] = self._parse_bg(val)
                elif key == "overlay":
                    layers["overlay"] = self._parse_overlay(val)
                else:
                    layers.setdefault(key, []).append(self._parse_object(key, val))
            elif current and current not in ("bg", "overlay"):
                obj = self._parse_object(current, line)
                if obj:
                    layers.setdefault(current, []).append(obj)
        return layers

    def _parse_bg(self, val: str) -> list:
        top = "#050a20"
        bottom = "#0a0a10"
        m = re.search(r"top=?(#?\w+)", val)
        if m:
            top = m.group(1)
        m = re.search(r"bottom=?(#?\w+)", val)
        if m:
            bottom = m.group(1)
        return [{"type": "bg", "top": top, "bottom": bottom}]

    def _parse_overlay(self, val: str) -> list:
        kind = "none"
        intensity = 0.0
        parts = val.split()
        if parts:
            kind = parts[0].lower()
            if len(parts) > 1:
                try:
                    intensity = float(parts[1])
                except ValueError:
                    pass
        return [{"type": "overlay", "kind": kind, "intensity": intensity}]

    def _parse_object(self, layer: str, val: str) -> dict:
        obj = {"type": "object", "color": "#888888", "x": 0.5, "size": 0.2, "layer": layer}
        m = re.search(r"color=?(#?\w+)", val)
        if m:
            obj["color"] = m.group(1)
        m = re.search(r"x=([\d.]+)", val)
        if m:
            obj["x"] = float(m.group(1))
        m = re.search(r"size=([\d.]+)", val)
        if m:
            obj["size"] = float(m.group(1))
        m = re.search(r"kind=(\w+)", val)
        if m:
            obj["kind"] = m.group(1)
        m = re.search(r'intensity=([\d.]+)', val)
        if m:
            obj["intensity"] = float(m.group(1))
        m = re.search(r'name="([^"]+)"', val)
        if m:
            obj["name"] = m.group(1)[:12]
        if "type" not in val.lower() and ("wall" in val.lower() or "brick" in val.lower() or "metal" in val.lower()):
            obj["type"] = "wall"
        if "type" not in val.lower() and ("entity" in val.lower() or "npc" in val.lower() or "merchant" in val.lower() or "guard" in val.lower()):
            obj["type"] = "entity"
        if "effect" in val.lower() or "neon" in val.lower() or "fire" in val.lower():
            obj["type"] = "effect"
        return obj

    def _hex(self, h: str):
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        try:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        except (ValueError, IndexError):
            return (136, 136, 136)

    def _draw_item(self, draw: ImageDraw, item: dict, out_w: int, out_h: int):
        t = item.get("type", "object")
        if t == "bg":
            top = self._hex(item.get("top", "#050a20"))
            bottom = self._hex(item.get("bottom", "#0a0a10"))
            for y in range(out_h):
                t = y / max(out_h - 1, 1)
                r = int(top[0] * (1 - t) + bottom[0] * t)
                g = int(top[1] * (1 - t) + bottom[1] * t)
                b = int(top[2] * (1 - t) + bottom[2] * t)
                draw.line([0, y, out_w, y], fill=(r, g, b))
            return
        if t == "overlay":
            kind = item.get("kind", "none")
            intensity = min(1.0, item.get("intensity", 0.3))
            if kind in ("rain", "drizzle"):
                density = 0.004 * intensity if kind == "rain" else 0.002 * intensity
                n = int(out_w * out_h * density)
                for _ in range(n):
                    rx = random.randint(0, out_w - 1)
                    ry = random.randint(0, out_h - 1)
                    draw.line([rx, ry, rx, ry + 4], fill=(100, 150, 200), width=1)
            elif kind == "fog":
                n = int(out_w * out_h * 0.003 * intensity)
                for _ in range(n):
                    fx = random.randint(0, out_w - 1)
                    fy = random.randint(0, out_h - 1)
                    fb = random.randint(40, 80)
                    draw.point((fx, fy), fill=(fb, fb + 10, fb + 20))
            elif kind == "dark":
                alpha = int(60 * intensity)
                draw.rectangle([0, 0, out_w, out_h], fill=(0, 0, 0, alpha))
            return
        x = item.get("x", 0.5)
        size = item.get("size", 0.2)
        color = self._hex(item.get("color", "#888888"))
        block_w = max(8, int(out_w * size))
        block_h = max(6, int(out_h * size * 1.5))
        cx = int(x * out_w)
        left = max(0, cx - block_w // 2)
        right = min(out_w, left + block_w)
        layer = item.get("layer", "mid")
        if layer == "far":
            top = out_h // 3
        elif layer == "fg":
            top = out_h // 2
        else:
            top = out_h // 4
        top = max(0, top)
        bottom = min(out_h, top + block_h)
        draw.rectangle([left, top, right, bottom], fill=color)
        name = item.get("name", "")
        if name:
            draw.text((left + 2, top), name, fill=(255, 255, 255))
