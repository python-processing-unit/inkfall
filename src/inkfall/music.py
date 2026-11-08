"""Original background music, composed and synthesised at boot.

The harmony, melody, and arrangement below were written for this game.
Nothing is transcribed, sampled, or derived from any existing piece of
music, and no audio files are shipped: the whole thing is generated from
these numbers when the game starts.

Two constraints shaped this file, both measured rather than guessed:

Timing. DASH_COOLDOWN is 0.42s and SHOT_COOLDOWN is 0.105s, exactly a 4:1
ratio, so the game already has a sixteenth-note grid. The tempo is read from
those constants; one beat is one dash and one sixteenth is one shot.

Interference. The effects own roughly 120-1000 Hz (heavy is 85% in 120-250,
absorb 77% in 250-500, wave 53/46 across both, shoot and orb peak near 1 kHz).
Music in that range masks them at any volume, so the arrangement keeps the
melody an octave above it, carves the shared band, and ducks under loud hits.
"""

from __future__ import annotations

import numpy as np
import pygame

from . import config as C

# ---------------------------------------------------------------- grid
# One beat is one dash; one sixteenth is one shot at full fire rate.
BEAT = C.DASH_COOLDOWN
STEP = BEAT / 4
BPM = 60.0 / BEAT
STEPS_PER_BAR = 16
BARS = 16
LOOP_STEPS = BARS * STEPS_PER_BAR


