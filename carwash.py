#!/usr/bin/env python3
"""carwash.py — NeonForge vocal chain CLI controller for Reaper via OSC"""

import json
import queue
import threading
import numpy as np
import sounddevice as sd
import whisper
import anthropic
from pythonosc import udp_client
from textual.app import App, ComposeResult
from textual.widgets import Button, Footer, Header, Label, Log
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive

# ── Config ───────────────────────────────────────────────────────────────────
REAPER_HOST = "127.0.0.1"
REAPER_PORT = 8000
SAMPLE_RATE  = 16000
CHUNK_SIZE   = 1024
ENERGY_THRESHOLD = 0.01
SILENCE_CHUNKS   = 30   # ~2s at 16kHz/1024

osc = udp_client.SimpleUDPClient(REAPER_HOST, REAPER_PORT)

# ── Presets ──────────────────────────────────────────────────────────────────
PRESETS = {
    "Modern Pop Crisp": {
        "gate_thresh": -45.0, "tone_low": -2.5, "tone_mid": -1.0,
        "tone_high": 3.0, "tone_air": 4.5, "space_sfx_level": 0.15,
        "space_decay_ms": 1500, "automix_target": -14.0,
    },
    "Vintage Tube Warmth": {
        "gate_thresh": -55.0, "tone_low": 2.0, "tone_mid": -2.5,
        "tone_high": -1.5, "tone_air": 0.0, "fusion_comp": 0.45,
        "automix_target": -16.0,
    },
    "Astro Infinite Space": {
        "gate_thresh": -40.0, "tone_low": -4.0, "tone_mid": 1.0,
        "tone_high": 2.0, "tone_air": 5.0, "fusion_comp": 0.70,
        "drive_sat": 0.3, "space_sfx_level": 1.0,
        "space_decay_ms": 2800, "automix_target": -14.0,
    },
    "Radio Broadcast Dry": {
        "tone_low": 1.5, "tone_mid": 0.0, "tone_high": 1.5,
        "fusion_comp": 0.60, "drive_sat": 0.05,
        "space_sfx_level": 0.0, "automix_target": -16.0,
    },
    "Aggressive FET Grit": {
        "gate_thresh": -30.0, "tone_low": -3.0, "tone_mid": 4.5,
        "tone_high": 2.0, "tone_air": 1.5,
        "space_sfx_level": 0.10, "automix_target": -12.0,
    },
}

PRESET_NAMES = list(PRESETS.keys())

# ── Reaper OSC param map  (path, min, max) ───────────────────────────────────
# Adjust FX slot numbers to match your Reaper chain order
PARAM_MAP = {
    "gate_thresh":     ("/fx/1/param/0/value", -80.0,   0.0),
    "tone_low":        ("/fx/2/param/0/value", -12.0,  12.0),
    "tone_mid":        ("/fx/2/param/1/value", -12.0,  12.0),
    "tone_high":       ("/fx/2/param/2/value", -12.0,  12.0),
    "tone_air":        ("/fx/2/param/3/value",  -6.0,  12.0),
    "fusion_comp":     ("/fx/3/param/0/value",   0.0,   1.0),
    "drive_sat":       ("/fx/4/param/0/value",   0.0,   1.0),
    "space_sfx_level": ("/fx/5/param/0/value",   0.0,   1.0),
    "space_decay_ms":  ("/fx/5/param/1/value",   0.0, 6000.0),
    "automix_target":  ("/fx/6/param/0/value", -30.0,   0.0),
}

def _norm(v, lo, hi):
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))

def send_preset(name: str):
    for k, v in PRESETS[name].items():
        if k in PARAM_MAP:
            path, lo, hi = PARAM_MAP[k]
            osc.send_message(path, _norm(v, lo, hi))

def send_param(key: str, value: float):
    if key in PARAM_MAP:
        path, lo, hi = PARAM_MAP[key]
        osc.send_message(path, _norm(value, lo, hi))

def transport(cmd: str):
    osc.send_message(f"/transport/{cmd}", 1)

