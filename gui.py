# -*- coding: utf-8 -*-
import json, os, queue, subprocess, threading, time, tkinter as tk, traceback
from tkinter import messagebox
from pathlib import Path
import logging
from io import BytesIO
from PIL import Image, ImageTk
import screen_sensor as _ss
os.makedirs('logs', exist_ok=True)
try:
    import pyautogui
except Exception:
    pyautogui = None
logging.basicConfig(filename='logs/sentinel.log', level=logging.INFO, format='%(asctime)s - %(message)s')
import customtkinter as ctk

APP_VERSION = '17.3'
P = {'bg':'#090d14','card':'#131a24','panel':'#0f1620','border':'#2d3746','blue':'#58a6ff','green':'#3fb950','yellow':'#d29922','red':'#f85149','text':'#e6edf3','sub':'#8b949e'}
_THEMES_P = {
    'Неон': {'blue':'#58a6ff','green':'#3fb950','card':'#131a24','panel':'#0f1620','bg':'#090d14','border':'#2d3746','text':'#e6edf3','sub':'#8b949e'},
    'Океан': {'blue':'#79c0ff','green':'#39c5bb','card':'#0c2030','panel':'#091926','bg':'#050d16','border':'#1f4d68','text':'#e6f4ff','sub':'#8fb7ca'},
    'Закат': {'blue':'#ff9f7a','green':'#f2cc60','card':'#241710','panel':'#1a110c','bg':'#100905','border':'#684234','text':'#fff1e6','sub':'#c99b82'},
    'Лес': {'blue':'#7ee787','green':'#3fb950','card':'#0f2213','panel':'#09180c','bg':'#050d07','border':'#2d6538','text':'#e8f5e9','sub':'#9bbb9c'},
    'Монохром': {'blue':'#d0d0d0','green':'#9a9a9a','card':'#242424','panel':'#1c1c1c','bg':'#111111','border':'#4a4a4a','text':'#eeeeee','sub':'#aaaaaa'},
}

_FACE = {
    'idle':('58a6ff','1a5fb4','0d2040','1a3a5c'), 'thinking':('d29922','8b5a00','3d2b00','5c4000'),
    'active':('3fb950','1a6b2a','0d3320','1a5c2e'), 'sleep':('8b949e','6e7681','161b22','30363d'),
    'error':('f85149','b42318','3d1110','5c1a14'), 'happy':('ffa657','c46200','3d2200','5c3300'),
    'surprised':('79c0ff','2a6bc6','0d2040','1a3a5c'), 'suspicious':('a371f7','6e40c9','2d1b4e','4a2b7a'),
    'hurt':('f85149','b42318','3d1110','5c1a14'), 'love':('f778ba','c9358b','3d1020','5c1a3a'),
    'angry':('ff7b72','c9372d','3d1510','5c241a'), 'bored':('8b949e','6e7681','161b22','30363d'),
    'excited':('ff7b72','c9372d','3d1510','5c241a'), 'determined':('58a6ff','1a5fb4','0d2040','1a3a5c'),
    'confused':('d29922','8b5a00','3d2b00','5c4000'), 'repair':('f85149','b42318','3d1110','5c1a14'),
    'watching':('a371f7','6e40c9','2d1b4e','4a2b7a'), 'success':('3fb950','1a6b2a','0d3320','1a5c2e'),
}
_FACE_SHAPES = {
    'idle':(0.7,0,'smile',0), 'thinking':(0.4,-4,'line',0), 'active':(1.0,0,'big_smile',0.1),
    'sleep':(0.15,2,'flat',0), 'error':(0.6,3,'frown',0), 'happy':(0.9,-2,'grin',0.15),
    'surprised':(1.0,-5,'o',0.3), 'suspicious':(0.5,-2,'smirk',0.0),
    'hurt':(0.4,4,'frown',0.05), 'love':(0.85,-3,'heart',0.2),
    'angry':(0.8,5,'grrr',0.1), 'bored':(0.3,1,'flat',0.0),
    'excited':(1.0,-4,'big_smile',0.2), 'determined':(0.75,1,'line',0.05),
    'confused':(0.6,-1,'smirk',0.0), 'repair':(0.55,4,'frown',0),
    'watching':(0.9,-2,'line',0.08), 'success':(1.0,-3,'big_smile',0.2),
}

