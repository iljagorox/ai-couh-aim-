# -*- coding: utf-8 -*-
"""
Голосовой перевод (ускоренный) — faster-whisper + Ollama + VAD.
Непрозрачные субтитры, минимум задержек.
"""
import threading
import json
import time
import queue
import re
import customtkinter as ctk
import sounddevice as sd
import ollama
import numpy as np
import tkinter as tk
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, get_speech_timestamps
import torch

DEFAULT_CONFIG = {
    "source_lang": "Русский",
    "target_lang": "Английский",
    "translator_model": "gemma3:4b-it-qat",
    "whisper_model_size": "base",
    "whisper_device": "cpu",
    "prompt_template": (
        "Ты переводчик. Переведи следующий текст с {source} на {target}. "
        "Выведи ТОЛЬКО перевод, без пояснений и кавычек. "
        "Старайся передать суть, убирай странные фразы. "
        "Если целевой язык английский, выделяй ключевые слова *звёздочками*.\n\n"
        "Текст: {text}"
    ),
    "subtitle_font": "Comic Sans MS",
    "subtitle_font_size": 36,
    "subtitle_text_color": "#FFA500",
    "subtitle_highlight_color": "#FFFF00",
    "subtitle_auto_clear_sec": 4,
    "similarity_threshold": 0.85,
    "vad_silence_duration": 0.4,
    "vad_min_speech_duration": 0.2,
    "vad_max_speech_duration": 10.0,
    "ollama_num_predict_voice": 256,
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

        self.source_lang = self.config["source_lang"]
        self.target_lang = self.config["target_lang"]
        self.translator_model = self.config["translator_model"]
        self.prompt_template = self.config["prompt_template"]
        self.threshold = self.config["similarity_threshold"]
        self.num_predict_voice = self.config.get("ollama_num_predict_voice", 256)

        self.is_recording = False
        self.stream = None
        self.audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._last_text = ""
        self._hide_timer = None

        self.sample_rate = 16000
        self.vad_silence_duration = self.config["vad_silence_duration"]
        self.vad_min_speech_duration = self.config["vad_min_speech_duration"]
        self.vad_max_speech_duration = self.config["vad_max_speech_duration"]

        self.whisper = None
        self.ready = False
        self._init_whisper_async()

        self.vad_model = None
        self._init_vad()

        self.title("Голосовой перевод (быстрый)")
        self.geometry("400x380")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Окно субтитров (непрозрачное)
        self.subtitle_win = ctk.CTkToplevel(self)
        self.subtitle_win.title("Субтитры")
        self.subtitle_win.geometry("1000x220")
        self.subtitle_win.attributes("-topmost", True)
        self.subtitle_win.overrideredirect(True)
        self.subtitle_win.configure(fg_color="#0a0a0a")
        self.subtitle_win.withdraw()
        self.subtitle_win.bind("<Button-1>", self._start_move)
        self.subtitle_win.bind("<B1-Motion>", self._on_move)
        self._load_subtitle_position()

        self.text_frame = ctk.CTkFrame(self.subtitle_win, fg_color="transparent")
        self.text_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.subtitle_text = tk.Text(
            self.text_frame,
            font=(self.config["subtitle_font"], self.config["subtitle_font_size"]),
            fg=self.config["subtitle_text_color"],
            bg="#0a0a0a",
            wrap="word",
            relief="flat",
            highlightthickness=0,
            borderwidth=0
        )
        self.subtitle_text.pack(fill="both", expand=True)
        self.subtitle_text.tag_configure("center", justify="center")
        self.subtitle_text.tag_configure("highlight",
                                         foreground=self.config["subtitle_highlight_color"],
                                         font=(self.config["subtitle_font"], self.config["subtitle_font_size"], "bold"))
        self.subtitle_text.insert("1.0", "", "center")
        self.subtitle_text.config(state="disabled")

        self._build_ui()

    # ---------- инициализация ----------
    def _init_vad(self):
        try:
            self.vad_model = load_silero_vad(onnx=True)
            self.log("🎙 Silero VAD загружен")
        except Exception as e:
            self.log(f"⚠️ VAD не загружен: {e}")
            self.vad_model = None

    def _init_whisper_async(self):
        threading.Thread(target=self._init_whisper, daemon=True).start()

    def _init_whisper(self):
        try:
            if self.config["whisper_device"] == "cuda" and torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
            else:
                device = "cpu"
                compute_type = "int8"
            self.whisper = WhisperModel(
                self.config["whisper_model_size"],
                device=device,
                compute_type=compute_type,
                cpu_threads=4,
                num_workers=1
            )
            self.ready = True
            self._update_status("✅ Готов", False)
            self.record_btn.configure(state="normal")
            self.log(f"Whisper ({self.config['whisper_model_size']}) на {device}")
        except Exception as e:
            self._update_status(f"❌ Whisper: {e}", True)

    # ---------- UI ----------
    def _build_ui(self):
        ctk.CTkLabel(self, text="Голосовой перевод (быстрый)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        frame = ctk.CTkFrame(self)
        frame.pack(pady=5, padx=20, fill="x")
        ctk.CTkLabel(frame, text="С какого:").grid(row=0, column=0, padx=5)
        self.source_combo = ctk.CTkComboBox(frame, values=["Русский", "Английский"], command=self._on_source_change)
        self.source_combo.set(self.source_lang)
        self.source_combo.grid(row=0, column=1, padx=5)
        ctk.CTkLabel(frame, text="На какой:").grid(row=1, column=0, padx=5)
        self.target_combo = ctk.CTkComboBox(frame, values=["Английский", "Русский"], command=self._on_target_change)
        self.target_combo.set(self.target_lang)
        self.target_combo.grid(row=1, column=1, padx=5)
        self.status = ctk.CTkLabel(self, text="⚪ Загрузка...", font=ctk.CTkFont(size=12))
        self.status.pack(pady=5)
        self.record_btn = ctk.CTkButton(self, text="🎤 Записать", command=self._toggle_recording, height=45, state="disabled")
        self.record_btn.pack(pady=10)
        self.clear_btn = ctk.CTkButton(self, text="🧹 Очистить контекст", command=self._clear_context, height=30)
        self.clear_btn.pack(pady=5)
        self.close_btn = ctk.CTkButton(self, text="❌ Закрыть", command=self.on_close, height=30)
        self.close_btn.pack(pady=5)

    # ---------- запись ----------
    def _toggle_recording(self):
        if not self.ready: return
        if self.is_recording: self._stop_recording()
        else: self._start_recording()

    def _start_recording(self):
        self.is_recording = True
        self._stop_event.clear()
        self.audio_queue = queue.Queue()
        self._update_status("🎤 Запись...", False)
        self.record_btn.configure(text="⏹ Остановить", fg_color="red")
        self.subtitle_win.deiconify()
        self._clear_subtitle()
        def callback(indata, frames, time_info, status):
            if status: self.log(f"Audio status: {status}")
            if self.is_recording: self.audio_queue.put(indata.copy())
        try:
            self.stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16', callback=callback, blocksize=512)
            self.stream.start()
        except Exception as e:
            self._update_status(f"❌ Микрофон: {e}", True)
            self._stop_recording()
            return
        threading.Thread(target=self._audio_processing_loop, daemon=True).start()

    def _stop_recording(self):
        self.is_recording = False
        self._stop_event.set()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.record_btn.configure(text="🎤 Записать", fg_color="#2a5f78")
        self._update_status("✅ Остановлено", False)

    # ---------- VAD + Whisper ----------
    def _audio_processing_loop(self):
        audio_buffer = np.array([], dtype=np.int16)
        min_speech = int(self.vad_min_speech_duration * self.sample_rate)
        max_speech = int(self.vad_max_speech_duration * self.sample_rate)
        silence_thresh = int(self.vad_silence_duration * self.sample_rate)

        while self.is_recording and not self._stop_event.is_set():
            try:
                chunk = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            chunk_flat = chunk.flatten()
            audio_buffer = np.concatenate([audio_buffer, chunk_flat])

            if self.vad_model is not None:
                audio_float = audio_buffer.astype(np.float32) / 32768.0
                speech_ts = get_speech_timestamps(audio_float, self.vad_model, sampling_rate=self.sample_rate,
                                                  threshold=0.5, min_speech_duration_ms=int(self.vad_min_speech_duration*1000),
                                                  min_silence_duration_ms=int(self.vad_silence_duration*1000))
                if speech_ts:
                    last = speech_ts[-1]
                    if len(audio_buffer) >= last['end'] + silence_thresh:
                        seg = audio_buffer[last['start']:last['end']]
                        if len(seg) >= min_speech:
                            self._process_speech_segment(seg)
                        audio_buffer = audio_buffer[last['end']:]
                    else:
                        self._update_status("🔴 Говорит...", False)
                else:
                    if len(audio_buffer) > 5*self.sample_rate:
                        audio_buffer = audio_buffer[-self.sample_rate:]
            else:
                if len(audio_buffer) > self.sample_rate * 1.0:
                    self._process_speech_segment(audio_buffer)
                    audio_buffer = np.array([], dtype=np.int16)
            if len(audio_buffer) > max_speech * 2:
                audio_buffer = audio_buffer[-max_speech:]

        if len(audio_buffer) > min_speech and self.is_recording:
            self._process_speech_segment(audio_buffer)

    def _process_speech_segment(self, audio_np):
        if audio_np is None or len(audio_np) == 0: return
        threading.Thread(target=self._recognize_and_translate, args=(audio_np,), daemon=True).start()

    def _recognize_and_translate(self, audio_np):
        if not self.whisper: return
        audio_float = audio_np.astype(np.float32) / 32768.0
        try:
            segments, _ = self.whisper.transcribe(audio_float, language="ru", beam_size=1, vad_filter=False)
            text = " ".join(seg.text for seg in segments).strip()
        except Exception as e:
            self.log(f"Ошибка Whisper: {e}")
            return
        if len(text) < 3: return
        if self._similarity(text, self._last_text) > self.threshold:
            self.log("🔁 Повтор")
            return
        self._last_text = text
        self.log(f"📝 {text}")
        self._update_status("🔄 Перевод...", False)

        prompt = self.prompt_template.format(source=self.source_lang, target=self.target_lang, text=text)
        try:
            resp = ollama.chat(model=self.translator_model, messages=[{"role":"user","content":prompt}],
                               options={"temperature":0.3, "num_predict": self.num_predict_voice}, keep_alive=-1)
            trans = resp["message"]["content"].strip().strip('"\'')
            if not trans: trans = "[Ошибка]"
            self._show_subtitle(trans)
            self.log(f"🌐 {trans}")
            self._update_status("🎤 Запись..." if self.is_recording else "✅ Готово", False)
        except Exception as e:
            self.log(f"❌ Перевод: {e}")
            self._update_status("❌ Ошибка перевода", True)

    # ---------- вспомогательные ----------
    def _similarity(self, a, b):
        wa, wb = set(a.lower().split()), set(b.lower().split())
        if not wa or not wb: return 0
        return len(wa & wb) / len(wa | wb)

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
        if self._hide_timer: self.after_cancel(self._hide_timer)
        if self.config["subtitle_auto_clear_sec"] > 0:
            self._hide_timer = self.after(int(self.config["subtitle_auto_clear_sec"]*1000), self._clear_subtitle)

    def _clear_subtitle(self):
        self.subtitle_text.config(state="normal")
        self.subtitle_text.delete("1.0", "end")
        self.subtitle_text.config(state="disabled")

    def _clear_context(self):
        self.log("🧹 Контекст очищен (не используется)")

    def _update_status(self, text, is_error):
        self.after(0, lambda: self._safe_update_status(text, is_error))
    def _safe_update_status(self, text, is_error):
        try:
            if self.winfo_exists():
                self.status.configure(text=text, text_color="red" if is_error else "green")
        except: pass

    def _on_source_change(self, v): self.source_lang = v
    def _on_target_change(self, v): self.target_lang = v
    def _load_subtitle_position(self):
        try:
            with open("subtitle_pos.json","r") as f:
                pos = json.load(f); self.subtitle_win.geometry(f"+{pos['x']}+{pos['y']}")
        except: pass
    def _save_subtitle_position(self):
        try:
            x, y = self.subtitle_win.winfo_x(), self.subtitle_win.winfo_y()
            with open("subtitle_pos.json","w") as f: json.dump({"x":x,"y":y}, f)
        except: pass
    def _start_move(self, e): self._drag_x, self._drag_y = e.x, e.y
    def _on_move(self, e):
        x = self.subtitle_win.winfo_x() + (e.x - self._drag_x)
        y = self.subtitle_win.winfo_y() + (e.y - self._drag_y)
        self.subtitle_win.geometry(f"+{x}+{y}")
        self._save_subtitle_position()
    def on_close(self):
        self._stop_recording()
        self._save_subtitle_position()
        self.subtitle_win.destroy()
        self.destroy()