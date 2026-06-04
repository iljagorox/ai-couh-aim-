# -*- coding: utf-8 -*-
from __future__ import annotations
import json, os, threading, time, random, math, re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import ollama
from saga_world import SagaWorld, SagaPhysics, SagaRenderer, Entity, TILE_WALL, TILE_FLOOR
from saga_data import SAGA_SETTINGS, NPC_PROFILES, DEFAULT_CHOICES, MOOD_STYLE, SCENE_LABELS, ENGLISH_MARKERS

@dataclass
class SagaState:
    transcript: list = field(default_factory=list)
    turn: int = 0
    hp: int = 5
    max_hp: int = 5
    level: int = 1
    xp: int = 0
    next_level_xp: int = 100
    skill_points: int = 0
    stats: dict = field(default_factory=lambda: {
        'strength': 5, 'agility': 5, 'perception': 5,
        'intelligence': 5, 'charisma': 5,
    })
    inventory: list = field(default_factory=list)
    mood: str = "neutral"
    setting_key: str = "cyber"
    world_dir: str = ""
    active_npcs: list = field(default_factory=list)
    known_locations: list = field(default_factory=list)
    player_x: int = 0
    player_y: int = 0
    seed: int = 0

    def add_xp(self, amount: int):
        self.xp += amount
        while self.xp >= self.next_level_xp:
            self.xp -= self.next_level_xp
            self.level += 1
            self.skill_points += 3
            self.max_hp += 2
            self.hp = min(self.hp + 2, self.max_hp)
            self.next_level_xp = int(self.next_level_xp * 1.5)


def _scene_label(setting_key: str, narrative: str) -> str:
    labels = SCENE_LABELS.get(setting_key, SCENE_LABELS["cyber"])
    h = abs(hash(narrative)) % 10000
    selected = [labels[(h + i * 7) % len(labels)] for i in range(2 + (h % 2))]
    return f"\n[ {' / '.join(selected)} ]\n"


