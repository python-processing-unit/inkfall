"""Objectively inspect the music: grid, harmony, register, and mix.

I cannot hear the output, so this checks the properties that separate a
coherent arrangement from a random one, plus the ones that decide whether
the music and the effects can be heard at the same time.

Run with: uv run python tools/music_audit.py
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from inkfall import config as C  # noqa: E402
from inkfall import music as M  # noqa: E402

RATE = 44100
PITCHED = {"bass", "lead", "pad"}
PERCUSSION = {"thud", "splat", "tick", "wood"}
BANDS = [0, 120, 250, 500, 1000, 2000, 4000, 22050]


def note_name(midi: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[midi % 12]}{midi // 12 - 1}"


def band_shares(data: np.ndarray) -> list[float]:
    spec = np.abs(np.fft.rfft(data)) ** 2
    freqs = np.fft.rfftfreq(len(data), 1 / RATE)
    shares = [
        spec[(freqs >= lo) & (freqs < hi)].sum()
        for lo, hi in zip(BANDS, BANDS[1:])
    ]
    total = sum(shares) or 1.0
    return [s / total * 100 for s in shares]


def audit(name: str, score, wet: float) -> dict:
    print(f"\n=== {name} ===")
    data = M.render(score, RATE, wet=wet)

    starts = [event[0] for event in score]
    off_grid = [s for s in starts if abs(s - round(s)) > 1e-9]
    print(f"events={len(score):3d}  off_grid={len(off_grid)}  "
          f"length={len(data) / RATE:.2f}s")

    # Register spread. Percussion carries a pitch too, but it is a hit, not a
    # note, so it is listed separately and excluded from the harmony check.
    by_voice: dict[str, list[int]] = {}
    for event in score:
        by_voice.setdefault(event[2], []).append(event[3])
    for voice, notes in sorted(by_voice.items()):
        if voice in PITCHED:
            print(f"  {voice:6s} n={len(notes):3d} "
                  f"{note_name(min(notes)):>5s}..{note_name(max(notes)):<5s} "
                  f"({M.hz(min(notes)):6.1f}..{M.hz(max(notes)):7.1f} Hz)")
        else:
            print(f"  {voice:6s} n={len(notes):3d} (percussion)")

    # Semitone clashes between notes that actually overlap in time and are
    # close enough in register to beat. Widely spaced intervals are fine.
    sounding = [
        (e[0], e[0] + e[1], e[3], e[2]) for e in score if e[2] in PITCHED
    ]
    clashes = []
    for i, (s0, e0, n0, v0) in enumerate(sounding):
        for s1, e1, n1, v1 in sounding[i + 1:]:
            if s0 >= e1 or s1 >= e0:
                continue
            distance = abs(n0 - n1)
            if distance == 0:
                continue
            if distance < 3 or (distance % 12 in (1, 11) and distance <= 14):
                clashes.append((min(s0, s1), n0, n1, v0, v1))
    print(f"  simultaneous semitone clashes: {len(clashes)}")
    for step, n0, n1, v0, v1 in clashes[:5]:
        print(f"    bar {step // M.STEPS_PER_BAR} step {step:3d}: "
              f"{v0} {note_name(n0)} against {v1} {note_name(n1)}")

    # Activity, to catch an arrangement that never breathes.
    perc = [e[0] for e in score if e[2] in PERCUSSION]
    per_bar = np.bincount([p // M.STEPS_PER_BAR for p in perc], minlength=M.BARS)
    onsets = {e[0] for e in score if e[2] in PITCHED or e[2] in PERCUSSION}
    print(f"  percussion per bar: min={per_bar.min()} max={per_bar.max()} "
          f"mean={per_bar.mean():.1f}")
    print(f"  bars with no percussion at all: {int((per_bar == 0).sum())}/{M.BARS}")
    print(f"  steps with an onset: {len(onsets)}/{M.BARS * M.STEPS_PER_BAR} "
          f"({100 * len(onsets) / (M.BARS * M.STEPS_PER_BAR):.0f}%)")

    shares = band_shares(data)
    print(f"  spectrum %: " + " ".join(f"{b:>5d}" for b in BANDS[1:]))
    print(f"              " + " ".join(f"{v:5.1f}" for v in shares))
    print(f"  peak={np.max(np.abs(data)):.2f} rms={np.sqrt(np.mean(data ** 2)):.4f} "
          f"({20 * np.log10(np.sqrt(np.mean(data ** 2))):.1f} dBFS)")

    return {"clashes": len(clashes), "shares": shares, "rms": float(np.sqrt(np.mean(data ** 2)))}


def sfx_shares() -> dict[str, list[float]]:
    """Measure the effects so the overlap is a fact, not an assumption."""
    from inkfall.audio import Audio

    audio = Audio()
    out = {}
    for name, snd in audio.sounds.items():
        arr = pygame.sndarray.array(snd).astype(np.float32).ravel() / 32768.0
        if arr.size:
            out[name] = band_shares(arr)
    return out


def main() -> int:
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    pygame.display.set_mode((C.WIDTH, C.HEIGHT))

    print(f"grid: {M.BPM:.2f} BPM, beat={M.BEAT:.4f}s, step={M.STEP:.4f}s")
    print(f"beat == DASH_COOLDOWN: {abs(M.BEAT - C.DASH_COOLDOWN) < 1e-9}")
    print(f"step == SHOT_COOLDOWN: {abs(M.STEP - C.SHOT_COOLDOWN) < 1e-9}")

    results = {
        "calm": audit("calm", M._calm(), 0.30),
        "combat": audit("combat", M._combat(), 0.20),
        "boss": audit("boss", M._boss(), 0.14),
    }

    print("\n=== mix: music against the effects ===")
    sfx = sfx_shares()
    for name, res in results.items():
        worst = []
        for sname, shares in sfx.items():
            # percentage points of shared energy in the 120-1000 Hz region
            music_mid = sum(res["shares"][0:4])
            sfx_mid = sum(shares[0:4])
            if music_mid > 15 and sfx_mid > 15:
                worst.append(sname)
        print(f"  {name:7s} mid-band energy {sum(res['shares'][0:4]):5.1f}%  "
              f"competes with: {', '.join(worst) if worst else 'nothing significant'}")

    total_clashes = sum(r["clashes"] for r in results.values())
    print(f"\ntotal semitone clashes across all three loops: {total_clashes}")

    pygame.quit()
    return 0 if total_clashes == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
