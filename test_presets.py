#!/usr/bin/env python3
"""test_presets.py — render each preset headlessly via pure scipy/numpy"""

import numpy as np
from scipy import signal
from scipy.io import wavfile

RATE = 44100
DURATION = 4

# ── Synthetic vocal ──────────────────────────────────────────────────────────
def make_vocal():
    t = np.linspace(0, DURATION, RATE * DURATION, endpoint=False)
    sig  = 0.40 * np.sin(2 * np.pi * 200 * t)
    sig += 0.20 * np.sin(2 * np.pi * 400 * t)
    sig += 0.12 * np.sin(2 * np.pi * 800 * t)
    sig += 0.08 * np.sin(2 * np.pi * 1600 * t)
    sig += 0.05 * np.sin(2 * np.pi * 3200 * t)
    sig += 0.02 * np.random.randn(len(t))
    env = np.ones(len(t))
    env[:int(0.05*RATE)] = np.linspace(0, 1, int(0.05*RATE))
    env[-int(0.3*RATE):]  = np.linspace(1, 0, int(0.3*RATE))
    return (sig * env).astype(np.float32)

# ── DSP primitives ───────────────────────────────────────────────────────────
def peaking_eq(audio, fc, gain_db, q=0.8):
    A  = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * fc / RATE
    alpha = np.sin(w0) / (2 * q)
    b = [1 + alpha*A, -2*np.cos(w0), 1 - alpha*A]
    a = [1 + alpha/A, -2*np.cos(w0), 1 - alpha/A]
    return signal.lfilter(b, a, audio).astype(np.float32)

def highpass(audio, fc):
    b, a = signal.butter(2, fc / (RATE/2), btype='high')
    return signal.lfilter(b, a, audio).astype(np.float32)

def compressor(audio, threshold_db, ratio, attack_ms=5, release_ms=80):
    thresh  = 10 ** (threshold_db / 20)
    attack  = np.exp(-1 / (RATE * attack_ms  / 1000))
    release = np.exp(-1 / (RATE * release_ms / 1000))
    env, out = 0.0, np.zeros_like(audio)
    for i, s in enumerate(audio):
        lvl = abs(s)
        if lvl > env:
            env = attack  * env + (1 - attack)  * lvl
        else:
            env = release * env + (1 - release) * lvl
        gain = 1.0 if env < thresh else thresh * (env/thresh)**(1/ratio - 1) / env
        out[i] = s * gain
    return out.astype(np.float32)

def saturate(audio, drive):
    return np.tanh(audio * (1 + drive * 8)).astype(np.float32)

def reverb(audio, room=0.5, wet=0.3):
    if wet == 0:
        return audio
    delays = [int(RATE * d) for d in [0.030, 0.047, 0.067, 0.089]]
    gains  = [0.8 * (room ** (i+1)) for i in range(4)]
    acc = np.zeros(len(audio) + max(delays))
    acc[:len(audio)] += audio
    for d, g in zip(delays, gains):
        acc[d:d+len(audio)] += audio * g
    wet_sig = acc[:len(audio)]
    return (audio * (1 - wet) + wet_sig * wet).astype(np.float32)

def noise_gate(audio, threshold_db):
    thresh = 10 ** (threshold_db / 20)
    return np.where(np.abs(audio) > thresh, audio, audio * 0.01).astype(np.float32)

def normalize_to(audio, target_db=-14.0):
    rms = np.sqrt(np.mean(audio**2))
    if rms == 0: return audio
    target_rms = 10 ** (target_db / 20)
    return np.clip(audio * (target_rms / rms), -1.0, 1.0).astype(np.float32)

# ── Full chain ────────────────────────────────────────────────────────────────
def process(audio, p):
    s = noise_gate(audio, p.get("gate_thresh", -60))
    s = highpass(s, 80 + p.get("tone_low", 0) * -4)
    s = peaking_eq(s, 1800,  p.get("tone_mid",  0))
    s = peaking_eq(s, 8000,  p.get("tone_high", 0))
    s = peaking_eq(s, 14000, p.get("tone_air",  0))
    s = compressor(s,
        threshold_db=-18 - p.get("fusion_comp", 0.5) * 12,
        ratio=max(1.5,    p.get("fusion_comp", 0.5) * 6))
    s = saturate(s, p.get("drive_sat", 0.1))
    s = reverb(s,
        room=p.get("space_sfx_level", 0.2),
        wet=p.get("space_sfx_level",  0.2) * 0.7)
    s = normalize_to(s, p.get("automix_target", -14.0))
    return s

# ── Presets ───────────────────────────────────────────────────────────────────
PRESETS = {
    "Modern_Pop_Crisp": {
        "gate_thresh": -45.0, "tone_low": -2.5, "tone_mid": -1.0,
        "tone_high": 3.0, "tone_air": 4.5, "fusion_comp": 0.85,
        "drive_sat": 0.20, "space_sfx_level": 0.15,
        "space_decay_ms": 1500, "automix_target": -14.0,
    },
    "Vintage_Tube_Warmth": {
        "gate_thresh": -55.0, "tone_low": 2.0, "tone_mid": -2.5,
        "tone_high": -1.5, "tone_air": 0.0, "fusion_comp": 0.45,
        "drive_sat": 0.65, "space_sfx_level": 0.25,
        "space_decay_ms": 900, "automix_target": -16.0,
    },
    "Astro_Infinite_Space": {
        "gate_thresh": -40.0, "tone_low": -4.0, "tone_mid": 1.0,
        "tone_high": 2.0, "tone_air": 5.0, "fusion_comp": 0.70,
        "drive_sat": 0.30, "space_sfx_level": 0.90,
        "space_decay_ms": 2800, "automix_target": -14.0,
    },
    "Radio_Broadcast_Dry": {
        "gate_thresh": -35.0, "tone_low": 1.5, "tone_mid": 0.0,
        "tone_high": 1.5, "tone_air": 1.0, "fusion_comp": 0.60,
        "drive_sat": 0.05, "space_sfx_level": 0.0,
        "automix_target": -16.0,
    },
    "Aggressive_FET_Grit": {
        "gate_thresh": -30.0, "tone_low": -3.0, "tone_mid": 4.5,
        "tone_high": 2.0, "tone_air": 1.5, "fusion_comp": 1.0,
        "drive_sat": 0.90, "space_sfx_level": 0.10,
        "automix_target": -12.0,
    },
}

# ── Render ────────────────────────────────────────────────────────────────────
src_rate, dry_raw = wavfile.read("/root/dry_vocal.wav")
dry = dry_raw.astype(np.float32) / 32768.0
if dry.ndim > 1:
    dry = dry[:, 0]
if src_rate != RATE:
    n = int(len(dry) * RATE / src_rate)
    dry = signal.resample(dry, n)
print(f"dry_vocal.wav  ({len(dry)/RATE:.1f}s)")

for name, params in PRESETS.items():
    wet = process(dry.copy(), params)
    wavfile.write(f"/root/{name}.wav", RATE, wet)
    print(f"{name}.wav")

print("\ndone — pull to listen:")
print("  scp administrator@108.181.162.206:/root/*.wav .")
