# -*- coding: utf-8 -*-
import threading
import json
import time
import queue
import re
from pathlib import Path
import customtkinter as ctk
import sounddevice as sd
import ollama
import numpy as np
import tkinter as tk
from faster_whisper import WhisperModel
try:
    from silero_vad import load_silero_vad, get_speech_timestamps
except Exception:
    load_silero_vad = get_speech_timestamps = None
import torch

P = {'border': '#2d3746', 'sub': '#8b949e'}

DEFAULT_CONFIG = {
    "source_lang": "Русский",
    "target_lang": "Английский",
    "translator_model": "",
    "whisper_model_size": "tiny",
    "whisper_device": "cpu",
    "prompt_template": (
        "Ты переводчик. Переведи следующий текст с {source} на {target}. "
        "Выведи ТОЛЬКО перевод, без пояснений и кавычек. "
        "Старайся передать суть, убирай странные фразы. "
        "Если целевой язык английский, выделяй ключевые слова *звёздочками*.\n\n"
        "Текст: {text}"
    ),
    "subtitle_font": "Comic Sans MS",
    "subtitle_font_size": 32,
    "subtitle_original_size": 22,
    "subtitle_text_color": "#FFA500",
    "subtitle_original_color": "#8B949E",
    "subtitle_highlight_color": "#FFFF00",
    "subtitle_auto_clear_sec": 6,
    "similarity_threshold": 0.85,
    "vad_silence_duration": 0.3,
    "vad_min_speech_duration": 0.15,
    "vad_max_speech_duration": 8.0,
    "ollama_num_predict_voice": 100,
}