def hz(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


# ---------------------------------------------------------------- form
# Sixteen bars in A minor: an eight-bar statement, then a variation that
# leans toward C major before resolving home. Eight bars looped every 13
# seconds, which the ear memorises in a couple of passes and then finds
# tiring; sixteen bars is 27 seconds and changes enough to stay unnoticed.
#
# Voices sit in their natural registers, one octave apart, so the parts never
# beat against each other:
#   bass  A2-A3   (110-220 Hz)
#   pad   A3-A4   (220-440 Hz)
#   lead  A4-E5   (440-659 Hz)
BASS_NOTE = [
    45, 41, 43, 45, 45, 41, 43, 40,
    45, 41, 48, 43, 45, 41, 40, 45,
]
CHORD = [
    (57, 60, 64), (53, 57, 60), (55, 59, 62), (57, 60, 64),
    (57, 60, 64), (53, 57, 60), (55, 59, 62), (52, 55, 59),
    (57, 60, 64), (53, 57, 60), (52, 55, 60), (55, 59, 62),
    (57, 60, 64), (53, 57, 60), (52, 55, 59), (57, 60, 64),
]

# Lead phrases, voiced high so they sit clear of the bass and pad. Entries are
# (step within bar, length in steps, midi). Empty bars are rests: continuous
# melody for 27 seconds is the main cause of fatigue, so the line stops and
# lets the pad carry the bar instead.
LEAD = [
    [(2, 2, 81), (4, 4, 84), (10, 2, 88), (12, 2, 86)],
    [(0, 2, 84), (4, 4, 89), (10, 2, 86), (12, 4, 84)],
    [(2, 2, 86), (6, 2, 83), (8, 4, 79)],
    [(0, 4, 81), (6, 2, 84), (10, 4, 88)],
    [],                                                  # rest
    [(2, 2, 84), (6, 2, 81), (8, 4, 77)],
    [(0, 2, 79), (4, 2, 83), (8, 4, 86), (14, 2, 83)],
    [(2, 4, 88), (8, 2, 86), (12, 2, 83)],
    [(0, 2, 81), (4, 4, 84), (10, 2, 88), (12, 2, 91)],
    [(2, 2, 89), (6, 4, 86), (12, 4, 84)],
    [(0, 4, 88), (6, 2, 91), (10, 4, 88)],
    [(2, 2, 86), (6, 2, 83), (8, 4, 79)],
    [],                                                  # rest before the return
    [(2, 2, 86), (6, 4, 89), (12, 2, 86)],
    [(0, 4, 83), (6, 4, 86), (12, 2, 83)],
    [(0, 6, 81), (8, 4, 84), (14, 2, 88)],
]

# How loud each bar's pad is. A pad held at constant level for 27 seconds is
# fatiguing on its own, so it swells and recedes across the form.
PAD_DYNAMICS = [
    0.6, 0.7, 0.8, 1.0, 0.7, 0.6, 0.8, 0.9,
    1.0, 0.8, 0.7, 0.9, 0.6, 0.7, 0.8, 0.5,
]

# Percussion per bar as (thuds, splats). Empty bars are deliberate holes: an
# unbroken pulse is the other half of fatigue, and the gaps also leave room
# for the effects. Bars 13-14 drop out so the return in bar 15 lands.
CALM_DRUMS = [
    ((0,), ()), ((), ()), ((0,), ()), ((), ()),
    ((0,), ()), ((), ()), ((0,), ()), ((), ()),
    ((0,), ()), ((), ()), ((0,), ()), ((), ()),
    ((), ()), ((0,), ()), ((), ()), ((0,), ()),
]

COMBAT_DRUMS = [
    ((0, 8), ()), ((0, 8), ()), ((0, 8), ()), ((0, 8, 14), ()),
    ((0, 8), ()), ((0, 8), ()), ((0, 8), ()), ((0, 8, 14), ()),
    ((0, 8), ()), ((0, 8), ()), ((0, 8), ()), ((0, 8, 14), ()),
    ((), ()), ((), ()), ((0, 8), ()), ((0, 8, 14), ()),
]

# The boss gets its own pattern: a heavy downbeat, a doubled hit into the
# second half of each bar, and splats on the offbeats. It never drops out,
# unlike calm and combat, because the boss is the one thing that lets up.
BOSS_DRUMS = [
    ((0, 6, 8, 14), (4, 12)),
    ((0, 6, 8, 14), (4, 12)),
    ((0, 6, 8, 12, 14), (4, 12)),
    ((0, 6, 8, 14), (4, 12)),
    ((0, 6, 8, 14), (4, 12)),
    ((0, 6, 8, 12, 14), (4, 12)),
    ((0, 6, 8, 14), (4, 12)),
    ((0, 4, 6, 8, 14), (4, 12)),
    ((0, 6, 8, 14), (4, 12)),
    ((0, 6, 8, 14), (4, 12)),
    ((0, 6, 8, 12, 14), (4, 12)),
    ((0, 6, 8, 14), (4, 12)),
    ((0, 6, 8, 14), (4, 12)),
    ((0, 4, 6, 8, 14), (4, 12)),
    ((0, 6, 8, 12, 14), (4, 12)),
    ((0, 4, 6, 8, 12, 14), (4, 12)),
]

# Bass figures in sixteenths, rotated by bar so the line is not one ostinato.
BASS_PATTERNS = (
    (0, 6, 8, 14),
    (0, 8),
    (0, 3, 8, 12),
    (0, 8, 11),
)


# ---------------------------------------------------------------- filtering
SFX_BAND = (300.0, 800.0)


def _carve(buf: np.ndarray, rate: int) -> np.ndarray:
    """Take the shared band down a few dB and leave the rest intact.

    Cutting 120-1000 Hz outright would remove most of the music and leave a
    rumble with a hiss on top. A partial cut plus ducking is the workable
    compromise: the music keeps its body, and the effects get the last word
    at the moment they fire.
    """
    n = len(buf)
    freqs = np.fft.rfftfreq(n, 1 / rate)
    spec = np.fft.rfft(buf)

    lo, hi = SFX_BAND
    edge_lo, edge_hi = lo / 2.0, hi * 2.0
    # 0 inside the band, 1 outside it, with smooth octave-wide skirts
    k_low = np.clip(np.log(lo / np.maximum(freqs, 1e-6)) / np.log(lo / edge_lo), 0, 1)
    k_high = np.clip(np.log(np.maximum(freqs, 1e-6) / hi) / np.log(edge_hi / hi), 0, 1)
    outside = np.maximum(k_low, k_high)

    # Shoot and orb both peak near 1 kHz, and that is where the music carries
    # most of its energy, so it gets a deeper notch than the rest of the band.
    notch = np.clip(1.0 - np.abs(np.log2(np.maximum(freqs, 1e-6) / 1000.0)) / 0.45, 0, 1)
    # About 3.5 dB down across the shared band and 5 dB at 1 kHz. Enough to
    # open room without gutting the arrangement; ducking covers the rest.
    gain = (0.66 + 0.34 * outside) * (1.0 - 0.22 * notch ** 2)

    return np.fft.irfft(spec * gain, n).astype(np.float32)


# ---------------------------------------------------------------- envelopes
def _env(n: int, attack: float, release: float, rate: int) -> np.ndarray:
    """Smooth attack and release, flat in between."""
    e = np.ones(n, dtype=np.float32)
    a = min(n, int(attack * rate))
    r = min(n, int(release * rate))
    if a > 0:
        e[:a] = np.linspace(0.0, 1.0, a, dtype=np.float32) ** 1.5
    if r > 0:
        e[n - r:] *= np.linspace(1.0, 0.0, r, dtype=np.float32)
    return e


def _place(buf: np.ndarray, start: int, data: np.ndarray) -> None:
    """Add `data` into `buf` at `start`, wrapping past the end.

    Wrapping makes the loop seam a continuation: a tail that runs past the
    last step is heard again at the top of the next repetition.
    """
    n = len(buf)
    if n == 0 or len(data) == 0:
        return
    if len(data) > n:
        data = data[:n]
    i = start % n
    end = i + len(data)
    if end <= n:
        buf[i:end] += data
    else:
        head = n - i
        buf[i:] += data[:head]
        buf[: len(data) - head] += data[head:]


# ---------------------------------------------------------------- voices
# Deliberately soft: sines and triangles with gentle attacks. The bright
# bell-like partials of the first attempt were a large part of the fatigue.
def v_pad(f, dur, rate, rng, swell=1.0):
    n = int(dur * rate)
    t = np.arange(n, dtype=np.float32) / rate
    # slow swell in and out, so the pad breathes instead of sitting still
    shape = np.sin(np.pi * np.clip(t / max(dur, 1e-6), 0.0, 1.0)) ** 0.8
    sig = (
        np.sin(2 * np.pi * f * t)
        + 0.34 * np.sin(2 * np.pi * f * 1.0021 * t)   # gentle beating, slow
        + 0.12 * np.sin(2 * np.pi * f * 2.0 * t)
    )
    return sig * shape * swell * _env(n, dur * 0.35, dur * 0.4, rate)


def v_bass(f, dur, rate, rng, swell=1.0):
    n = int(dur * rate)
    t = np.arange(n, dtype=np.float32) / rate
    sig = np.sin(2 * np.pi * f * t) + 0.18 * np.sin(4 * np.pi * f * t)
    return sig * np.exp(-3.4 * t) * _env(n, 0.006, min(0.12, dur * 0.5), rate)


def v_lead(f, dur, rate, rng, swell=1.0):
    """Soft mallet: mostly sine, a touch of second harmonic, quick decay."""
    n = int(dur * rate)
    t = np.arange(n, dtype=np.float32) / rate
    sig = np.sin(2 * np.pi * f * t) + 0.16 * np.sin(2 * np.pi * f * 2.0 * t)
    return sig * np.exp(-4.2 * t) * _env(n, 0.008, 0.10, rate)


def v_thud(f, dur, rate, rng, swell=1.0):
    """A wet drop landing: low, bending down, quickly damped."""
    n = int(dur * rate)
    t = np.arange(n, dtype=np.float32) / rate
    freq = f * (1.0 + 1.8 * np.exp(-30.0 * t))
    phase = np.cumsum(2 * np.pi * freq / rate, dtype=np.float32)
    body = np.sin(phase) * np.exp(-16.0 * t)
    wet = rng.normal(0.0, 1.0, n).astype(np.float32) * np.exp(-55.0 * t) * 0.10
    return (body + wet) * _env(n, 0.002, 0.04, rate)


def v_splat(f, dur, rate, rng, swell=1.0):
    """A splat: noise through a falling filter, so it reads as liquid."""
    n = int(dur * rate)
    t = np.arange(n, dtype=np.float32) / rate
    noise = rng.normal(0.0, 1.0, n).astype(np.float32)
    fast = np.convolve(noise, np.ones(9, dtype=np.float32) / 9.0, mode="same")
    slow = np.convolve(noise, np.ones(56, dtype=np.float32) / 56.0, mode="same")
    blend = np.exp(-10.0 * t).astype(np.float32)
    body = np.sin(2 * np.pi * f * t) * np.exp(-34.0 * t) * 0.25
    return ((fast * blend + slow * (1.0 - blend)) * 2.4 + body) * _env(n, 0.001, 0.03, rate)


VOICES = {
    "pad": v_pad,
    "bass": v_bass,
    "lead": v_lead,
    "thud": v_thud,
    "splat": v_splat,
}


# ---------------------------------------------------------------- rendering
def render(score, rate: int, wet: float = 0.0, seed: int = 11) -> np.ndarray:
    """Render (start_step, len_steps, voice, midi, gain) events into one loop."""
    rng = np.random.default_rng(seed)
    buf = np.zeros(int(round(LOOP_STEPS * STEP * rate)), dtype=np.float32)

    for start_step, len_steps, voice, midi, gain, *rest in score:
        swell = rest[0] if rest else 1.0
        dur = len_steps * STEP
        data = VOICES[voice](hz(midi), dur, rate, rng, swell)
        _place(buf, int(start_step * STEP * rate), data * gain)

    if wet > 0:
        tap = (
            0.16 * np.roll(buf, int(0.085 * rate))
            + 0.09 * np.roll(buf, int(0.145 * rate))
            + 0.05 * np.roll(buf, int(0.230 * rate))
        )
        buf = buf + wet * tap

    buf = _carve(buf, rate)
    peak = float(np.max(np.abs(buf))) or 1.0
    return (buf / peak * 0.80).astype(np.float32)


def _build(mode: str) -> list:
    """Assemble a score for one mode from the shared sixteen-bar form."""
    if mode == "calm":
        drums, drum_gain = CALM_DRUMS, 0.55
        pad_gain, bass_gain, lead_gain = 0.085, 0.20, 0.19
    elif mode == "combat":
        drums, drum_gain = COMBAT_DRUMS, 0.80
        pad_gain, bass_gain, lead_gain = 0.050, 0.26, 0.24
    else:
        drums, drum_gain = BOSS_DRUMS, 0.82
        pad_gain, bass_gain, lead_gain = 0.050, 0.30, 0.22

    score = []
    for bar in range(BARS):
        base = bar * STEPS_PER_BAR
        root = BASS_NOTE[bar]
        chord = CHORD[bar]
        swell = PAD_DYNAMICS[bar]
        if mode == "boss":
            root -= 12          # bass alone drops; the pad stays put

        thuds, splats = drums[bar]
        for st in thuds:
            score.append((base + st, 2, "thud", 55, 0.9 * drum_gain))
        for st in splats:
            score.append((base + st, 1, "splat", 150, 0.30 * drum_gain))

        if thuds or mode == "boss":
            # Every bass note stays on the bar's own root. Leaping a fifth on
            # the last note put it a semitone under the next bar's root.
            # The boss keeps the bass running through the drum gaps, so the
            # dropouts feel like a held breath rather than a stop.
            pattern = BASS_PATTERNS[bar % len(BASS_PATTERNS)]
            for st in pattern:
                score.append((base + st, 3, "bass", root, bass_gain))

        # The pad stays in its normal register in every mode. Raising it for
        # the boss put its chord tones in the same octave as the doubled lead
        # and produced minor seconds; the lead's lower octave is what gives
        # the boss its weight, and the pad underneath is what stops the bass
        # from sitting alone.
        for note in chord:
            score.append((base, 16, "pad", note, pad_gain, swell))

        if mode == "boss":
            # The boss is the main theme itself, an octave down and doubled,
            # rather than unrelated material. The player has already heard
            # this tune for several waves, so hearing it turn sour is the
            # point: it reads as the same world going wrong.
            for st, length, note in LEAD[bar]:
                score.append((base + st, length, "lead", note - 12, lead_gain))
                score.append((base + st, length, "lead", note + 12, lead_gain * 0.34))
        else:
            for st, length, note in LEAD[bar]:
                score.append((base + st, length, "lead", note, lead_gain))

    return score


def _calm() -> list:
    return _build("calm")


def _combat() -> list:
    return _build("combat")


def _boss() -> list:
    return _build("boss")


class Music:
    """Three original loops, cross-faded, on reserved mixer channels."""

    MODES = ("calm", "combat", "boss")
    FADE = 1.4

    def __init__(self, audio) -> None:
        self.ok = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.mode = None
        self.gain = 1.0
        self.muted = False
        self._channels: list[pygame.mixer.Channel] = []
        self._live = -1        # channel index currently audible
        self._prev = -1        # channel index fading out, if any
        self._fade = 1.0       # 0 = start of crossfade, 1 = done
        self._paused = False

        # Ducking. Only significant effects dip the music, and never more
        # often than DUCK_GAP: ducking on every shot would modulate the
        # music ten times a second, a flutter-rate tremolo that is more
        # tiring than the masking it would fix.
        self._duck = 0.0
        self.DUCK_TO = 0.55
        self.DUCK_OUT = 0.16
        self.DUCK_FLOOR = 0.60
        self.DUCK_GAP = 0.14
        self._duck_wait = 0.0

        if not getattr(audio, "ok", False):
            return
        init = pygame.mixer.get_init()
        if init is None:
            return
        self.rate = init[0]
        # Low on purpose: the music is a bed, not a co-lead with the effects.
        self.base = 0.26
        try:
            pygame.mixer.set_reserved(2)
            self._channels = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
            self._build()
            self.ok = True
        except (pygame.error, ValueError):
            self.ok = False

    def _build(self) -> None:
        for name, score, wet in (
            ("calm", _calm(), 0.30),
            ("combat", _combat(), 0.20),
            ("boss", _boss(), 0.14),
        ):
            data = render(score, self.rate, wet=wet)
            pcm = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
            self.sounds[name] = pygame.mixer.Sound(buffer=pcm.tobytes())

    @property
    def length(self) -> float:
        if not self.sounds:
            return 0.0
        return self.sounds["calm"].get_length()

    def set(self, mode: str, gain: float = 1.0) -> None:
        """Ask for a mode. Switching only happens when the mode changes."""
        self.gain = max(0.0, min(1.0, gain))
        if not self.ok or mode == self.mode:
            return
        snd = self.sounds.get(mode)
        if snd is None:
            return

        if self._live < 0:
            ch = self._channels[0]
            ch.play(snd, loops=-1)
            ch.set_volume(0.0)
            if self._paused:
                ch.pause()
            self._live, self._prev, self.mode, self._fade = 0, -1, mode, 0.0
            return

        nxt = 1 - self._live
        # A second switch mid-fade reuses the fading channel, cutting the
        # oldest tail. Modes change on wave and boss beats, so two switches
        # inside 1.4 s only happens at a wave boundary during a boss.
        if nxt == self._prev:
            self._channels[nxt].stop()
        self._channels[nxt].play(snd, loops=-1)
        self._channels[nxt].set_volume(0.0)
        if self._paused:
            self._channels[nxt].pause()
        self._channels[self._live].set_volume(self.base * self.gain * (1.0 - self._fade))
        self._prev, self._live, self.mode, self._fade = self._live, nxt, mode, 0.0

    def duck(self, amount: float = 1.0) -> None:
        """Dip the music so a significant effect can be heard through it."""
        if not self.ok or amount < self.DUCK_FLOOR or self._duck_wait > 0.0:
            return
        self._duck = max(self._duck, min(1.0, amount))
        self._duck_wait = self.DUCK_GAP

    def pause(self) -> None:
        """Freeze the loop in place; it resumes from the same beat."""
        if not self.ok or self._paused:
            return
        self._paused = True
        for ch in self._channels:
            if ch.get_busy():
                ch.pause()

    def resume(self) -> None:
        if not self.ok or not self._paused:
            return
        self._paused = False
        for ch in self._channels:
            if ch.get_busy():
                ch.unpause()

    def silence(self) -> None:
        for ch in self._channels:
            ch.stop()
        self._live = -1
        self._prev = -1
        self.mode = None

    def update(self, dt: float) -> None:
        if not self.ok or self._live < 0:
            return
        if self._fade < 1.0:
            self._fade = min(1.0, self._fade + dt / self.FADE)
        if self._duck_wait > 0.0:
            self._duck_wait = max(0.0, self._duck_wait - dt)
        if self._duck > 0.0:
            self._duck = max(0.0, self._duck - dt / self.DUCK_OUT)
        duck_scale = 1.0 - (1.0 - self.DUCK_TO) * self._duck

        level = 0.0 if self.muted else self.base * self.gain * self._fade * duck_scale
        self._channels[self._live].set_volume(level)

        if self._prev >= 0:
            if self._fade >= 1.0:
                self._channels[self._prev].stop()
                self._prev = -1
            else:
                self._channels[self._prev].set_volume(
                    self.base * self.gain * (1.0 - self._fade) * duck_scale
                )

    def stop(self) -> None:
        if self.ok:
            for ch in self._channels:
                ch.stop()