class WorldManager:
    def __init__(self):
        self.entities: dict[str, dict] = {}
        self.npcs: dict[str, dict] = {}
        self.locations: dict[str, dict] = {}
        self.witness_log: list[dict] = []
        self.world_map_data: dict = {}
        self.register_default_locations()

    def register_entity(self, entity_id: str, entity_type: str, name: str, details: dict) -> bool:
        if entity_id in self.entities:
            return False
        self.entities[entity_id] = {"type": entity_type, "name": name, "details": details}
        return True

    def register_npc(self, npc_id: str, name: str, initial_location: str, biography: str, appearance: str, initial_state: dict) -> bool:
        if npc_id in self.npcs:
            return False
        self.npcs[npc_id] = {
            "name": name,
            "location_id": initial_location,
            "biography": biography,
            "appearance": appearance,
            "state": initial_state,
            "is_alive": True,
            "last_seen": {"x": 0, "y": 0, "time": 0}
        }
        self.locations["" + npc_id + "_loc"] = {"coord": {"x": 0, "y": 0}, "owner": "person"}
        return True

    def register_location(self, loc_id: str, name: str, description: str, area_type: str, bounds: tuple = None, is_safe: bool = True, lore_data: dict = None):
        if loc_id in self.locations:
            return False
        loc_data = {
            "name": name,
            "description": description,
            "type": area_type,
            "bounds": bounds,
            "is_safe": is_safe,
            "lore": lore_data or {}
        }
        self.locations[loc_id] = loc_data
        return True

    def _get_location_description(self, location_id: str) -> str:
        location = self.locations.get(location_id)
        return f"[{location['name']}]: {location['description']} | Тип: {location['type']}"

    def get_active_location_description(self, location_id: str) -> str:
        location = self.locations.get(location_id)
        if not location:
            return "Неизвестное место. Стены давят, а вонь старого камня застилает глаза."
        if location['type'] == "MountainRange":
            return f"[Горы] В воздухе пахнет влажным камнем и смолой. Вы видите массивные граниты и туманное ущелье."
        elif location['type'] == "DeepForest":
            return f"[Лес] Густой подлесок и влажный мх глушат звук. Солнечный свет едва пробивается сквозь вековые кроны."
        elif location['type'] == "Urban":
            return f"[Город] Вы стоите на многослойной, грязной площади. Вокруг — неоновое сияние и грязь промышленных труб."
        else:
            return f"[{location['name']}] Здесь все должно быть, что и должно быть. Место пропитано энергией."

    def register_default_locations(self):
        grid = [
            ("cyber_streets", "Улицы Под-Неона", "Мокрый асфальт отражает вывески. Дрон прошёл низко, сканируя лица.", "Urban", ["дрон-рейдер", "уличный хакер", "бездомный пророк"], {"loot": "чип-схема", "noise": "высокий", "danger": 3}, 0, 0),
            ("cyber_bazaar", "Чёрный Базар", "Пахнет озоном и жареным жиром. Продавцы смотрят на твои карманы.", "Market", ["торговец органами", "информатор", "кибер-хирург"], {"loot": "имплант", "noise": "хаотичный", "danger": 2}, 0, -1),
            ("cyber_tower", "Башня Корпорации", "Стекло и сталь уходят в облака. Охранники смотрят сквозь тебя.", "Corporate", ["кибер-охранник", "топ-менеджер", "ИИ-секретарь"], {"loot": "ключ-карта", "noise": "низкий", "danger": 4}, 1, 0),
            ("cyber_subway", "Заброшенное Метро", "Поезда ходят, но не останавливаются. В темноте кто-то шепчет.", "Tunnel", ["крысиный мутант", "беглый киборг", "подземный торговец"], {"loot": "старый накопитель", "noise": "гулкий", "danger": 3}, -1, 1),
            ("cyber_club", "Нейрон-Клуб «Разряд»", "Бас пробивает грудь. Танцоры с открытыми портами.", "Nightlife", ["танцор с нейро-интерфейсом", "бармен-информатор", "охранник с дубиной"], {"loot": "записанный разговор", "noise": "оглушительный", "danger": 2}, 1, 1),
            ("cyber_roof", "Крыши Города", "Над смогом — тишина. Антенны ловят чужие сигналы.", "Roof", ["снайпер-наблюдатель", "курьер с дроном", "беспилотник"], {"loot": "оптический прицел", "noise": "ветер", "danger": 2}, 0, 2),
            ("cyber_junkyard", "Кладбище Дронов", "Горы мёртвого металла. Кое-что гудит, ищет сигнал.", "Wasteland", ["восставший дрон", "сборщик-одиночка", "дикий киборг"], {"loot": "рабочий сервопривод", "noise": "потрескивание", "danger": 3}, -2, 0),
            ("cyber_netcafe", "Нет-Кафе «Паутина»", "Экраны треснуты. Воздух сизый. Кто-то взламывает банк.", "Digital", ["нет-бегун", "администратор-шпион", "бот-консультант"], {"loot": "парольная флешка", "noise": "клавиатурный", "danger": 1}, -1, -1),
            ("fantasy_forest", "Пепельный Лес", "Деревья без коры — белые кости. Птицы слушают.", "Forest", ["лесной дух", "скелет-воин", "безумный друид"], {"loot": "говорящая руна", "noise": "шелест пепла", "danger": 3}, -4, -4),
            ("fantasy_castle", "Павший Замок", "Чёрный гранит помнит осаду. Трон пуст, но не холоден.", "Ruins", ["призрачный рыцарь", "пепельный червь", "беженка из деревни"], {"loot": "зачарованный клинок", "noise": "шёпот камня", "danger": 4}, -3, -4),
            ("fantasy_swamp", "Гнилая Топь", "Пузыри газа лопаются, выпуская сны утопленников.", "Swamp", ["болотный огонёк", "гигантский слизень", "отшельник-травник"], {"loot": "светящийся мох", "noise": "чавканье", "danger": 2}, -5, -3),
            ("fantasy_temple", "Храм Забытого Бога", "Колонны в темноте. Бог не умер — он спит.", "Temple", ["каменный голем", "жрица в трансе", "ловушка-иллюзия"], {"loot": "божественный артефакт", "noise": "органный гул", "danger": 5}, -4, -5),
            ("fantasy_village", "Опалённая Деревня", "Дома целы, жители смотрят сквозь тебя.", "Village", ["напуганный крестьянин", "проповедник конца", "зверь в хлеву"], {"loot": "припасы", "noise": "тишина", "danger": 1}, -3, -3),
            ("fantasy_mountain", "Хребет Великана", "Ветер валит с ног. В пещерах кто-то жрёт.", "Mountain", ["каменный великан", "горный козёл-мутант", "старик-отшельник"], {"loot": "драгоценный камень", "noise": "вой ветра", "danger": 4}, -5, -5),
            ("fantasy_crypt", "Склеп Королей", "Саркофаги открыты. На стенах — фрески, что движутся.", "Crypt", ["скелет-лорд", "нежить-слуга", "ловушка с ядом"], {"loot": "королевский перстень", "noise": "капель", "danger": 3}, -3, -5),
            ("space_bridge", "Капитанский Мостик", "Экраны горят алым. Кресло пусто, но ещё тёплое.", "Command", ["ИИ-фантом", "абордажник", "офицер связи"], {"loot": "бортовой журнал", "noise": "писки аварии", "danger": 3}, 5, 5),
            ("space_cargo", "Грузовой Отсек", "Контейнеры гудут. Что-то внутри хочет выйти.", "Storage", ["грузовая дверь-ловушка", "паразит в контейнере", "беглый пассажир"], {"loot": "ценный груз", "noise": "скрежет металла", "danger": 2}, 6, 5),
            ("space_engine", "Реакторный Зал", "Жар и радиация. Один шаг — корабль станет звездой.", "Engine", ["инженер-зомби", "плазменный сгусток", "техно-культист"], {"loot": "топливный стержень", "noise": "гул турбин", "danger": 5}, 7, 6),
            ("space_medbay", "Медицинский Отсек", "Автодоки мигают. На столах тела пристёгнуты.", "Medical", ["заражённый доктор", "подопытный №7", "мед-бот"], {"loot": "стимулятор", "noise": "писк кардиографа", "danger": 2}, 5, 7),
            ("space_airlock", "Шлюз №4", "Снаружи пустота. Внутри лужа замёрзшей крови.", "Airlock", ["вакуум-паразит", "труп в скафандре", "маяк SOS"], {"loot": "рабочий скафандр", "noise": "шипение воздуха", "danger": 3}, 6, 7),
            ("space_derelict", "Обломки «Надежды»", "Остов-призрак. Команды нет, но еда свежая.", "Derelict", ["крипто-зверь", "выживший-параноик", "авто-турель"], {"loot": "координаты аномалии", "noise": "помехи", "danger": 4}, 7, 5),
            ("horror_ward", "Палата №13", "Койки заправлены. На подушке мокрый след.", "Hospital", ["медсестра-призрак", "пациент без лица", "санитар-автомат"], {"loot": "история болезни", "noise": "капельница", "danger": 3}, -4, 4),
            ("horror_morgue", "Морг", "Холодно. Ячейки открыты. Дыши через раз.", "Morgue", ["оживший труп", "патологоанатом", "тень на стене"], {"loot": "ключ от архива", "noise": "капанье", "danger": 3}, -5, 4),
            ("horror_chapel", "Институтская Часовня", "Скамейки перевёрнуты. Священник сидит лицом к стене.", "Chapel", ["священник-одержимый", "летучий мышиный рой", "голос из алтаря"], {"loot": "серебряный крест", "noise": "шёпот молитвы", "danger": 4}, -3, 5),
            ("horror_office", "Кабинет Директора", "В каждом отчёте — твоё имя. Дверь захлопнулась.", "Office", ["директор-марионетка", "бумажный голем", "запертый шкаф"], {"loot": "личное дело", "noise": "тиканье часов", "danger": 2}, -3, 4),
            ("horror_cellar", "Подвал", "Лампочка моргает. Кто-то царапается изнутри стены.", "Cellar", ["крысиный король", "эксперимент №0", "чёрная плесень"], {"loot": "дневник медсестры", "noise": "царапанье", "danger": 3}, -5, 5),
            ("horror_roof", "Крыша Института", "Антенны ловят голос — он читает твою мед-карту.", "Roof", ["сигнал-ловушка", "птица-наблюдатель", "тело на парапете"], {"loot": "антенный адаптер", "noise": "ветер и голос", "danger": 2}, -4, 3),
        ]
        for lid, name, desc, loc_type, creatures, meta, x, y in grid:
            self.locations[lid] = {
                "name": name, "description": desc, "type": loc_type,
                "creatures": creatures, "meta": meta, "x": x, "y": y,
                "events": [
                    f"{random.choice(creatures)} появился",
                    f"что-то изменилось в {name}",
                ],
            }