class VoiceTranslatorOverlay(ctk.CTkToplevel):
    def __init__(self, master, core, log_callback=None):
        super().__init__(master)
        self.core = core
        self.log = log_callback or print
        self.config = {**DEFAULT_CONFIG}
        for k in DEFAULT_CONFIG:
            if k in core.cfg:
                self.config[k] = core.cfg[k]
        if "voice_translator_model" in core.cfg:
            self.config["translator_model"] = core.cfg["voice_translator_model"]
        if "voice_source_name" in core.cfg:
            self.config["source_lang"] = core.cfg["voice_source_name"]
        if "voice_target_name" in core.cfg:
            self.config["target_lang"] = core.cfg["voice_target_name"]
        if "voice_subtitle_font" in core.cfg:
            self.config["subtitle_font"] = core.cfg["voice_subtitle_font"]
        if "voice_font_size" in core.cfg:
            self.config["subtitle_font_size"] = core.cfg["voice_font_size"]
        if "voice_text_color" in core.cfg:
            self.config["subtitle_text_color"] = core.cfg["voice_text_color"]

        if not self.config.get("translator_model"):
            self.config["translator_model"] = core.cfg.get("translator_model") or core.cfg.get("voice_translator_model") or core.cfg.get("brain_model", "")

        self.source_lang = self.config["source_lang"]
        self.target_lang = self.config["target_lang"]
        self.translator_model = self.config["translator_model"]
        self.prompt_template = self.config["prompt_template"]
        self.threshold = self.config["similarity_threshold"]
        self.num_predict_voice = self.config.get("ollama_num_predict_voice", 100)

        self.is_recording = False
        self.stream = None
        self.audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._last_text = ""
        self._original_text = ""
        self._hide_timer = None
        self._trans_pending = False
        self._last_audio_time = 0

        self.sample_rate = 16000
        self.whisper = None
        self.ready = False
        self.vad_model = None
        self._init_vad()
        self._init_whisper_async()

        self.title("Голосовой перевод")
        self.geometry("360x280")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.subtitle_win = ctk.CTkToplevel(self)
        self.subtitle_win.title("Субтитры")
        self.subtitle_win.geometry("900x180")
        self.subtitle_win.attributes("-topmost", True)
        self.subtitle_win.overrideredirect(True)
        self.subtitle_win.configure(fg_color="#0a0a0a")
        self.subtitle_win.attributes("-transparentcolor", "#0a0a0a")
        self.subtitle_win.wm_attributes("-alpha", 0.85)
        self.subtitle_win.bind("<Button-1>", self._start_move)
        self.subtitle_win.bind("<B1-Motion>", self._on_move)
        self._load_subtitle_position()

        self.subtitle_text = tk.Text(
            self.subtitle_win,
            font=(self.config["subtitle_font"], self.config["subtitle_font_size"]),
            fg=self.config["subtitle_text_color"],
            bg="#0a0a0a",
            wrap="word",
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            height=2,
        )
        self.subtitle_text.pack(fill="both", expand=True, padx=12, pady=(4, 0))
        self.subtitle_text.tag_configure("center", justify="center")
        self.subtitle_text.tag_configure("highlight",
                                         foreground=self.config["subtitle_highlight_color"],
                                         font=(self.config["subtitle_font"], self.config["subtitle_font_size"], "bold"))
        self.subtitle_text.insert("1.0", "", "center")
        self.subtitle_text.config(state="disabled")

        self.original_text = tk.Text(
            self.subtitle_win,
            font=(self.config["subtitle_font"], self.config["subtitle_original_size"]),
            fg=self.config["subtitle_original_color"],
            bg="#0a0a0a",
            wrap="word",
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            height=1,
        )
        self.original_text.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.original_text.tag_configure("center", justify="center")
        self.original_text.insert("1.0", "", "center")
        self.original_text.config(state="disabled")

        self._build_ui()
        self._auto_start()

    def _init_vad(self):
        if load_silero_vad is None:
            self.log("Silero VAD not installed")
            self.vad_model = None
            return
        try:
            self.vad_model = load_silero_vad(onnx=True)
            self.log("Silero VAD loaded")
        except Exception as e:
            self.log(f"VAD error: {e}")
            self.vad_model = None

    def _init_whisper_async(self):
        threading.Thread(target=self._init_whisper, daemon=True).start()

    def _init_whisper(self):
        try:
            device = "cpu"
            compute_type = "int8"
            if self.config["whisper_device"] == "cuda" and torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
            self.whisper = WhisperModel(
                "tiny",
                device=device,
                compute_type=compute_type,
                cpu_threads=2,
                num_workers=1
            )
            self.ready = True
            self._update_status("Готов", False)
            self.log(f"Whisper tiny on {device}")
        except Exception as e:
            self._update_status(f"Whisper: {e}", True)

    def _build_ui(self):
        ctk.CTkLabel(self, text="Перевод в реальном времени", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(10, 4))
        self.status = ctk.CTkLabel(self, text="Загрузка...", font=ctk.CTkFont(size=11))
        self.status.pack(pady=2)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=6)
        self.source_combo = ctk.CTkComboBox(row, values=["Русский", "Английский", "Немецкий", "Французский", "Испанский"],
                                              width=120, command=self._on_source_change)
        self.source_combo.set(self.source_lang)
        self.source_combo.pack(side="left", padx=4)
        ctk.CTkLabel(row, text="→", font=ctk.CTkFont(size=16)).pack(side="left", padx=4)
        self.target_combo = ctk.CTkComboBox(row, values=["Английский", "Русский", "Немецкий", "Французский", "Испанский"],
                                              width=120, command=self._on_target_change)
        self.target_combo.set(self.target_lang)
        self.target_combo.pack(side="left", padx=4)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=8)
        self.lang_btn = ctk.CTkButton(btn_row, text="Автоопределение языка", height=32, fg_color=P["border"], hover_color="#444c56",
                                       font=ctk.CTkFont(size=11), command=self._toggle_auto_lang)
        self.lang_btn.pack(side="left", padx=4)
        self.clear_btn = ctk.CTkButton(btn_row, text="Очистить", height=32, fg_color=P["border"], hover_color="#444c56",
                                        font=ctk.CTkFont(size=11), command=self._clear_context)
        self.clear_btn.pack(side="left", padx=4)
        self.close_btn = ctk.CTkButton(btn_row, text="Закрыть", height=32, fg_color="#f85149", hover_color="#da3633",
                                        font=ctk.CTkFont(size=11), command=self.on_close)
        self.close_btn.pack(side="left", padx=4)

        info = ctk.CTkLabel(self, text="Микрофон включён — говорит в микрофон", font=ctk.CTkFont(size=10),
                             text_color=P["sub"])
        info.pack(pady=(4, 2))

    def _auto_start(self):
        def wait_and_start():
            for _ in range(20):
                if self.ready:
                    self.after(0, self._start_recording)
                    return
                time.sleep(0.2)
        threading.Thread(target=wait_and_start, daemon=True).start()

    def _toggle_recording(self):
        pass

    def _start_recording(self):
        if self.is_recording: return
        self.is_recording = True
        self._stop_event.clear()
        self._last_audio_time = time.time()
        self.audio_queue = queue.Queue()
        self.subtitle_win.deiconify()
        self._update_status("Слушаю...", False)

        def callback(indata, frames, time_info, status):
            if status: self.log(f"Audio: {status}")
            if self.is_recording:
                self.audio_queue.put(indata.copy())
                self._last_audio_time = time.time()

        try:
            self.stream = sd.InputStream(samplerate=self.sample_rate, channels=1,
                                          dtype='int16', callback=callback, blocksize=256)
            self.stream.start()
        except Exception as e:
            self._update_status(f"Микрофон: {e}", True)
            self._stop_recording()
            return

        threading.Thread(target=self._audio_processing_loop, daemon=True).start()
        threading.Thread(target=self._vad_watchdog, daemon=True).start()
        self.log("Recording started")

    def _vad_watchdog(self):
        while self.is_recording and not self._stop_event.is_set():
            if time.time() - self._last_audio_time > 3.0:
                self._update_status("Ожидание микрофона...", False)
            time.sleep(1.0)

    def _stop_recording(self):
        self.is_recording = False
        self._stop_event.set()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self._update_status("Остановлено", False)

    def _audio_processing_loop(self):
        audio_buffer = np.array([], dtype=np.int16)
        min_speech = int(self.config["vad_min_speech_duration"] * self.sample_rate)
        max_speech = int(self.config["vad_max_speech_duration"] * self.sample_rate)
        silence_thresh = int(self.config["vad_silence_duration"] * self.sample_rate)

        while self.is_recording and not self._stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.05)
            except queue.Empty:
                if len(audio_buffer) > self.sample_rate * 2:
                    audio_buffer = audio_buffer[-self.sample_rate:]
                continue
            chunk_flat = chunk.flatten()
            audio_buffer = np.concatenate([audio_buffer, chunk_flat])

            if self.vad_model is not None and len(audio_buffer) > self.sample_rate // 4:
                audio_float = audio_buffer.astype(np.float32) / 32768.0
                try:
                    speech_ts = get_speech_timestamps(audio_float, self.vad_model, sampling_rate=self.sample_rate,
                                                      threshold=0.3, min_speech_duration_ms=int(self.config["vad_min_speech_duration"]*1000),
                                                      min_silence_duration_ms=int(self.config["vad_silence_duration"]*1000))
                except Exception:
                    speech_ts = []
                if speech_ts:
                    last = speech_ts[-1]
                    self._update_status("Говорит...", False)
                    if len(audio_buffer) >= last['end'] + silence_thresh:
                        seg = audio_buffer[last['start']:last['end']]
                        if len(seg) >= min_speech:
                            self._process_speech_segment(seg)
                        audio_buffer = audio_buffer[last['end']:]
                else:
                    if len(audio_buffer) > max_speech:
                        audio_buffer = audio_buffer[-self.sample_rate:]
            elif self.vad_model is None:
                if len(audio_buffer) > self.sample_rate * 0.6:
                    self._process_speech_segment(audio_buffer)
                    audio_buffer = np.array([], dtype=np.int16)

            if len(audio_buffer) > max_speech * 2:
                audio_buffer = audio_buffer[-max_speech:]

        if len(audio_buffer) > min_speech and self.is_recording:
            self._process_speech_segment(audio_buffer)

    def _process_speech_segment(self, audio_np):
        if audio_np is None or len(audio_np) < 100: return
        if self._trans_pending: return
        self._trans_pending = True
        threading.Thread(target=self._recognize_and_translate, args=(audio_np,), daemon=True).start()

    def _recognize_and_translate(self, audio_np):
        if not self.whisper:
            self._trans_pending = False
            return
        audio_float = audio_np.astype(np.float32) / 32768.0
        text = ""
        try:
            segments, _ = self.whisper.transcribe(audio_float, language=None, beam_size=1, vad_filter=False, temperature=0)
            text = " ".join(seg.text for seg in segments).strip()
        except Exception as e:
            self.log(f"Whisper: {e}")

        self._trans_pending = False
        if len(text) < 2:
            return

        if self._similarity(text, self._last_text) > self.threshold:
            return
        self._last_text = text

        self.after(0, lambda t=text: self._show_original(t))
        self.log(f"[{text}]")

        prompt = self.prompt_template.format(source=self.source_lang, target=self.target_lang, text=text)
        try:
            resp = ollama.chat(model=self.translator_model, messages=[{"role": "user", "content": prompt}],
                               options={"temperature": 0.2, "num_predict": self.num_predict_voice},
                               keep_alive=self.core.brain_keep_alive() if hasattr(self.core, "brain_keep_alive") else 0)
            trans = resp["message"]["content"].strip().strip('"\'')
            if not trans:
                trans = "[...]"
            self.after(0, lambda t=trans: self._show_subtitle(t))
            self.log(f"→ {trans}")
        except Exception as e:
            self.log(f"Translate: {e}")
            self.after(0, lambda: self._show_subtitle("❌"))
        finally:
            self._update_status("Слушаю..." if self.is_recording else "Готов", False)

    def _similarity(self, a, b):
        wa, wb = set(a.lower().split()), set(b.lower().split())
        if not wa or not wb:
            return 0
        return len(wa & wb) / len(wa | wb)

    def _show_original(self, text):
        self.original_text.config(state="normal")
        self.original_text.delete("1.0", "end")
        self.original_text.insert("end", text, "center")
        self.original_text.config(state="disabled")

    def _show_subtitle(self, text):
        self.subtitle_text.config(state="normal")
        self.subtitle_text.delete("1.0", "end")
        parts = re.split(r'(\*[^*]+\*)', text)
        for part in parts:
            if part.startswith('*') and part.endswith('*'):
                self.subtitle_text.insert("end", part[1:-1], "highlight")
            else:
                self.subtitle_text.insert("end", part, "center")
        self.subtitle_text.config(state="disabled")
        self.subtitle_win.deiconify()
        if self._hide_timer:
            self.after_cancel(self._hide_timer)
        if self.config["subtitle_auto_clear_sec"] > 0:
            self._hide_timer = self.after(int(self.config["subtitle_auto_clear_sec"]*1000), self._clear_all)

    def _clear_all(self):
        self.subtitle_text.config(state="normal")
        self.subtitle_text.delete("1.0", "end")
        self.subtitle_text.config(state="disabled")
        self.original_text.config(state="normal")
        self.original_text.delete("1.0", "end")
        self.original_text.config(state="disabled")

    def _clear_context(self):
        self._last_text = ""
        self._clear_all()
        self.log("Context cleared")

    def _toggle_auto_lang(self):
        self.log("Auto language detection (placeholder)")

    def _update_status(self, text, is_error=False):
        self.after(0, lambda: self._safe_status(text, is_error))

    def _safe_status(self, text, is_error):
        try:
            if self.winfo_exists():
                self.status.configure(text=text, text_color="#f85149" if is_error else "#3fb950")
        except tk.TclError:
            pass
        except Exception:
            pass

    def _on_source_change(self, v):
        self.source_lang = v

    def _on_target_change(self, v):
        self.target_lang = v

    def _subtitle_pos_path(self):
        return Path(__file__).parent / "subtitle_pos.json"

    def _load_subtitle_position(self):
        try:
            p = json.loads(self._subtitle_pos_path().read_text(encoding="utf-8"))
            self.subtitle_win.geometry(f"+{int(p['x'])}+{int(p['y'])}")
        except Exception:
            pass

    def _save_subtitle_position(self):
        try:
            x, y = self.subtitle_win.winfo_x(), self.subtitle_win.winfo_y()
            self._subtitle_pos_path().write_text(json.dumps({"x": x, "y": y}), encoding="utf-8")
        except Exception:
            pass

    def _start_move(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _on_move(self, e):
        x = self.subtitle_win.winfo_x() + (e.x - self._drag_x)
        y = self.subtitle_win.winfo_y() + (e.y - self._drag_y)
        self.subtitle_win.geometry(f"+{x}+{y}")
        self._save_subtitle_position()

    def on_close(self):
        self._stop_recording()
        self._save_subtitle_position()
        if hasattr(self, 'whisper') and self.whisper:
            try:
                del self.whisper
            except Exception:
                pass
            self.whisper = None
        self.subtitle_win.destroy()
        self.destroy()


