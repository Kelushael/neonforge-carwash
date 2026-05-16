# ◈ CARWASH

> Drop audio. Auto-align to mix baseline. Add style only. Save your sound.

---

## Install

### Linux (Debian/Ubuntu)
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Kelushael/neonforge-carwash/master/install.sh)
```

### Mac (Homebrew)
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Kelushael/neonforge-carwash/master/install.sh)
```

### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/Kelushael/neonforge-carwash/master/install.ps1 | iex
```

### Termux (Android)
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Kelushael/neonforge-carwash/master/install.sh)
```

### Manual (any platform)
```bash
git clone https://github.com/Kelushael/neonforge-carwash.git
cd neonforge-carwash
python3 -m venv env && source env/bin/activate
pip install -r requirements.txt
python3 server.py
# open http://localhost:8888
```

---

## How it works

### Stage 1 — AUTO ALIGN
Analyzes the dropped file. Detects if already mixed (peak, RMS, dynamic range).
- Already mixed → corrective processing skipped, style-only mode
- Raw mic → gain correction, high pass, transparency comp applied

### Stage 2 — SEAL
Locks clarity. Nothing colored, nothing added beyond what's needed.

### Stage 3 — STYLE
Additive only. Described by texture, not genre.

| Slider | Effect |
|---|---|
| HIDDEN WET | Reverb felt not heard |
| SPACE SIZE | Room → infinite tail |
| PITCH | Down = darker, heavier |
| WIDTH | Mono → wide |
| DRIVE | Clean → colored harmonics |

| FX Toggle | Effect |
|---|---|
| GATED | Hard chop on reverb tail |
| REVERSE VERB | Tail breathes before the hit |
| CHOPPED | Houston slow (0.72x pitch + tempo) |
| STUTTER | Rhythmic gate |

### Save a Sound
Dial in any combination → name it → SAVE SOUND.
Persists in browser localStorage + uploads JSON to server.
Load any saved sound instantly by clicking its name.

---

## Reaper OSC (CLI controller)

Enable OSC in Reaper on port 8000, then run the TUI controller:

```bash
python3 carwash.py
```

- Preset buttons fire OSC parameter values to Reaper live
- Manual trim: nudge individual params on top of any preset
- Transport: rec / play / stop from terminal
- Voice: toggle mic listening — speak commands, Whisper transcribes, Claude parses intent, OSC fires

```
"hit astro preset"     → loads Astro Infinite Space
"more reverb"          → nudges space_sfx_level up
"record"               → fires /transport/record to Reaper
```

---

## Requirements

- Python 3.9+
- ffmpeg (for MP3 decode in test_presets.py)
- espeak (optional, for test signal generation)
- ANTHROPIC_API_KEY (for voice intent parsing)

---

## Files

| File | Purpose |
|---|---|
| `index.html` | Browser player + processor (Web Audio API, zero dependencies) |
| `server.py` | Flask server — serves files, accepts uploads |
| `carwash.py` | Reaper OSC TUI controller + voice |
| `test_presets.py` | Headless preset rendering via scipy |
| `install.sh` | Linux / Mac / Termux installer |
| `install.ps1` | Windows PowerShell installer |