class SagaEngine:
    def __init__(self, core, memory_store=None):
        self.core = core
        self.memory_store = memory_store
        self.state = SagaState()
        self.world_manager = WorldManager()

    def _world_path(self, *parts):
        return os.path.join(self.state.world_dir, *parts) if self.state.world_dir else ""

    def _init_world_folder(self, skin):
        self.state.world_dir = ""

    def _save_npc(self, npc_id, data):
        pass

    def _save_npc_thoughts(self, eid: int, text: str):
        ent = self.world.entities.get(eid)
        if ent:
            ent.thoughts = text

    def _load_all_npcs(self):
        return self.world_manager.npcs if hasattr(self.world_manager, 'npcs') else {}

    def _save_map(self):
        pass

    def new_game(self, skin):
        self.state = SagaState(setting_key=skin)
        self.state.hp = 5
        self.state.max_hp = 5
        self.state.mood = "neutral"
        self.world_manager = WorldManager()
        world_seed = random.randint(100000, 999999)
        self.state.seed = world_seed
        self.world = SagaWorld(200, 150, seed=world_seed)
        self.physics = SagaPhysics(self.world)
        self.renderer = SagaRenderer(self.world)
        self._init_world_folder(skin)
        self.state.known_locations = list(self.world_manager.locations.keys())
        if not self.world_manager.npcs:
            self.world_manager.npcs = {}
            for loc_id in self.world_manager.locations:
                loc_data = self.world_manager.locations[loc_id]
                n = loc_data.get("creatures", [])
                for c in n[:2]:
                    nid = f"npc_template_{int(time.time())}_{abs(hash(loc_id + c)) % 9999}"
                    ndata = {
                        "name": c, "appearance": "типичный обитатель", "personality": "нейтральное",
                        "biography": "Местный житель.", "state": {"attitude": "нейтральный", "background_mood": "спокойный"},
                        "is_alive": True, "hp": 3, "fate": "", "history": [],
                        "location": loc_data.get("name", loc_id),
                        "pos_x": loc_data.get("x", 0), "pos_y": loc_data.get("y", 0),
                        "created": datetime.now().isoformat(),
                    }
                    self.world_manager.npcs[nid] = ndata
        self.save_world()

    @staticmethod
    def _extract_json(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n", 1)
            raw = lines[-1] if len(lines) > 1 else raw[3:]
            if "```" in raw:
                raw = raw.rsplit("```", 1)[0]
        return raw.strip()

    def _build_world_from_ollama(self, data: dict):
        self.world.generate_city()
        cx, cy = self.world.width // 2, self.world.height // 2
        for i, loc in enumerate(data.get("locations", [])):
            ox = int(loc.get("x", i % 3 - 1)) * 20 + random.randint(5, 15)
            oy = int(loc.get("y", i // 3 - 1)) * 20 + random.randint(5, 15)
            for dy in range(6):
                for dx in range(8):
                    wx, wy = cx + ox + dx, cy + oy + dy
                    if 0 <= wx < self.world.width and 0 <= wy < self.world.height:
                        if dx == 0 or dy == 0 or dx == 7 or dy == 5:
                            self.world.grid[wy][wx] = TILE_WALL
                        else:
                            self.world.grid[wy][wx] = TILE_FLOOR
        player = Entity(
            eid=self.world.new_eid(), name="Игрок", kind="player",
            x=float(cx), y=float(cy), speed=3.0, faction="player",
        )
        self.world.add_entity(player)
        self.world.player_eid = player.eid
        for npc in data.get("npcs", []):
            loc_id = npc.get("loc_id", "")
            loc_data = next((l for l in data.get("locations", []) if l["id"] == loc_id), None)
            nx = cx + int(loc_data.get("x", 0) if loc_data else 0) * 15 + 4
            ny = cy + int(loc_data.get("y", 0) if loc_data else 0) * 15 + 3
            ent = Entity(
                eid=self.world.new_eid(), name=npc.get("name", "NPC"),
                kind=npc.get("kind", "human"), x=float(nx), y=float(ny),
                speed=1.0, faction="neutral", ai_state="idle",
                title=npc.get("name", "NPC")[:12], emotion="neutral",
                thoughts=npc.get("appearance", "обычный житель"),
            )
            self.world.add_entity(ent)
            nid = f"npc_{ent.eid}_{hash(npc['name']) % 1000}"
            ndata = {
                "name": npc.get("name", "NPC"), "kind": npc.get("kind", "human"),
                "appearance": npc.get("appearance", "обычный житель"),
                "personality": npc.get("personality", "нейтральный"),
                "biography": npc.get("bio", "История неизвестна."),
                "state": {"attitude": "нейтральный", "background_mood": "спокойный"},
                "is_alive": True, "hp": 3, "fate": "", "history": [],
                "location": loc_data.get("name", loc_id) if loc_data else loc_id,
                "pos_x": int(nx), "pos_y": int(ny),
                "created": datetime.now().isoformat(),
            }

    def _rebuild_world_from_data(self):
        cx, cy = self.world.width // 2, self.world.height // 2
        self.world.generate_city()
        for i, (lid, loc) in enumerate(self.world_manager.locations.items()):
            ox = int(loc.get("x", i % 3 - 1)) * 20 + random.randint(5, 15)
            oy = int(loc.get("y", i // 3 - 1)) * 20 + random.randint(5, 15)
            for dy in range(6):
                for dx in range(8):
                    wx, wy = cx + ox + dx, cy + oy + dy
                    if 0 <= wx < self.world.width and 0 <= wy < self.world.height:
                        if dx == 0 or dy == 0 or dx == 7 or dy == 5:
                            self.world.grid[wy][wx] = TILE_WALL
                        else:
                            self.world.grid[wy][wx] = TILE_FLOOR
        player = Entity(
            eid=self.world.new_eid(), name="Игрок", kind="player",
            x=float(cx), y=float(cy), speed=3.0, faction="player",
        )
        self.world.add_entity(player)
        self.world.player_eid = player.eid
        for nid, ndata in self.world_manager.npcs.items():
            if ndata.get("is_alive", True):
                ent = Entity(
                    eid=self.world.new_eid(), name=ndata.get("name", "NPC"),
                    kind=ndata.get("kind", "human"),
                    x=float(cx + int(ndata.get("pos_x", 0)) * 15 + 4),
                    y=float(cy + int(ndata.get("pos_y", 0)) * 15 + 3),
                    speed=1.0, faction="neutral", ai_state="idle",
                    title=ndata.get("name", "NPC")[:12], emotion="neutral",
                    thoughts=ndata.get("appearance", "обычный житель"),
                )
                self.world.add_entity(ent)

    def list_worlds(self):
        worlds_dir = "worlds"
        if not os.path.isdir(worlds_dir):
            return []
        result = []
        for d in os.listdir(worlds_dir):
            seed_dir = os.path.join(worlds_dir, d)
            if not os.path.isdir(seed_dir):
                continue
            required = ["player.json", "locations.json", "npcs.json", "history.json"]
            if not all(os.path.isfile(os.path.join(seed_dir, f)) for f in required):
                continue
            try:
                data = json.loads(Path(os.path.join(seed_dir, "player.json")).read_text(encoding="utf-8"))
                result.append((int(d), data.get("turn", 0)))
            except Exception:
                pass
        return sorted(result, key=lambda x: -x[1])

    def _ai_generate_world(self) -> bool:
        try:
            setting = SAGA_SETTINGS.get(self.state.setting_key, SAGA_SETTINGS["cyber"])
            prompt = (
                f"Мир: {setting['name']}. {setting['vibe']}\n\n"
                f"Верни JSON с миром: 5-7 локаций, 8-12 NPC.\n"
                f"Локация: id, name, desc, type, x (-5..5), y (-5..5), creatures [2]\n"
                f"NPC: name, appearance, personality, bio, loc_id\n"
                f'Пример: {{"world_name":"...","locations":[{{"id":"loc_1","name":"...","desc":"...","type":"Market","creatures":["..."],"x":0,"y":0}}],"npcs":[{{"name":"...","appearance":"...","personality":"...","bio":"...","loc_id":"loc_1"}}]}}\n'
                f"Только JSON."
            )
            opts = self.core.ollama_chat_options(0.3)
            opts["num_predict"] = 4096
            r = ollama.chat(model=self.core.brain_model, messages=[
                {"role": "system", "content": "Ты генератор миров. Отвечай JSON."},
                {"role": "user", "content": prompt}
            ], options=opts, **self.core._ollama_keep_alive_kw())
            raw = self._extract_json(r["message"]["content"])
            data = json.loads(raw)
            self.world_manager.locations.clear()
            for loc in data.get("locations", []):
                self.world_manager.locations[loc["id"]] = {
                    "name": loc["name"], "description": loc["desc"],
                    "type": loc.get("type", "Urban"),
                    "creatures": loc.get("creatures", []),
                    "meta": {}, "x": loc.get("x", 0), "y": loc.get("y", 0),
                    "events": [f"{c} появился" for c in loc.get("creatures", [])[:2]],
                }
            for npc in data.get("npcs", []):
                nid = f"npc_{int(time.time())}_{hash(npc['name']) % 1000}"
                loc_id = npc.get("loc_id", "")
                loc_data = self.world_manager.locations.get(loc_id, {})
                ndata = {
                    "name": npc["name"], "appearance": npc.get("appearance", ""),
                    "personality": npc.get("personality", ""),
                    "biography": npc.get("bio", ""),
                    "state": {"attitude": "нейтральный", "background_mood": "спокойный"},
                    "is_alive": True, "hp": 3, "fate": "", "history": [],
                    "location": loc_data.get("name", loc_id),
                    "pos_x": loc_data.get("x", 0),
                    "pos_y": loc_data.get("y", 0),
                    "created": datetime.now().isoformat(),
                }
                self._save_npc(nid, ndata)
            self.state.known_locations = list(self.world_manager.locations.keys())
            if self.world_manager.locations:
                first = list(self.world_manager.locations.values())[0]
                self.state.player_x = first.get("x", 0)
                self.state.player_y = first.get("y", 0)
            self._build_world_from_ollama(data)
            self.save_world()
            return True
        except Exception as e:
            print(f"[Saga] AI world gen failed: {e}, using fallback")
            self.world.generate_city()
            cx, cy = self.world.width // 2, self.world.height // 2
            if not self.world.get_player():
                player = Entity(
                    eid=self.world.new_eid(), name="Игрок", kind="player",
                    x=float(cx), y=float(cy), speed=3.0, faction="player",
                )
                self.world.add_entity(player)
                self.world.player_eid = player.eid
            for _ in range(5):
                attempts = 0
                while attempts < 30:
                    nx, ny = cx + random.randint(-20, 20), cy + random.randint(-20, 20)
                    attempts += 1
                    if not self.world.is_solid(nx, ny):
                        break
                if not self.world.is_solid(nx, ny):
                    patrol = [(float(nx + random.randint(-2, 2)), float(ny + random.randint(-2, 2))) for _ in range(3)]
                    ent = Entity(
                        eid=self.world.new_eid(),
                        name=f"NPC_{random.choice(['Прохожий','Торговец','Страж','Дрон'])}{random.randint(10,99)}",
                        kind=random.choice(["human","merchant","guard","droid"]),
                        x=float(nx), y=float(ny), speed=1.5, faction="neutral",
                        ai_state="patrol", patrol_points=patrol,
                    )
                    self.world.add_entity(ent)
            return False

    def save(self):
        seed = self.state.seed or getattr(self.world, 'seed', 0)
        base = os.path.join("worlds", str(seed))
        os.makedirs(base, exist_ok=True)
        Path(os.path.join(base, "player.json")).write_text(json.dumps({
            "x": self.state.player_x, "y": self.state.player_y,
            "hp": self.state.hp, "max_hp": self.state.max_hp,
            "inventory": self.state.inventory, "mood": self.state.mood,
            "level": self.state.level, "turn": self.state.turn,
            "seed": self.state.seed,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(os.path.join(base, "history.json")).write_text(json.dumps({
            "transcript": self.state.transcript[-40:],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_world(self, seed: int) -> bool:
        base = os.path.join("worlds", str(seed))
        if not os.path.isdir(base):
            return False
        try:
            data = json.loads(Path(os.path.join(base, "player.json")).read_text(encoding="utf-8"))
            self.state = SagaState(
                player_x=data.get("x", 0),
                player_y=data.get("y", 0),
                hp=data.get("hp", 5),
                max_hp=data.get("max_hp", 5),
                inventory=data.get("inventory", []),
                mood=data.get("mood", "neutral"),
                level=data.get("level", 1),
                turn=data.get("turn", 0),
                seed=data.get("seed", seed),
                setting_key=self.state.setting_key if self.state else "cyber",
            )
            hist = json.loads(Path(os.path.join(base, "history.json")).read_text(encoding="utf-8"))
            self.state.transcript = hist.get("transcript", [])
            locs = json.loads(Path(os.path.join(base, "locations.json")).read_text(encoding="utf-8"))
            self.world_manager.locations.clear()
            self.world_manager.locations.update(locs)
            npcs = json.loads(Path(os.path.join(base, "npcs.json")).read_text(encoding="utf-8"))
            self.world_manager.npcs.clear()
            self.world_manager.npcs.update(npcs)
            self.state.known_locations = list(locs.keys())
            self.world = SagaWorld(200, 150, seed=self.state.seed)
            self.physics = SagaPhysics(self.world)
            self.renderer = SagaRenderer(self.world)
            self._rebuild_world_from_data()
            return True
        except Exception as e:
            print(f"[Saga] load failed: {e}")
            return False

    def save_world(self):
        seed = self.state.seed or getattr(self.world, 'seed', 0)
        base = os.path.join("worlds", str(seed))
        os.makedirs(base, exist_ok=True)
        self.save()
        Path(os.path.join(base, "locations.json")).write_text(json.dumps(
            self.world_manager.locations, ensure_ascii=False, indent=2), encoding="utf-8")
        Path(os.path.join(base, "npcs.json")).write_text(json.dumps(
            self.world_manager.npcs, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_system_prompt(self) -> str:
        inv = ", ".join(self.state.inventory[-6:]) or "пуст"
        st = self.state
        weather_str = {'clear':'ясно','rain':'дождь','fog':'туман','drizzle':'морось','overcast':'пасмурно'}.get(self.world.weather, 'ясно')
        # NPC контекст
        npc_lines = []
        for ndata in list(self._load_all_npcs().values())[:6]:
            if ndata.get("is_alive", True):
                desire = ndata.get("desire", "")
                dream = ndata.get("dream", "")
                d = f" хочет: {desire}" if desire else ""
                dr = f" мечтает: {dream}" if dream else ""
                npc_lines.append(f"  • {ndata['name']} ({ndata.get('kind','human')}) — {ndata.get('appearance','')[:30]}{d}{dr}")
        npc_ctx = ("\nПерсонажи рядом:\n" + "\n".join(npc_lines)) if npc_lines else ""
        return (
            f"Ты рассказчик в мире {st.setting_key}. Сид: {getattr(self.world, 'seed', 0)}.\n"
            f"Игрок: HP {st.hp}, Lv.{st.level}. Инвентарь: {inv}. Погода: {weather_str}.\n"
            f"Локация: {st.player_x},{st.player_y}{npc_ctx}\n\n"
            f"Напиши 3-5 предложений. Живой язык, образы, не шаблон. Создай VISUAL — описание кадра.\n"
            f"VISUAL — слои сзади наперёд:\n"
            f"  bg: top=#цвет bottom=#цвет\n"
            f"  far/layer: объект color=#hex x=0..1 size=0..1\n"
            f"  mid/layer: entity kind=тип color=#hex name=\"имя\" x=0..1 size=0..1\n"
            f"  fg/layer: effect kind=neon/fire color=#hex x=0..1 intensity=0..1\n"
            f"  overlay: rain/fog/dark 0..1\n"
            f"Формат:\nNARRATIVE: текст\nVISUAL:\n  ...\nMOOD: mood\nCHOICES: вариант1, вариант2, вариант3"
        )

    BLOCKED_PATTERNS = [
        'ядерк', 'ядерн', 'бомб', 'взрывчатк', 'бессмерт', 'всемогущ',
        'всесил', 'бесконечн', 'всё могу', 'я бог', 'читер',
        'баг', 'эксплоит', 'лёгк', 'мгновен', 'телепорт',
        'всё знаю', 'все ответ', 'бесконечн', 'миллион',
        'триллион', 'бесконеч', 'взлом игр', 'админ',
        'оружи масс', 'атомн',
    ]

    def _validate_user_input(self, text: str) -> Optional[str]:
        lower = text.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in lower:
                return None
        if len(text) > 200:
            return None
        return text

    def _sanitize_narrative(self, text: str, inventory: list) -> str:
        forb = ['атомн', 'ядерн', 'взрывчатк', 'бомб', 'божествен']
        lower = text.lower()
        for f in forb:
            if f in lower and not any(f in i.lower() for i in inventory):
                while f in lower:
                    idx = lower.find(f)
                    text = text[:idx] + '[ЗАПРЕЩЕНО]' + text[idx+len(f):]
                    lower = text.lower()
        return text

    def step(self, player_line: str):
        player_line = self._validate_user_input(player_line.strip()) or "..."
        self.state.transcript.append({"role": "user", "text": player_line})
        self.state.turn += 1
        prompt = self._build_system_prompt()

        # последние 4 хода истории как контекст
        history = ""
        recent = self.state.transcript[-8:-1] if len(self.state.transcript) > 8 else self.state.transcript[:-1]
        for msg in recent:
            role = msg.get("role", "")
            if role == "user":
                history += f"Игрок: {msg.get('text', '')}\n"
            elif role == "assistant":
                history += f"GM: {msg.get('text', '')[:100]}...\n"

        user_text = (
            f"## ИСТОРИЯ (последние шаги)\n{history}\n"
            f"## ДЕЙСТВИЕ ИГРОКА (ход {self.state.turn})\n"
            f"«{player_line}»\n\n"
            f"Ответь NARRATIVE + MOOD + CHOICES."
        )
        max_retries = 2
        for attempt in range(max_retries):
            try:
                opts = self.core.ollama_chat_options(0.7)
                opts["num_predict"] = 1800
                opts["repeat_penalty"] = 1.15
                messages = [
                    {"role": "system", "content": prompt},
                ]
                if self.memory_store and self.state.turn > 1:
                    mem = self.memory_store.get_context(query=player_line, limit=2)
                    if mem:
                        messages.append({"role": "system", "content": f"Память: {mem}"})
                # inject recent history as user/assistant pairs for better continuity
                for msg in self.state.transcript[-6:-1]:
                    if msg.get("role") == "user":
                        messages.append({"role": "user", "content": msg.get("text", "")})
                    elif msg.get("role") == "assistant":
                        messages.append({"role": "assistant", "content": msg.get("text", "")[:300]})
                messages.append({"role": "user", "content": user_text})
                r = ollama.chat(model=self.core.brain_model, messages=messages,
                                options=opts, **self.core._ollama_keep_alive_kw())
                raw = r["message"]["content"]
                narrative, mood, visual, choices_text = self._parse(raw)
                if self._needs_russian_retry(narrative):
                    narrative = self._ollama(f"Перепиши на русском (только текст, без пояснений): {narrative[:400]}",
                                            system="Только русский язык.", temp=0.2, num=300)
                choices = [c.strip() for c in choices_text.split(",") if c.strip()][:4]
                while len(choices) < 2:
                    choices.append("Осмотреться")
                narrative = self._sanitize_narrative(narrative, self.state.inventory)
                self.state.transcript.append({"role": "assistant", "text": narrative, "mood": mood, "visual": visual})
                item = self._extract_item(narrative)
                if item and item not in self.state.inventory:
                    self.state.inventory.append(item)
                if self.memory_store and len(narrative) > 30:
                    self.memory_store.add_fact(f"Ход {self.state.turn}: {narrative[:200]}")
                self.save()
                if self.state.hp <= 0:
                    return narrative, "sad", "", ["Начать заново"], True
                ended = self.state.turn >= 50 or self.state.hp <= 0
                return narrative, mood, visual, choices, ended
            except Exception as e:
                print(f"[Saga] step attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    return _fallback_scene(self.state), "tense", "", DEFAULT_CHOICES, False

    def _setting_profile(self, setting_key: str) -> Tuple[str, str, str, str]:
        profiles = NPC_PROFILES.get(setting_key, NPC_PROFILES["cyber"])
        appearance = random.choice(profiles["appearance_pool"])
        personality = random.choice(profiles["personality_pool"])
        bio = profiles["biography_template"].format(personality=personality)
        return appearance, personality, bio, profiles.get("name_template", "")

    def _generate_npc_appearance(self, setting_key: str) -> str:
        return self._setting_profile(setting_key)[0]

    def _generate_npc_personality(self, setting_key: str) -> str:
        return self._setting_profile(setting_key)[1]

    def _generate_npc_biography(self, setting_key: str) -> str:
        return self._setting_profile(setting_key)[2]

    def _npc_short_state(self, ndata: dict) -> str:
        parts = [ndata.get("name", "?")]
        s = ndata.get("state", {})
        if s.get("attitude") != "нейтральный":
            parts.append(s.get("attitude", ""))
        if s.get("background_mood") not in ("спокойный", ""):
            parts.append(s.get("background_mood", ""))
        if not ndata.get("is_alive", True):
            parts.append("мёртв")
        return " | ".join(parts)

    def _evolve_npcs(self) -> list:
        events = []
        npcs = self._load_all_npcs()
        for lid, ndata in list(npcs.items())[:5]:
            if not ndata.get("is_alive", True):
                continue
            states = ["attitude", "background_mood"]
            if random.random() < 0.2:
                shift = random.choice(["настороженный", "дружелюбный", "агрессивный", "нейтральный", "задумчивый", "растерянный"])
                ndata.setdefault("state", {})[random.choice(states)] = shift
                events.append(f"{ndata['name']} стал {shift}")
            if random.random() < 0.15:
                new_loc_list = [l for l in self.state.known_locations if l != ndata.get("location", "")]
                if new_loc_list:
                    old = ndata.get("location", "?")
                    new_loc = random.choice(new_loc_list)
                    ndata["location"] = self.world_manager.locations.get(new_loc, {}).get("name", new_loc)
                    events.append(f"{ndata['name']} переместился из {old} куда-то ещё")
        return events

    def _background_evolve(self) -> list:
        if not self.state.known_locations:
            return []
        self.world.update_cycle(25.0)
        events = []
        weather_names = {'clear': 'ясно', 'rain': 'дождь', 'fog': 'туман', 'drizzle': 'морось', 'overcast': 'пасмурно'}
        day_str = 'день' if self.world.daylight > 0.5 else 'вечер' if self.world.daylight > 0.3 else 'ночь'
        events.append(f"{weather_names.get(self.world.weather, '?')}, {day_str}")
        for lid in random.sample(self.state.known_locations, min(2, len(self.state.known_locations))):
            loc = self.world_manager.locations.get(lid, {})
            if loc and random.random() < 0.25:
                sounds = ["шум", "шаги", "звук", "вспышка", "голос", "сигнал", "треск", "эхо"]
                events.append(f"{loc.get('name', '?')}: {random.choice(sounds)}")
        events.extend(self._evolve_npcs())
        return events[:5]

    def _fallback_scene(self, state) -> str:
        templates = [
            "Тишина. Только ветер шевелит пыль. Ничего не происходит.",
            "Где-то вдалеке сработала сигнализация. Или показалось.",
            "Тени сгущаются. Или это просто усталость играет с глазами.",
            "Ничего нового. Мир замер в ожидании твоего следующего шага.",
        ]
        mood_labels = {"neutral": "спокойно", "tense": "напряжённо", "combat": "опасно", "discovery": "интригующе"}
        mood_str = mood_labels.get(state.mood, "спокойно")
        return random.choice(templates).rstrip(".!") + f", но {mood_str}."

    def _needs_russian_retry(self, text: str) -> bool:
        if not text or len(text) < 10:
            return True
        return bool(ENGLISH_MARKERS.search(text))

    def _ollama(self, prompt: str, system: str = "", temp: float = 0.2, num: int = 300) -> str:
        opts = self.core.ollama_chat_options(temp)
        opts["num_predict"] = num
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        r = ollama.chat(model=self.core.brain_model, messages=msgs,
                        options=opts, **self.core._ollama_keep_alive_kw())
        return r["message"]["content"]

    def _parse(self, text: str):
        narrative = ""
        mood = "neutral"
        visual = ""
        choices_raw = ""
        in_visual = False
        visual_lines = []
        for line in text.split("\n"):
            l = line.strip()
            if l.upper().startswith("NARRATIVE:"):
                narrative = l[len("NARRATIVE:"):].strip()
            elif l.upper().startswith("MOOD:"):
                mood = l[len("MOOD:"):].strip().lower()
            elif l.upper().startswith("VISUAL:"):
                in_visual = True
                rest = l[len("VISUAL:"):].strip()
                if rest:
                    visual_lines.append(rest)
            elif l.upper().startswith("CHOICES:"):
                choices_raw = l[len("CHOICES:"):].strip()
                in_visual = False
            elif in_visual:
                visual_lines.append(l)
        if visual_lines:
            visual = "\n".join(visual_lines)
        if not narrative and text:
            narrative = text[:200]
        return narrative, mood, visual, choices_raw

    def _extract_item(self, text: str) -> Optional[str]:
        items = re.findall(r'(?:нашёл|подобрал|взял|получил|находит|поднимает)\s+([А-Яа-яA-Za-z\s-]{3,30}?)\.', text)
        return items[0] if items else None