# ── Voice / Whisper / Claude ─────────────────────────────────────────────────
_whisper = None
_claude  = None

def load_models():
    global _whisper, _claude
    _whisper = whisper.load_model("base")
    _claude  = anthropic.Anthropic()

INTENT_PROMPT = """You control a vocal chain in Reaper. Given a voice command return ONLY valid JSON:
{"action":"preset","name":"<name>"}
{"action":"param","key":"<key>","value":<float>}
{"action":"transport","cmd":"play"|"stop"|"record"}
{"action":"none"}

Preset names: Modern Pop Crisp, Vintage Tube Warmth, Astro Infinite Space, Radio Broadcast Dry, Aggressive FET Grit
Param keys: gate_thresh tone_low tone_mid tone_high tone_air fusion_comp drive_sat space_sfx_level space_decay_ms automix_target"""

def parse_intent(text: str) -> dict:
    r = _claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        system=INTENT_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    return json.loads(r.content[0].text)

def audio_listener(log_q: queue.Queue, active: threading.Event):
    audio_buf = []
    silence_n = 0
    recording = False

    def cb(indata, frames, t, status):
        nonlocal audio_buf, silence_n, recording
        chunk = indata[:, 0]
        energy = float(np.sqrt(np.mean(chunk ** 2)))
        if energy > ENERGY_THRESHOLD:
            recording = True
            silence_n = 0
            audio_buf.append(chunk.copy())
        elif recording:
            audio_buf.append(chunk.copy())
            silence_n += 1
            if silence_n >= SILENCE_CHUNKS:
                audio = np.concatenate(audio_buf).astype(np.float32)
                audio_buf.clear()
                silence_n = 0
                recording = False
                try:
                    text = _whisper.transcribe(audio, fp16=False)["text"].strip()
                    if text:
                        log_q.put(("voice", text))
                        intent = parse_intent(text)
                        log_q.put(("intent", intent))
                        _execute(intent)
                except Exception as e:
                    log_q.put(("error", str(e)))

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        blocksize=CHUNK_SIZE, callback=cb):
        while active.is_set():
            sd.sleep(200)

def _execute(intent: dict):
    a = intent.get("action")
    if a == "preset" and intent.get("name") in PRESETS:
        send_preset(intent["name"])
    elif a == "param":
        send_param(intent["key"], float(intent["value"]))
    elif a == "transport":
        transport(intent["cmd"])