class AnimatedFace(tk.Canvas):
    def __init__(self, parent, size=220, **kw):
        bg = kw.pop('bg', P['card'])
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, **kw)
        self.size = size; self.state = 'idle'; self._tick = 0; self._after_id = None
        self._items = {}; self._particles = []
        self._build(); self._loop()

    def _build(self):
        s = self.size; cx = cy = s//2; r = s//2 - 14
        self._items['glow1'] = self.create_oval(cx-r-18,cy-r-18,cx+r+18,cy+r+18, outline='#0d2040', width=12, fill='', tags='glow')
        self._items['glow2'] = self.create_oval(cx-r-10,cy-r-10,cx+r+10,cy+r+10, outline='#1a3a5c', width=4, fill='', tags='glow')
        self._items['face_bg'] = self.create_oval(cx-r,cy-r,cx+r,cy+r, outline='', fill='#0d1117', width=0)
        self._items['face_ring'] = self.create_oval(cx-r,cy-r,cx+r,cy+r, outline='#1a3a5c', width=2, fill='')
        ex_l = cx - r//3; ex_r = cx + r//3; ey = cy - r//5; ew, eh = 28, 18
        for side, ex in [('l',ex_l),('r',ex_r)]:
            self._items[f'eye_{side}_bg'] = self.create_oval(ex-ew//2,ey-eh//2,ex+ew//2,ey+eh//2, fill='#161b22', outline='', tags='eye')
            self._items[f'iris_{side}'] = self.create_oval(ex-8,ey-8,ex+8,ey+8, fill='#58a6ff', outline='', tags='eye')
            self._items[f'pupil_{side}'] = self.create_oval(ex-4,ey-4,ex+4,ey+4, fill='#0d1117', outline='', tags='eye')
            self._items[f'shine_{side}'] = self.create_oval(ex-2,ey-5,ex+1,ey-1, fill='#ffffff', outline='', tags='eye')
        self._items['brow_l'] = self.create_arc(ex_l-16,ey-22,ex_l+16,ey-2, start=20, extent=140, style='arc', outline='#58a6ff', width=3, tags='brow')
        self._items['brow_r'] = self.create_arc(ex_r-16,ey-22,ex_r+16,ey-2, start=20, extent=140, style='arc', outline='#58a6ff', width=3, tags='brow')
        self._items['mouth'] = self.create_arc(cx-r//3,cy+r//8,cx+r//3,cy+r//2, start=200, extent=140, style='arc', outline='#58a6ff', width=3, tags='mouth')
        for i in range(6):
            px = cx + int((r+20)*0.9)
            dot = self.create_oval(px-2,cy-2,px+2,cy+2, fill='#58a6ff', outline='', tags='particle')
            self._particles.append({'id':dot, 'angle':(i/6)*360, 'speed':0.5+i*0.2, 'dist':r+18+i*3})

    def recolor(self, accent, dim, bg):
        self.itemconfig(self._items['face_ring'], outline=dim)
        self.itemconfig(self._items['glow2'], outline=dim)
        for side in ['l','r']:
            self.itemconfig(self._items[f'iris_{side}'], fill=accent)
            self.itemconfig(self._items[f'brow_{side}'], outline=accent)
        self.itemconfig(self._items['mouth'], outline=accent)
        for p in self._particles: self.itemconfig(p['id'], fill=accent)
        self.itemconfig(self._items['face_bg'], fill=bg)

    def set_state(self, state):
        if state not in _FACE or state == self.state: return
        self.state = state
        eye_c, iris_c, glow_c, ring_c = (f'#{x}' for x in _FACE[state])
        self.itemconfig(self._items['face_ring'], outline=ring_c)
        self.itemconfig(self._items['glow2'], outline=glow_c)
        for side in ['l','r']:
            self.itemconfig(self._items[f'iris_{side}'], fill=iris_c)
            self.itemconfig(self._items[f'brow_{side}'], outline=eye_c)
        self.itemconfig(self._items['mouth'], outline=eye_c)
        for p in self._particles: self.itemconfig(p['id'], fill=eye_c)
        s = self.size; cx = cy = s//2; r = s//2 - 14
        ex_l = cx - r//3; ex_r = cx + r//3; ey = cy - r//5; ew, eh = 28, 18
        eye_open, brow_dy, mouth_shape, _ = _FACE_SHAPES.get(state, _FACE_SHAPES['idle'])
        eh_curr = max(2, int(eh * eye_open))
        for side, ex in [('l',ex_l),('r',ex_r)]:
            self.coords(self._items[f'eye_{side}_bg'], ex-ew//2, ey-eh_curr//2, ex+ew//2, ey+eh_curr//2)
            if eh_curr < 6:
                for t in ['iris','pupil','shine']: self.itemconfig(self._items[f'{t}_{side}'], state='hidden')
            else:
                for t in ['iris','pupil','shine']: self.itemconfig(self._items[f'{t}_{side}'], state='normal')
                self.coords(self._items[f'iris_{side}'], ex-8, ey-8, ex+8, ey+8)
                self.coords(self._items[f'pupil_{side}'], ex-4, ey-4, ex+4, ey+4)
                self.coords(self._items[f'shine_{side}'], ex-2, ey-5, ex+1, ey-1)
        brow_y = ey - 18 + brow_dy
        self.coords(self._items['brow_l'], ex_l-16, brow_y-10, ex_l+16, brow_y+10)
        self.coords(self._items['brow_r'], ex_r-16, brow_y-10, ex_r+16, brow_y+10)
        if mouth_shape == 'smile':
            self.itemconfig(self._items['mouth'], start=200, extent=140, style='arc')
            self.coords(self._items['mouth'], cx-r//3, cy+r//8, cx+r//3, cy+r//2)
        elif mouth_shape == 'big_smile':
            self.itemconfig(self._items['mouth'], start=190, extent=160, style='arc')
            self.coords(self._items['mouth'], cx-r//3, cy+r//10, cx+r//3, cy+r//1.8)
        elif mouth_shape == 'grin':
            self.itemconfig(self._items['mouth'], start=200, extent=140, style='arc')
            self.coords(self._items['mouth'], cx-r//3, cy+r//8, cx+r//3, cy+r//1.6)
        elif mouth_shape == 'line':
            self.itemconfig(self._items['mouth'], start=0, extent=180, style='arc')
            self.coords(self._items['mouth'], cx-r//4, cy+r//4, cx+r//4, cy+r//3)
        elif mouth_shape == 'flat':
            self.itemconfig(self._items['mouth'], start=0, extent=180, style='arc')
            self.coords(self._items['mouth'], cx-r//5, cy+r//4, cx+r//5, cy+r//4+2)
        elif mouth_shape == 'frown':
            self.itemconfig(self._items['mouth'], start=20, extent=140, style='arc')
            self.coords(self._items['mouth'], cx-r//3, cy+r//3, cx+r//3, cy+r//1.5)

    def _loop(self):
        self._tick += 1; s = self.size; cx = cy = s//2; r = s//2 - 14
        if self.state != 'sleep':
            blink = 100 + (self._tick % 97)
            tb = self._tick % blink
            if tb == 0: self._blink(True)
            elif tb == 4: self._blink(False)
        glow = 1.0 + 0.08 * (1 if (self._tick//15)%2 else -1)
        rg = (s//2-14) * glow
        self.coords(self._items['glow1'], cx-rg-18, cy-rg-18, cx+rg+18, cy+rg+18)
        self.coords(self._items['glow2'], cx-rg-10, cy-rg-10, cx+rg+10, cy+rg+10)
        if self.state in ('thinking','active'):
            pulse = f'#{_FACE[self.state][0]}' if (self._tick//8)%2 else f'#{_FACE[self.state][3]}'
            self.itemconfig(self._items['face_ring'], outline=pulse)
        for p in self._particles:
            px = cx + int(p['dist'] * 0.9 * (1 + 0.03*((self._tick%30)-15)/15))
            py = cy + int((p['dist']*0.4) * ((self._tick%40)-20)/20)
            self.coords(p['id'], px-2, py-2, px+2, py+2)
        if self.state in ('idle','thinking','active','happy'):
            try:
                mx = self.winfo_pointerx() - self.winfo_rootx()
                my = self.winfo_pointery() - self.winfo_rooty()
                for side, ex in [('l',cx-r//3),('r',cx+r//3)]:
                    dx = max(-6, min(6, (mx-ex)//30)); dy = max(-4, min(4, (my-(cy-r//5))//30))
                    be = cy - r//5
                    self.coords(self._items[f'iris_{side}'], ex-8+dx, be-8+dy, ex+8+dx, be+8+dy)
                    self.coords(self._items[f'pupil_{side}'], ex-4+dx, be-4+dy, ex+4+dx, be+4+dy)
                    self.coords(self._items[f'shine_{side}'], ex-2+dx, be-5+dy, ex+1+dx, be-1+dy)
            except tk.TclError: pass
        ms = 40 if self.state in ('thinking','active') else (200 if self.state=='sleep' else 80)
        self._after_id = self.after(ms, self._loop)

    def _blink(self, close):
        s = self.size; cx = s//2; r = s//2 - 14
        ex_l = cx - r//3; ex_r = cx + r//3; ey = s//2 - r//5; ew = 28
        if close:
            for side, ex in [('l',ex_l),('r',ex_r)]:
                self.coords(self._items[f'eye_{side}_bg'], ex-ew//2, ey-1, ex+ew//2, ey+1)
                for t in ['iris','pupil','shine']: self.itemconfig(self._items[f'{t}_{side}'], state='hidden')
        else:
            st = self.state; self.state = ''; self.set_state(st)

    def stop(self):
        if self._after_id: self.after_cancel(self._after_id); self._after_id = None

class AimOverlay(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True); self.attributes('-topmost', True); self.attributes('-alpha', 0.92)
        self.configure(bg='#0a0a0a'); self.geometry('480x130')
        self._dx = self._dy = 0
        self.bind('<Button-1>', lambda e: (setattr(self,'_dx',e.x), setattr(self,'_dy',e.y)))
        self.bind('<B1-Motion>', self._drag); self.bind('<Double-1>', lambda _: self.withdraw())
        fr = tk.Frame(self, bg='#0a0a0a', padx=12, pady=6); fr.pack(fill='both', expand=True)
        top = tk.Frame(fr, bg='#0a0a0a'); top.pack(fill='x')
        self._prof = tk.Label(top, text='Aim Coach', bg='#0a0a0a', fg='#58a6ff', font=('Segoe UI',9,'bold'), anchor='w')
        self._prof.pack(side='left')
        self._scene_lbl = tk.Label(top, text='', bg='#0a0a0a', fg='#8b949e', font=('Segoe UI',8), anchor='e')
        self._scene_lbl.pack(side='right')
        self._tip = tk.Label(fr, text='Waiting...', bg='#0a0a0a', fg='#e6edf3', font=('Segoe UI',15,'bold'), wraplength=460, justify='left', anchor='w')
        self._tip.pack(fill='x', pady=(2,0))
        bot = tk.Frame(fr, bg='#0a0a0a'); bot.pack(fill='x')
        self._stat = tk.Label(bot, text='', bg='#0a0a0a', fg='#8b949e', font=('Segoe UI',8), anchor='w')
        self._stat.pack(side='left')
        self._ocr_lbl = tk.Label(bot, text='', bg='#0a0a0a', fg='#FFA500', font=('Segoe UI',8), anchor='e')
        self._ocr_lbl.pack(side='right')
        try:
            p = json.loads(Path(__file__).parent.joinpath('aim_overlay_pos.json').read_text())
            x, y = int(p['x']), int(p['y'])
            self.geometry(f"+{x}+{y}")
        except Exception:
            self.geometry('+50+50')
    def update_advice(self, advice, profile='', stats='', ocr='', scene=''):
        self._tip.configure(text=advice or '—')
        if profile: self._prof.configure(text=f'{profile}')
        if stats: self._stat.configure(text=stats)
        if ocr: self._ocr_lbl.configure(text=ocr[:80])
        if scene: self._scene_lbl.configure(text=scene)
        self.deiconify()
    def _drag(self, e):
        x, y = self.winfo_x()+e.x-self._dx, self.winfo_y()+e.y-self._dy
        self.geometry(f'+{x}+{y}')
        try: Path(__file__).parent.joinpath('aim_overlay_pos.json').write_text(json.dumps({'x':x,'y':y}))
        except Exception: pass

class SentinelGUI(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode('dark'); ctk.set_default_color_theme('blue')
        super().__init__()
        self.title(f'SENTINEL AI v{APP_VERSION}')
        self.geometry('1280x780'); self.minsize(920, 620); self.configure(fg_color=P['bg'])
        self._log_q = queue.Queue(); self._running = threading.Event(); self._aim_active = threading.Event(); self._sleep_mode = False
        self._core = self._planner = self._executor = None; self._aim_coach = self._memory = self._custodian = None
        self._translator_win = None; self._aim_overlay = None
        self._last_agent_mouse = None; self._agent_mouse_owned_until = 0.0; self._manual_pause_until = 0.0
        self._repair_error = ""; self._repair_frame = None
        self._pending_game_profile = 'Auto Detect'
        self._build_ui(); self._start_log_drain(); self.after(200, self._load_async)
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _load_async(self):
        threading.Thread(target=self._load_modules, daemon=True).start()

    def _load_modules(self):
        self._log('Loading modules...'); self._face.set_state('thinking'); self._set_status('Loading', 'yellow')
        try:
            from core import Core; from planner import Planner; from executor import Executor
            from aim_coach import AimCoach; from memory import MemoryStore
            self._core = Core()
            self._memory = MemoryStore(
                path=self._core.cfg.get('memory_file', 'sentinel_memory.json'),
                limit=self._core.cfg.get('memory_limit', 200)
            )
            self._core.memory = self._memory
            self._planner = Planner(core=self._core, brain_model=self._core.brain_model,
                planner_history_limit=self._core.cfg.get('planner_history_limit',4),
                planner_max_steps=self._core.cfg.get('planner_max_steps',16),
                planner_temperature=self._core.cfg.get('planner_temperature',0.4),
                allow_web_search=self._core.cfg.get('allow_web_search',False),
                memory_store=self._memory, offline_mode=self._core.cfg.get('offline_mode',True))
            self._executor = Executor(core=self._core, auto=self._core.auto_execute,
                search_engine=self._core.cfg.get('use_search_engine',''), offline_mode=self._core.cfg.get('offline_mode',True))
            self._core.executor = self._executor; self._core.planner = self._planner
            self._aim_coach = AimCoach(core=self._core, planner=self._planner, log_callback=self._log, memory_store=self._memory)
            self._aim_coach.set_game_profile(self._pending_game_profile)
            try:
                from night_custodian import NightCustodian
                self._custodian = NightCustodian(memory_store=self._memory, core=self._core, log_callback=self._log)
                self._custodian.start()
            except Exception as e: self._log(f'Custodian: {e}')
            try:
                from sleep_cycle import SleepCycle
                self._sleep_cycle = SleepCycle(core=self._core, memory_store=self._memory)
                self._sleep_cycle.start()
            except Exception as e: self._log(f'SleepCycle: {e}')
            self._log('All modules loaded.'); self._face.set_state('idle'); self._set_status('Ready', 'green')
            self.after(0, self._unlock_controls)
            self.after(1000, self._start_metrics_timer)
        except Exception as exc:
            self._write_startup_error(exc)
            self._log(f'Load error: {exc}')
            self.after(0, lambda e=exc: self._enter_repair_mode(e))

    def _write_startup_error(self, exc):
        try:
            Path('logs').mkdir(exist_ok=True)
            Path('logs/startup_error.log').write_text(
                f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
                encoding='utf-8'
            )
        except Exception:
            pass

    def _start_metrics_timer(self):
        try:
            from AgentToolbox import AIAgentToolbox
            self._toolbox = AIAgentToolbox()
        except Exception:
            self._toolbox = None
        self._update_metrics()

    def _update_metrics(self):
        if not hasattr(self, '_metrics_lbl') or not self._metrics_lbl:
            self.after(5000, self._update_metrics)
            return
        if self._toolbox:
            try:
                m = self._toolbox.get_performance_metrics()
                cpu = m.get('cpu_percent', 0)
                mem = m.get('memory_percent', 0)
                gpu = m.get('gpu_percent')
                gpu_mem = m.get('gpu_memory_gb')
                parts = [f"CPU {cpu:.0f}%"]
                parts.append(f"RAM {mem:.0f}%")
                if gpu is not None:
                    parts.append(f"GPU {gpu:.0f}%")
                if gpu_mem is not None:
                    parts.append(f"VRAM {gpu_mem:.1f}GB")
                txt = " | ".join(parts)
                self.after(0, lambda: self._metrics_lbl.configure(text=txt))
            except Exception:
                pass
        self.after(5000, self._update_metrics)
        self._update_screen_preview()

    def _update_screen_preview(self):
        if not hasattr(self, '_screen_preview_lbl') or not self._screen_preview_lbl or not hasattr(self, '_screen_preview_info'):
            self.after(1000, self._update_screen_preview)
            return
        try:
            buf = _ss.LAST_SCREEN
            if buf:
                img = Image.open(BytesIO(buf))
                tk_img = ImageTk.PhotoImage(img)
                self._screen_preview_lbl.configure(image=tk_img)
                self._screen_preview_lbl._preview_img = tk_img
                desc = _ss.LAST_SCREEN_STATE
                if desc:
                    lines = desc.split('\n')
                    scene_line = lines[0] if lines else ''
                    ui_line = next((l for l in lines if l.startswith('UI:')), '')
                    info = scene_line[:50] + (' | ' + ui_line[:40] if ui_line else '')
                    self._screen_preview_info.configure(text=info)
                else:
                    self._screen_preview_info.configure(text='')
            else:
                self._screen_preview_lbl.configure(image='')
                self._screen_preview_info.configure(text='Screen preview inactive')
        except Exception:
            pass
        self.after(1000, self._update_screen_preview)

    def _enter_repair_mode(self, exc):
        self._repair_error = str(exc)
        self._face.set_state('repair'); self._set_status('Repair', 'red')
        self._face_title.configure(text='SENTINEL / REPAIR')
        self._face_sub.configure(text='Мозг не загрузился, пульт жив')
        self._log('Repair mode: GUI жив, можно проверить Ollama/конфиг.')
        try:
            self._tabs.set('Agent')
            self._show_repair_panel(str(exc))
        except Exception:
            pass
        for w in (self._input_entry, self._send_btn):
            try: w.configure(state='disabled')
            except Exception: pass

    def _show_repair_panel(self, error_text):
        if not self._repair_frame:
            tab = self._tabs.tab('Agent')
            self._repair_frame = ctk.CTkFrame(tab, fg_color=P['panel'], corner_radius=8, border_width=1, border_color=P['red'])
            ctk.CTkLabel(self._repair_frame, text='Режим ремонта', font=ctk.CTkFont(size=15, weight='bold'), text_color=P['red']).pack(anchor='w', padx=10, pady=(8,2))
            self._repair_label = ctk.CTkLabel(self._repair_frame, text='', font=ctk.CTkFont(size=11), text_color=P['text'], wraplength=820, justify='left')
            self._repair_label.pack(fill='x', padx=10, pady=(0,8))
            row = ctk.CTkFrame(self._repair_frame, fg_color=P['panel']); row.pack(fill='x', padx=8, pady=(0,8))
            for text, cmd in (
                ('Проверить Ollama', self._repair_check_ollama),
                ('Показать модели', self._repair_list_models),
                ('Открыть config', self._repair_open_config),
                ('Без мозга', self._repair_brainless),
            ):
                ctk.CTkButton(row, text=text, width=135, height=30, fg_color=P['border'], hover_color=P['blue'], command=cmd).pack(side='left', padx=3)
        self._repair_label.configure(text=error_text[:900])
        self._repair_frame.pack(fill='x', padx=8, pady=(8,0), before=self._log_text)

    def _repair_check_ollama(self):
        threading.Thread(target=lambda: self._run_repair_cmd(['ollama', 'list'], 'Ollama'), daemon=True).start()

    def _repair_list_models(self):
        threading.Thread(target=lambda: self._run_repair_cmd(['ollama', 'list'], 'Models'), daemon=True).start()

    def _repair_open_config(self):
        try:
            os.startfile(str(Path('config.json').resolve()))
        except Exception as e:
            self._log(f'Config open error: {e}')

    def _repair_brainless(self):
        try:
            from core import Core
            from executor import Executor
            from memory import MemoryStore
            self._core = Core(skip_model_check=True)
            self._memory = MemoryStore(path=self._core.cfg.get('memory_file', 'sentinel_memory.json'), limit=self._core.cfg.get('memory_limit', 200))
            self._core.memory = self._memory
            self._executor = Executor(core=self._core, auto=False, search_engine=self._core.cfg.get('use_search_engine',''), offline_mode=True)
            self._core.executor = self._executor
            self._log('Без мозга: доступны зрение, память, коуч-эвристика и ремонт.')
            self._set_status('Brainless', 'yellow')
            self._unlock_repair_controls()
        except Exception as e:
            self._log(f'Brainless start error: {e}')

    def _unlock_repair_controls(self):
        for w in (self._input_entry,):
            try: w.configure(state='normal')
            except Exception: pass

    def _run_repair_cmd(self, cmd, label):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20, encoding='utf-8', errors='replace')
            out = (res.stdout or res.stderr or '').strip()
            self._log(f'{label}: {out[:1800] or "нет вывода"}')
        except Exception as e:
            self._log(f'{label} error: {e}')

    def _unlock_controls(self):
        for w in (self._start_btn, self._input_entry, self._send_btn, self._aim_q_entry):
            w.configure(state='normal')

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color=P['card'], height=52, corner_radius=0)
        self._hdr = hdr
        hdr.pack(fill='x'); self._hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='SENTINEL AI', font=ctk.CTkFont(size=20, weight='bold'), text_color=P['blue']).pack(side='left', padx=18, pady=8)
        ctk.CTkLabel(hdr, text='Autonomous assistant, coach and safe local UI explorer', font=ctk.CTkFont(size=11), text_color=P['sub']).pack(side='left', pady=8)
        ctk.CTkButton(hdr, text='Fullscreen', width=120, height=30, fg_color=P['border'], hover_color='#444c56', command=self._toggle_fullscreen).pack(side='right', padx=6, pady=10)
        self._status_lbl = ctk.CTkLabel(self._hdr, text='Loading', text_color=P['yellow'], font=ctk.CTkFont(size=12, weight='bold'))
        self._status_lbl.pack(side='right', padx=10)
        body = tk.Frame(self, bg=P['bg']); self._body = body; body.pack(fill='both', expand=True)
        body.columnconfigure(1, weight=1); body.rowconfigure(0, weight=1)
        self._build_left(body); self._build_right(body)

    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, fg_color=P['card'], width=240, corner_radius=0)
        left.grid(row=0, column=0, sticky='nsew'); left.pack_propagate(False)
        fwrap = ctk.CTkFrame(left, fg_color=P['card']); fwrap.pack(pady=(14,2))
        self._face = AnimatedFace(fwrap, size=190, bg=P['card']); self._face.pack()
        self._face_title = ctk.CTkLabel(left, text='SENTINEL / IDLE', font=ctk.CTkFont(size=12, weight='bold'), text_color=P['blue'])
        self._face_title.pack(pady=(2,0))
        self._face_sub = ctk.CTkLabel(left, text='Ready', font=ctk.CTkFont(size=10), text_color=P['sub'])
        self._face_sub.pack(pady=(0,4))
        self._screen_preview_lbl = ctk.CTkLabel(left, text='', fg_color=P['bg'], width=200, height=112)
        self._screen_preview_lbl.pack(pady=(0,2))
        self._screen_preview_info = ctk.CTkLabel(left, text='', font=ctk.CTkFont(size=8), text_color=P['sub'])
        self._screen_preview_info.pack(pady=(0,2))
        self._metrics_lbl = ctk.CTkLabel(left, text='', font=ctk.CTkFont(size=8), text_color=P['sub'])
        self._metrics_lbl.pack(pady=(0,6))
        ctk.CTkFrame(left, height=1, fg_color=P['border']).pack(fill='x', padx=14, pady=2)
        ctk.CTkLabel(left, text='Управление', font=ctk.CTkFont(size=11, weight='bold'), text_color=P['sub']).pack(pady=(6,4), padx=14, anchor='w')
        self._start_btn = ctk.CTkButton(left, text='▶ Запустить задачу', height=38, fg_color='#2563eb', hover_color='#1d4ed8', corner_radius=8, command=self._toggle_agent, state='disabled')
        self._start_btn.pack(fill='x', padx=14, pady=2)
        mode_row = ctk.CTkFrame(left, fg_color=P['card']); mode_row.pack(fill='x', padx=14, pady=2)
        ctk.CTkLabel(mode_row, text='Режим:', text_color=P['sub'], font=ctk.CTkFont(size=10)).pack(side='left')
        self._run_mode_cb = ctk.CTkComboBox(mode_row, values=['Авто','По шагам','Только совет'], height=28, width=140)
        self._run_mode_cb.set('Авто'); self._run_mode_cb.pack(side='right')
        theme_row = ctk.CTkFrame(left, fg_color=P['card']); theme_row.pack(fill='x', padx=14, pady=(0,10))
        ctk.CTkLabel(theme_row, text='Тема:', text_color=P['sub'], font=ctk.CTkFont(size=10)).pack(side='left')
        self._theme_cb = ctk.CTkComboBox(theme_row, values=list(_THEMES_P.keys()), height=28, width=140, command=self._on_theme)
        self._theme_cb.set('Неон'); self._theme_cb.pack(side='right')

    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color=P['bg'], corner_radius=0)
        right.grid(row=0, column=1, sticky='nsew')
        right.rowconfigure(1, weight=1); right.columnconfigure(0, weight=1)
        top = ctk.CTkFrame(right, fg_color=P['bg'])
        self._top_frame = top
        top.grid(row=0, column=0, sticky='ew', padx=18, pady=(14,6))
        ctk.CTkLabel(top, text='Пульт SENTINEL', font=ctk.CTkFont(size=17, weight='bold'), text_color=P['text']).pack(side='left')
        for txt, cmd in [('Авто-safe',self._safe_autopilot),('Коуч',lambda:self._tabs.set('Aim Coach')),('Сага',lambda:self._tabs.set('Saga')),('Память',self._goto_memory),('Офлайн',self._toggle_offline)]:
            ctk.CTkButton(self._top_frame, text=txt, width=110, height=28, fg_color='transparent', border_color=P['border'], border_width=1, hover_color=P['border'], text_color=P['blue'], command=cmd).pack(side='left', padx=3)
        self._tabs = ctk.CTkTabview(right, fg_color=P['card'], segmented_button_fg_color=P['bg'], segmented_button_selected_color='#2563eb', segmented_button_unselected_color=P['border'])
        self._tabs.grid(row=1, column=0, sticky='nsew', padx=18, pady=(0,8))
        for t in ['Agent','Aim Coach','Saga','Translator','Memory']: self._tabs.add(t)
        self._tab_agent(); self._tab_aim(); self._tab_saga(); self._tab_translator(); self._tab_memory()
        inp = ctk.CTkFrame(right, fg_color=P['card'], corner_radius=8)
        inp.grid(row=2, column=0, sticky='ew', padx=18, pady=(0,12))
        self._input_entry = ctk.CTkEntry(inp, placeholder_text='Напиши задачу: открой, найди, сделай, помоги...', height=44, font=ctk.CTkFont(size=13), fg_color=P['bg'], border_color=P['border'], state='disabled')
        self._input_entry.pack(side='left', fill='x', expand=True, padx=(10,6), pady=8)
        self._input_entry.bind('<Return>', lambda _: self._send_task())
        self._send_btn = ctk.CTkButton(inp, text='Пуск', width=90, height=44, fg_color='#2563eb', hover_color='#1d4ed8', font=ctk.CTkFont(size=14, weight='bold'), command=self._send_task, state='disabled')
        self._send_btn.pack(side='right', padx=(0,10), pady=8)

    def _tab_agent(self):
        tab = self._tabs.tab('Agent')
        self._log_text = ctk.CTkTextbox(tab, font=ctk.CTkFont(family='Cascadia Code', size=12), fg_color=P['bg'], wrap='word', text_color=P['text'])
        self._log_text.pack(fill='both', expand=True, padx=8, pady=8)
        self._log_text.configure(state='disabled')

    def _tab_aim(self):
        tab = self._tabs.tab('Aim Coach')
        top_bar = ctk.CTkFrame(tab, fg_color=P['bg']); top_bar.pack(fill='x', padx=8, pady=(8,2))
        ctk.CTkLabel(top_bar, text='Игра:', text_color=P['sub'], font=ctk.CTkFont(size=11)).pack(side='left', padx=(0,6))
        self._game_profile_cb = ctk.CTkComboBox(top_bar, values=['Auto Detect','CS2','Valorant','KovaaK','Aim Lab','TF2','Overwatch','FragPunk','Marvel Rivals','Deadlock','Osu','Payday 2','3D Aim Trainer','Aimbeast','Furry Aim Trainer'], height=28, width=180, command=self._on_game_profile)
        self._game_profile_cb.set('Auto Detect'); self._game_profile_cb.pack(side='left')
        ctk.CTkLabel(top_bar, text='  Ранк:', text_color=P['sub'], font=ctk.CTkFont(size=11)).pack(side='left', padx=(6,0))
        self._aim_slbls = {}
        sr = ctk.CTkFrame(tab, fg_color=P['bg']); sr.pack(fill='x', padx=8, pady=(4,4))
        for key, label in [('sessions','Sessions'),('advices','Advices'),('questions','Questions'),('rank','Rank')]:
            card = ctk.CTkFrame(sr, fg_color=P['card'], corner_radius=8); card.pack(side='left', expand=True, fill='x', padx=3)
            ctk.CTkLabel(card, text=label, text_color=P['sub'], font=ctk.CTkFont(size=10)).pack(pady=(6,0))
            lbl = ctk.CTkLabel(card, text='—', text_color=P['blue'], font=ctk.CTkFont(size=16, weight='bold')); lbl.pack(pady=(0,6))
            self._aim_slbls[key] = lbl
        ctk.CTkLabel(tab, text='Last advice:', text_color=P['sub'], font=ctk.CTkFont(size=11)).pack(anchor='w', padx=8, pady=(8,2))
        self._last_advice = ctk.CTkLabel(tab, text='No data', text_color=P['text'], font=ctk.CTkFont(size=14, weight='bold'), wraplength=600, justify='left')
        self._last_advice.pack(anchor='w', padx=8)
        ask = ctk.CTkFrame(tab, fg_color=P['bg']); ask.pack(fill='x', padx=8, pady=8)
        self._aim_q_entry = ctk.CTkEntry(ask, placeholder_text='Ask coach...', height=36, fg_color=P['bg'], state='disabled')
        self._aim_q_entry.pack(side='left', fill='x', expand=True, padx=(0,6))
        self._aim_q_entry.bind('<Return>', lambda _: self._ask_aim())
        ctk.CTkButton(ask, text='Ask', width=100, height=36, fg_color='#2563eb', command=self._ask_aim).pack(side='right')
        ctk.CTkLabel(tab, text='Q&A History:', text_color=P['sub'], font=ctk.CTkFont(size=11)).pack(anchor='w', padx=8)
        self._aim_hist = ctk.CTkTextbox(tab, font=ctk.CTkFont(size=11), fg_color=P['bg'], text_color=P['text'])
        self._aim_hist.pack(fill='both', expand=True, padx=8, pady=(0,8))
        self._aim_hist.configure(state='disabled')

    def _tab_saga(self):
        tab = self._tabs.tab('Saga')
        hdr = ctk.CTkFrame(tab, fg_color=P['bg']); hdr.pack(fill='x', padx=8, pady=(8,4))
        ctk.CTkLabel(hdr, text='Интерактивные саги', font=ctk.CTkFont(size=16, weight='bold'), text_color=P['text']).pack(side='left')
        ctk.CTkButton(hdr, text='Играть', width=100, height=32, fg_color='#2563eb', hover_color='#1d4ed8', command=self._open_saga).pack(side='right', padx=4)
        cards = ctk.CTkFrame(tab, fg_color=P['bg']); cards.pack(fill='x', padx=8, pady=4)
        self._saga_settings = {
            'cyber':('Киберпанк','Неоновый мегаполис 2089. Ты наёмник с имплантами.','#58a6ff'),
            'fantasy':('Фэнтези','Тёмный мир руин, магии и опасных договоров.','#3fb950'),
            'space':('Космос','2847 год. Корабль у края известной галактики.','#d29922'),
            'horror':('Хоррор','Забытый институт, чужие записи и ненадёжная память.','#f85149'),
        }
        self._saga_var = tk.StringVar(value='cyber')
        for key, (title, desc, color) in self._saga_settings.items():
            card = ctk.CTkFrame(cards, fg_color=P['card'], corner_radius=12, border_width=2, border_color=color if key=='cyber' else P['border'])
            card.pack(side='left', expand=True, fill='both', padx=4, pady=4)
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight='bold'), text_color=color).pack(pady=(10,2))
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=10), text_color=P['sub'], wraplength=180, justify='center').pack(pady=(0,10))
            ctk.CTkRadioButton(card, text='', variable=self._saga_var, value=key, fg_color=color, hover_color=color).pack(pady=(0,8))
        ctk.CTkLabel(tab, text='Последний сюжет:', text_color=P['sub'], font=ctk.CTkFont(size=11)).pack(anchor='w', padx=8, pady=(8,2))
        self._saga_preview = ctk.CTkTextbox(tab, font=ctk.CTkFont(size=12), fg_color=P['bg'], text_color=P['text'], wrap='word', height=180)
        self._saga_preview.pack(fill='both', expand=True, padx=8, pady=(0,8))
        self._saga_preview.insert('1.0', 'Выбери сеттинг и нажми «Играть». Сюжет будет на русском.')
        self._saga_preview.configure(state='disabled')

    def _tab_translator(self):
        tab = self._tabs.tab('Translator')
        ctk.CTkLabel(tab, text='Voice translator overlay\nWhisper + Ollama — all local', text_color=P['sub'], font=ctk.CTkFont(size=12), justify='center').pack(pady=(30,14))
        ctk.CTkButton(tab, text='Open Translator', height=46, width=270, fg_color='#2563eb', hover_color='#1d4ed8', font=ctk.CTkFont(size=14, weight='bold'), command=self._open_translator).pack()
        sc = ctk.CTkFrame(tab, fg_color=P['card'], corner_radius=8); sc.pack(padx=50, pady=20, fill='x')
        ctk.CTkLabel(sc, text='Quick settings', font=ctk.CTkFont(size=12, weight='bold'), text_color=P['text']).pack(pady=(10,6))
        row = ctk.CTkFrame(sc, fg_color=P['card']); row.pack(pady=6, padx=20, fill='x')
        ctk.CTkLabel(row, text='Whisper model:', text_color=P['sub'], font=ctk.CTkFont(size=10)).pack(side='left', padx=(0,4))
        self._w_model = ctk.CTkComboBox(row, values=['tiny','base','small','medium'], width=110, command=self._on_whisper_model)
        self._w_model.set('tiny'); self._w_model.pack(side='left', padx=(0,12))
        ctk.CTkLabel(row, text='Device:', text_color=P['sub'], font=ctk.CTkFont(size=10)).pack(side='left', padx=(0,4))
        self._w_dev = ctk.CTkComboBox(row, values=['cuda','cpu'], width=90, command=self._on_whisper_dev)
        self._w_dev.set('cuda'); self._w_dev.pack(side='left')
        ctk.CTkLabel(sc, text='tiny + cuda = best speed', text_color=P['green'], font=ctk.CTkFont(size=11)).pack(pady=(4,10))
        ctk.CTkLabel(tab, text='Recent translations:', text_color=P['sub'], font=ctk.CTkFont(size=11)).pack(anchor='w', padx=20, pady=(6,2))
        self._trans_log = ctk.CTkTextbox(tab, font=ctk.CTkFont(size=12), fg_color=P['bg'], text_color=P['text'])
        self._trans_log.pack(fill='both', expand=True, padx=20, pady=(0,12))
        self._trans_log.configure(state='disabled')

    def _tab_memory(self):
        tab = self._tabs.tab('Memory')
        br = ctk.CTkFrame(tab, fg_color=P['bg']); br.pack(fill='x', padx=8, pady=8)
        ctk.CTkButton(br, text='Refresh', width=110, height=30, command=self._refresh_memory).pack(side='left', padx=4)
        ctk.CTkButton(br, text='Compact', width=90, height=30, fg_color=P['border'], command=self._compact_memory).pack(side='left', padx=4)
        self._mem_text = ctk.CTkTextbox(tab, font=ctk.CTkFont(size=12), fg_color=P['bg'], text_color=P['text'])
        self._mem_text.pack(fill='both', expand=True, padx=8, pady=(0,8))
        self._mem_text.configure(state='disabled')

    def _toggle_agent(self):
        if self._running.is_set():
            self._running.clear()
            self._start_btn.configure(text='Запустить задачу', fg_color='#2563eb')
            self._face.set_state('idle'); self._set_status('Stopped', 'sub')
        else:
            task = self._input_entry.get().strip()
            if not task: self._log('Enter a task!'); return
            self._running.set()
            self._start_btn.configure(text='Stop', fg_color=P['red'])
            self._face.set_state('thinking'); self._set_status('Working', 'green')
            threading.Thread(target=self._agent_loop, args=(task,), daemon=True).start()

    def _send_task(self):
        task = self._input_entry.get().strip()
        if not task or not self._planner: return
        if self._planner.is_question_or_dialog(task):
            self._log(f'User: {task}')
            threading.Thread(target=self._dialog_worker, args=(task,), daemon=True).start()
        else:
            self._toggle_agent()

    def _dialog_worker(self, task):
        self._face.set_state('thinking')
        ans = self._planner.answer_dialog(task)
        self._log(f'AI: {ans}'); self._face.set_state('idle')

    def _agent_loop(self, task):
        if not all([self._planner, self._executor, self._core]): return
        self._planner.reset(); self._executor.no_change_steps = 0; self._executor.smart_pilot.reset()
        self._core.last_task = task; self._log(f'Task: {task}')
        cfg = self._core.cfg; delay = cfg.get('agent_step_delay_sec', 0.3); steps = cfg.get('planner_max_steps', 16)
        run_mode = self._run_mode_cb.get() if hasattr(self, '_run_mode_cb') else 'Авто'
        smart_no_progress_runs = 0
        macro = self._planner.create_macro_plan(task)
        for i, step in enumerate(macro[:4], 1):
            self._log(f'План {i}: {step}')
        start_visual = self._remember_visual("agent_start")
        if self._memory:
            self._memory.remember_agent_event(task, "start", "Агент начал задачу и сохранил визуальную карту.", start_visual)
        if run_mode == 'Только совет':
            self._face.set_state('watching')
            self._set_status('Advice', 'yellow')
            context = self._core.build_screen_context().as_prompt_text()
            ans = self._planner.answer_dialog(f"Задача пользователя: {task}\nЭкран:\n{context}\nДай короткий план действий по-русски, без управления компьютером.")
            self._log(f'Совет: {ans}')
            if self._memory:
                self._memory.remember_agent_event(task, "advice", ans, start_visual)
            self._running.clear()
            self.after(0, lambda: (self._start_btn.configure(text='Запустить задачу', fg_color='#2563eb'), self._face.set_state('idle'), self._set_status('Ready', 'green')))
            return
        for _ in range(steps):
            if not self._running.is_set(): self._log('Agent stopped'); break
            if self._user_took_mouse():
                self._manual_pause_until = time.time() + 1.8
                self._face.set_state('watching'); self._set_status('Watching', 'yellow')
                self._log('Ты взял мышь — я не мешаю, наблюдаю и подстроюсь через секунду.')
                self._remember_visual("user_mouse")
                time.sleep(1.8)
                self._core.invalidate_screen_cache()
                continue
            if self._executor.no_change_steps >= 5:
                if smart_no_progress_runs >= int(cfg.get('agent_max_smart_explore_runs', 2)):
                    self._log('Нет прогресса — ухожу в сон/перепланирование вместо беготни курсором.')
                    self._sleep_replan(task)
                    break
                if time.time() - getattr(self, '_last_smart_explore_time', 0) < 30.0:
                    self._log('SmartExplore на кулдауне — жду.')
                    time.sleep(2.0)
                    continue
                self._log('No progress — exploring screen')
                self._face.set_state('thinking')
                self._last_smart_explore_time = time.time()
                self._executor.smart_pilot.reset(); self._executor.smart_pilot.activate()
                explored = self._executor.execute('SMART_EXPLORE')
                lessons = getattr(self._core, 'last_smart_explore', {}).get('lessons', []) if self._core else []
                if lessons and self._memory:
                    self._memory.remember_insight("SmartExplore: " + "; ".join(lessons[-4:]), source="smart_pilot", confidence=0.75)
                    self._log("SmartExplore вывод: " + "; ".join(lessons[-2:]))
                if not explored:
                    smart_no_progress_runs += 1
                else:
                    smart_no_progress_runs = 0
                self._core.invalidate_screen_cache(); time.sleep(0.5); continue
            ctx = self._core.build_screen_context(max_depth=3)
            desc = ctx.as_prompt_text()
            cmd = self._planner.plan(task, desc); self._log(f'-> {cmd}')
            if cmd.startswith('DIALOG:'): self._log(f'AI: {self._planner.answer_dialog(cmd[7:])}'); break
            if cmd == 'DONE': self._log('Done'); break
            if run_mode == 'По шагам' and cmd.upper().startswith(('CLICK:', 'DBLCLICK:', 'RIGHTCLICK:', 'TYPE:', 'HOTKEY:')):
                if not self._confirm_step(cmd):
                    self._log('Шаг пропущен пользователем.')
                    self._planner.remember_result(cmd, False)
                    continue
            ok = self._executor.execute(cmd); self._face.set_state('active' if ok else 'thinking')
            self._mark_agent_mouse()
            if ok:
                smart_no_progress_runs = 0
            self._planner.remember_result(cmd, ok)
            visual_ref = self._remember_visual("agent_step") if (not ok or cmd.upper().startswith(('CLICK:', 'DBLCLICK:', 'RIGHTCLICK:', 'TYPE:', 'HOTKEY:', 'SMART_EXPLORE'))) else {}
            if self._memory:
                self._memory.remember_command(task, cmd, ok, desc[:300])
                if visual_ref:
                    self._memory.remember_agent_event(task, "step", f"{cmd} -> {'ok' if ok else 'fail'}", visual_ref)
            time.sleep(delay)
        self._running.clear()
        self.after(0, lambda: (self._start_btn.configure(text='Запустить задачу', fg_color='#2563eb'), self._face.set_state('idle'), self._face_title.configure(text='SENTINEL / IDLE'), self._face_sub.configure(text='Ready'), self._set_status('Ready', 'green')))

    def _confirm_step(self, cmd):
        result = {"ok": False}
        event = threading.Event()
        def ask():
            result["ok"] = messagebox.askyesno("SENTINEL: шаг", f"Выполнить команду?\n\n{cmd}")
            event.set()
        self.after(0, ask)
        event.wait(timeout=60)
        return result["ok"]

    def _mark_agent_mouse(self):
        if not pyautogui:
            return
        try:
            self._last_agent_mouse = pyautogui.position()
            self._agent_mouse_owned_until = time.time() + 0.7
        except Exception:
            pass

    def _user_took_mouse(self):
        if not pyautogui or time.time() < self._agent_mouse_owned_until or time.time() < self._manual_pause_until:
            return False
        try:
            pos = pyautogui.position()
        except Exception:
            return False
        if self._last_agent_mouse is None:
            self._last_agent_mouse = pos
            return False
        dx = abs(pos.x - self._last_agent_mouse.x) if hasattr(pos, 'x') else abs(pos[0] - self._last_agent_mouse[0])
        dy = abs(pos.y - self._last_agent_mouse.y) if hasattr(pos, 'y') else abs(pos[1] - self._last_agent_mouse[1])
        moved = dx + dy > 80
        self._last_agent_mouse = pos
        return moved

    def _sleep_replan(self, task):
        try:
            visual = self._remember_visual("agent_replan")
            if self._memory:
                self._memory.remember_insight(f"Агент застрял на задаче: {task}. Нужен другой путь или вопрос пользователю.", source="agent_replan", confidence=0.7)
                self._memory.remember_agent_event(task, "replan", "Агент застрял и ушёл в сон/перепланирование.", visual)
                result = self._memory.sleep_compact(keep_last=self._core.cfg.get('memory_sleep_keep_last', 80))
                for line in result.get('report', {}).get('summary', [])[:3]:
                    self._log('Сон: ' + line)
            self._face.set_state('sleep')
            self._set_status('Replan', 'yellow')
        except Exception as e:
            self._log(f'Replan error: {e}')

    def _remember_visual(self, reason):
        if not self._core or not self._memory:
            return {}
        try:
            snap = self._core.capture_visual_memory_snapshot(reason=reason)
            if snap:
                self._memory.remember_visual_snapshot(snap)
                self._log(f"Visual memory: {snap.get('summary','')}")
            return snap
        except Exception as e:
            self._log(f'Visual memory error: {e}')
            return {}

    def _toggle_aim(self):
        if not self._aim_coach: return
        if self._aim_active.is_set():
            self._aim_active.clear(); self._aim_coach.stop_session()
            if self._aim_overlay: self._aim_overlay.withdraw()
            self._log('Aim coach off')
        else:
            self._aim_active.set(); self._aim_coach.start_session()
            if not self._aim_overlay: self._aim_overlay = AimOverlay(self)
            self._aim_overlay.deiconify(); self._log('Aim coach on')
            threading.Thread(target=self._aim_loop, daemon=True).start()

    def _aim_loop(self):
        poll = self._core.cfg.get('aim_coach_poll_sec', 2.5) if self._core else 2.5
        while self._aim_active.is_set():
            try:
                advice = self._aim_coach.observe_and_advise(); profile = self._aim_coach.game_profile; stats = ''
                ocr_text = ''; scene = ''
                state = self._aim_coach._get_state()
                if state:
                    scene = getattr(state, 'scene', '')
                    ocr_text = getattr(state, 'ocr_text', '')[:80]
                    enemies = getattr(state, 'enemies', [])
                    metrics = self._aim_coach._extract_metrics_from_state(state)
                    parts = []
                    if enemies: parts.append(f'🎯 {len(enemies)}')
                    if metrics.get('accuracy'): parts.append(f'📊 {metrics["accuracy"]}')
                    if metrics.get('score'): parts.append(f'🏆 {metrics["score"]}')
                    if metrics.get('health'): parts.append(f'❤️ {metrics["health"]}')
                    if metrics.get('kills'): parts.append(f'💀 {metrics["kills"]}')
                    if self._memory:
                        s = self._memory.get_aim_stats(); rank = self._memory.aim_rank_guess()
                        parts.append(f'📈 {s["aim_sessions_started"]} | {rank}')
                    stats = ' | '.join(parts)
                if self._aim_overlay:
                    self.after(0, lambda a=advice, p=profile, st=stats, oc=ocr_text, sc=scene:
                               self._aim_overlay.update_advice(a, p, st, oc, sc))
                self.after(0, lambda a=advice: self._last_advice.configure(text=a))
                self.after(0, self._refresh_aim_stats)
            except Exception as e:
                self._log(f'Aim error: {e}')
            time.sleep(poll)

    def _ask_aim(self):
        if not self._aim_coach: return
        q = self._aim_q_entry.get().strip()
        if not q: return
        self._aim_q_entry.delete(0, 'end')
        threading.Thread(target=self._aim_q_worker, args=(q,), daemon=True).start()

    def _aim_q_worker(self, q):
        ans = self._aim_coach.ask_question(q)
        self.after(0, lambda: self._add_aim_hist(q, ans))
        self.after(0, self._refresh_aim_stats)

    def _add_aim_hist(self, q, a):
        self._aim_hist.configure(state='normal')
        self._aim_hist.insert('end', f'Q: {q}\nA: {a}\n\n')
        self._aim_hist.see('end'); self._aim_hist.configure(state='disabled')

    def _refresh_aim_stats(self):
        if not self._memory: return
        s = self._memory.get_aim_stats(); rank = self._memory.aim_rank_guess()
        self._aim_slbls['sessions'].configure(text=str(s.get('aim_sessions_started',0)))
        self._aim_slbls['advices'].configure(text=str(s.get('aim_auto_advices',0)))
        self._aim_slbls['questions'].configure(text=str(s.get('aim_questions',0)))
        self._aim_slbls['rank'].configure(text=rank)

    def _open_translator(self):
        if self._translator_win and self._translator_win.winfo_exists(): self._translator_win.focus(); return
        if not self._core: self._log('Core not loaded'); return
        self._core.cfg['whisper_model_size'] = self._w_model.get(); self._core.cfg['whisper_device'] = self._w_dev.get()
        try:
            from voice_translator import VoiceTranslatorOverlay
            self._translator_win = VoiceTranslatorOverlay(self, self._core, log_callback=self._log_translator)
        except Exception as e: self._log(f'Translator error: {e}')

    def _log_translator(self, msg):
        self._log(msg)
        self.after(0, lambda: (self._trans_log.configure(state='normal'), self._trans_log.insert('end', f'{msg}\n'), self._trans_log.see('end'), self._trans_log.configure(state='disabled')))

    def _refresh_memory(self):
        if not self._memory: return
        self._mem_text.configure(state='normal'); self._mem_text.delete('1.0', 'end')
        for line in self._memory.ui_aim_summary(lines_each=5): self._mem_text.insert('end', line+'\n')
        tasks = self._memory.recent_summary('task_history', 5)
        if tasks:
            self._mem_text.insert('end', '\n-- Recent tasks --\n')
            for t in reversed(tasks): self._mem_text.insert('end', f"• {t.get('task','')[:80]} -> {t.get('outcome','')}\n")
        self._mem_text.configure(state='disabled')

    def _compact_memory(self):
        if not self._memory:
            return
        try:
            keep = self._core.cfg.get('memory_manual_keep_last', 80) if self._core else 80
            rec = self._memory.compact(keep_last=keep, preserve_archive=True, reason='gui_manual_compact')
            self._log(f"Memory compacted safely: archived {rec.get('archived_items',0)} -> {rec.get('archive_path','')}")
        except Exception as e:
            self._log(f'Memory compact error: {e}')
        self._refresh_memory()

    def _toggle_sleep(self):
        self._sleep_mode = not self._sleep_mode
        if self._sleep_mode:
            self._face.set_state('sleep'); self._set_status('Sleep', 'sub'); self._log('Sleep mode: compressing context without data loss')
            threading.Thread(target=self._sleep_worker, daemon=True).start()
        else:
            self._face.set_state('idle'); self._set_status('Ready', 'green'); self._log('Wake up')

    def _sleep_worker(self):
        if not self._memory:
            return
        try:
            self._remember_visual("sleep")
            keep = self._core.cfg.get('memory_sleep_keep_last', 80) if self._core else 80
            result = self._memory.sleep_compact(keep_last=keep)
            self._memory.prune_runtime_context()
            report = result.get('report', {})
            for line in report.get('summary', [])[:4]:
                self._log('Sleep summary: ' + line)
            self.after(0, self._refresh_memory)
        except Exception as e:
            self._log(f'Sleep error: {e}')

    def _toggle_fullscreen(self): self.attributes('-fullscreen', not self.attributes('-fullscreen'))
    def _safe_autopilot(self):
        if self._core: self._core.cfg['offline_mode'] = True
        if self._planner: self._planner.offline_mode = True
        if self._executor: self._executor.offline_mode = True
        self._log('Safe autopilot — internet off')
    def _toggle_offline(self):
        if not self._core: return
        val = not self._core.cfg.get('offline_mode', True); self._core.cfg['offline_mode'] = val
        if self._planner: self._planner.offline_mode = val
        if self._executor: self._executor.offline_mode = val
        self._log(f"Offline: {'ON' if val else 'OFF'}")
    def _goto_memory(self): self._tabs.set('Memory'); self._refresh_memory()
    def _on_game_profile(self, val):
        self._pending_game_profile = val or 'Auto Detect'
        if self._aim_coach:
            self._aim_coach.set_game_profile(self._pending_game_profile)
        self._log(f'Aim profile: {self._pending_game_profile}')

    def _on_theme(self, val):
        m, c = {'Неон':('dark','blue'),'Океан':('dark','blue'),'Закат':('dark','dark-blue'),'Лес':('dark','green'),'Монохром':('dark','blue')}.get(val, ('dark','blue'))
        ctk.set_appearance_mode(m); ctk.set_default_color_theme(c); P.update(_THEMES_P.get(val, {}))
        self._face.recolor(P['blue'], P['border'], P['card'])
        prev = self._face.state; self._face.state = ''; self._face.set_state(prev)
        self._apply_theme_tree()
        self._log(f'Theme: {val}')

    def _apply_theme_tree(self):
        self.configure(fg_color=P['bg'])
        if hasattr(self, '_body'): self._body.configure(bg=P['bg'])
        if hasattr(self, '_hdr'): self._hdr.configure(fg_color=P['card'])
        for widget in self.winfo_children():
            self._theme_widget(widget)

    def _theme_widget(self, widget):
        name = widget.__class__.__name__
        try:
            if name in ('CTkFrame', 'CTkScrollableFrame'):
                widget.configure(fg_color=P['card'], border_color=P['border'])
            elif name == 'CTkTabview':
                widget.configure(fg_color=P['card'], segmented_button_fg_color=P['bg'],
                                 segmented_button_selected_color=P['blue'],
                                 segmented_button_unselected_color=P['border'])
            elif name in ('CTkTextbox', 'CTkEntry'):
                widget.configure(fg_color=P['bg'], text_color=P['text'], border_color=P['border'])
            elif name == 'CTkLabel':
                widget.configure(text_color=P['text'])
            elif name in ('CTkButton', 'CTkComboBox', 'CTkRadioButton'):
                widget.configure(border_color=P['border'])
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._theme_widget(child)
        except Exception:
            pass

    def _on_whisper_model(self, val):
        if self._core: self._core.cfg['whisper_model_size'] = val
    def _on_whisper_dev(self, val):
        if self._core: self._core.cfg['whisper_device'] = val

    def _open_saga(self):
        if not self._core: self._log('Core not loaded'); return
        try:
            from neural_saga import SagaPlayWindow
            setting = self._saga_var.get()
            win = SagaPlayWindow(self, self._core, self._memory, skin=setting, log_fn=self._log)
            self._log(f'Saga started: {self._saga_settings[setting][0]}')
        except Exception as e: self._log(f'Saga error: {e}')

    def _log(self, msg): self._log_q.put(msg)
    def _start_log_drain(self): self._drain()
    def _drain(self):
        try:
            for _ in range(8):
                msg = self._log_q.get_nowait()
                self._log_text.configure(state='normal'); self._log_text.insert('end', f'{msg}\n'); self._log_text.see('end'); self._log_text.configure(state='disabled')
        except (queue.Empty, AttributeError): pass
        self.after(60, self._drain)

    def _set_status(self, text, color):
        c = {'green':P['green'],'yellow':P['yellow'],'red':P['red'],'sub':P['sub']}.get(color, P['sub'])
        self.after(0, lambda: self._status_lbl.configure(text=f'● {text}', text_color=c))

    def _on_close(self):
        self._running.clear(); self._aim_active.clear()
        if self._custodian: self._custodian.stop()
        for w in [self._aim_overlay, self._translator_win]:
            if w:
                try:
                    w.destroy()
                except tk.TclError:
                    pass
        self._face.stop(); self.destroy()
