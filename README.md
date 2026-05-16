# CARWASH

Vocal chain controller. Drop audio, auto-align to mix baseline, add style.

## What it does

1. **AUTO ALIGN** — analyzes incoming audio, detects if already mixed, applies only what's missing (gain, high pass, transparency comp)
2. **SEAL** — locks clarity hermetically
3. **STYLE** — additive FX only: hidden wet, space, pitch, width, drive, gated reverb, reverse verb, chopped, stutter
4. **SAVE** — name and save any combination as a "sound", persists locally + uploads to server

## Stack

- `index.html` — browser-based audio player + processor (Web Audio API, no dependencies)
- `server.py` — Flask server, serves files + accepts uploads
- `carwash.py` — CLI/TUI controller for Reaper via OSC (textual + python-osc + whisper)
- `test_presets.py` — headless preset rendering via scipy

## Run

```bash
pip install -r requirements.txt
python3 server.py
# open http://localhost:8888
```

## OSC / Reaper

Enable OSC in Reaper on port 8000, then:

```bash
python3 carwash.py
```

Voice control via monitored mic track. Whisper transcribes, Claude parses intent, OSC fires to Reaper live.