# ── TUI ──────────────────────────────────────────────────────────────────────
class CarwashApp(App):
    CSS = """
    Screen            { background: #0a0a0a; }
    Label.hdr         { color: #555; margin: 1 0 0 1; }
    #presets          { height: 7; border: solid #222; padding: 0 1; margin: 0 0 1 0; }
    #trim             { height: 9; border: solid #222; padding: 0 1; margin: 0 0 1 0; }
    #transport        { height: 5; border: solid #222; padding: 0 1; margin: 0 0 1 0; }
    #log              { border: solid #222; margin: 0; }
    Button            { min-width: 22; margin: 0 1; }
    Button.active     { background: #00ff88; color: #000; }
    Button.voice-on   { background: #cc2222; color: #fff; }
    Button.nudge      { min-width: 10; }
    Label.val         { width: 14; content-align: left middle; color: #aaa; }
    """

    _active = reactive(0)
    _voice  = reactive(False)
    _trim   = {"gate_thresh": 0.0, "fusion_comp": 0.0, "space_sfx_level": 0.0}

    def __init__(self):
        super().__init__()
        self._log_q      = queue.Queue()
        self._voice_flag = threading.Event()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Label("── PRESETS", classes="hdr")
            with Vertical(id="presets"):
                with Horizontal():
                    for i in range(3):
                        yield Button(PRESET_NAMES[i], id=f"p{i}")
                with Horizontal():
                    for i in range(3, 5):
                        yield Button(PRESET_NAMES[i], id=f"p{i}")

            yield Label("── MANUAL TRIM  (Δ on top of preset)", classes="hdr")
            with Vertical(id="trim"):
                with Horizontal():
                    yield Button("Gate ↑", id="g_up", classes="nudge")
                    yield Button("Gate ↓", id="g_dn", classes="nudge")
                    yield Label("Δ 0.0 dB", id="g_val", classes="val")
                with Horizontal():
                    yield Button("Comp ↑", id="c_up", classes="nudge")
                    yield Button("Comp ↓", id="c_dn", classes="nudge")
                    yield Label("Δ 0.00", id="c_val", classes="val")
                with Horizontal():
                    yield Button("Space ↑", id="s_up", classes="nudge")
                    yield Button("Space ↓", id="s_dn", classes="nudge")
                    yield Label("Δ 0.00", id="s_val", classes="val")

            yield Label("── TRANSPORT", classes="hdr")
            with Horizontal(id="transport"):
                yield Button("⏺  REC",  id="rec")
                yield Button("▶  PLAY", id="play")
                yield Button("■  STOP", id="stop")
                yield Button("🎤 VOICE", id="voice")

            yield Log(id="log", max_lines=30)
        yield Footer()

    def on_mount(self):
        load_models()
        self.set_interval(0.1, self._drain)
        self._mark_preset(0)

    def _drain(self):
        log = self.query_one("#log", Log)
        while not self._log_q.empty():
            kind, data = self._log_q.get_nowait()
            if kind == "voice":
                log.write_line(f"[HEARD]  {data}")
            elif kind == "intent":
                log.write_line(f"[→ OSC]  {data}")
            elif kind == "error":
                log.write_line(f"[ERR]    {data}")

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id

        if bid and bid.startswith("p"):
            idx = int(bid[1:])
            self._active = idx
            self._trim   = {"gate_thresh": 0.0, "fusion_comp": 0.0, "space_sfx_level": 0.0}
            send_preset(PRESET_NAMES[idx])
            self._mark_preset(idx)
            self._update_vals()
            self._log_q.put(("intent", {"action": "preset", "name": PRESET_NAMES[idx]}))

        elif bid == "g_up":  self._nudge("gate_thresh",    1.0)
        elif bid == "g_dn":  self._nudge("gate_thresh",   -1.0)
        elif bid == "c_up":  self._nudge("fusion_comp",    0.05)
        elif bid == "c_dn":  self._nudge("fusion_comp",   -0.05)
        elif bid == "s_up":  self._nudge("space_sfx_level", 0.05)
        elif bid == "s_dn":  self._nudge("space_sfx_level",-0.05)

        elif bid == "rec":   transport("record")
        elif bid == "play":  transport("play")
        elif bid == "stop":  transport("stop")

        elif bid == "voice":
            self._voice = not self._voice
            btn = self.query_one("#voice", Button)
            if self._voice:
                btn.label = "🎤 LISTENING"
                btn.add_class("voice-on")
                self._voice_flag.set()
                threading.Thread(
                    target=audio_listener,
                    args=(self._log_q, self._voice_flag),
                    daemon=True,
                ).start()
            else:
                btn.label = "🎤 VOICE"
                btn.remove_class("voice-on")
                self._voice_flag.clear()

    def _nudge(self, key: str, delta: float):
        self._trim[key] = self._trim.get(key, 0.0) + delta
        base = PRESETS[PRESET_NAMES[self._active]].get(key, 0.0)
        send_param(key, base + self._trim[key])
        self._update_vals()

    def _mark_preset(self, idx: int):
        for i in range(5):
            try:
                btn = self.query_one(f"#p{i}", Button)
                btn.remove_class("active")
            except Exception:
                pass
        try:
            self.query_one(f"#p{idx}", Button).add_class("active")
        except Exception:
            pass

    def _update_vals(self):
        self.query_one("#g_val", Label).update(f"Δ {self._trim['gate_thresh']:+.1f} dB")
        self.query_one("#c_val", Label).update(f"Δ {self._trim['fusion_comp']:+.2f}")
        self.query_one("#s_val", Label).update(f"Δ {self._trim['space_sfx_level']:+.2f}")

if __name__ == "__main__":
    CarwashApp().run()
