"""Procedural audio: every sound is synthesised at boot, no asset files."""

from __future__ import annotations

import random

import numpy as np
import pygame


class Audio:
    def __init__(self) -> None:
        self.ok = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            self.rate = pygame.mixer.get_init()[0]
            self.ok = True
        except pygame.error:
            return
        self._build()

    # ------------------------------------------------------------------
    def _tone(
        self,
        dur: float,
        freq0: float,
        freq1: float | None = None,
        kind: str = "sine",
        volume: float = 0.35,
        decay: float = 3.0,
        noise: float = 0.0,
        attack: float = 0.004,
        vib: float = 0.0,
    ) -> np.ndarray:
        n = max(1, int(self.rate * dur))
        t = np.arange(n, dtype=np.float32) / self.rate
        f1 = freq0 if freq1 is None else freq1
        freq = np.linspace(freq0, f1, n, dtype=np.float32)
        if vib:
            freq = freq * (1.0 + vib * np.sin(2 * np.pi * 7.5 * t))
        phase = np.cumsum(2 * np.pi * freq / self.rate, dtype=np.float32)
        if kind == "sine":
            wave = np.sin(phase)
        elif kind == "square":
            wave = np.sign(np.sin(phase)) * 0.7
        elif kind == "saw":
            wave = 2.0 * (phase / (2 * np.pi) % 1.0) - 1.0
        elif kind == "tri":
            wave = 2.0 * np.abs(2.0 * (phase / (2 * np.pi) % 1.0) - 1.0) - 1.0
        else:
            wave = np.sin(phase)
        env = np.exp(-decay * t)
        a = max(1, int(attack * self.rate))
        env[:a] *= np.linspace(0, 1, a)
        if noise > 0:
            rng = np.random.default_rng(1234)
            wave = wave * (1 - noise) + rng.normal(0, 1, n).astype(np.float32) * noise
        out = wave * env * volume
        return np.clip(out, -1.0, 1.0)

    def _seq(self, parts: list[np.ndarray], gap: float = 0.0) -> np.ndarray:
        if gap > 0:
            silence = np.zeros(int(self.rate * gap), dtype=np.float32)
            joined = []
            for p in parts:
                joined.extend([p, silence])
            return np.concatenate(joined)
        return np.concatenate(parts) if parts else np.zeros(1, dtype=np.float32)

    def _make(self, name: str, data: np.ndarray, volume: float = 1.0) -> None:
        stereo = np.repeat((data * volume * 32767).astype(np.int16), 1)
        self.sounds[name] = pygame.mixer.Sound(buffer=stereo.tobytes())

    def _build(self) -> None:
        # dart: a short wet flick
        self._make("shoot", self._seq([self._tone(0.09, 900, 420, "tri", 0.22, 26, noise=0.35)]), 0.55)
        # heavy: deep blorp
        self._make(
            "heavy",
            self._seq(
                [
                    self._tone(0.1, 220, 120, "sine", 0.4, 14),
                    self._tone(0.28, 160, 60, "sine", 0.35, 9, noise=0.25),
                ]
            ),
            0.6,
        )
        self._make("splat", self._seq([self._tone(0.12, 420, 150, "sine", 0.3, 22, noise=0.5)]), 0.4)
        self._make("absorb", self._seq([self._tone(0.13, 330, 720, "sine", 0.16, 12)]), 0.5)
        self._make("orb", self._seq([self._tone(0.1, 880, 1320, "tri", 0.14, 18)]), 0.45)
        self._make("kill", self._seq([self._tone(0.2, 300, 90, "saw", 0.16, 11, noise=0.4)]), 0.45)
        self._make("hurt", self._seq([self._tone(0.24, 190, 70, "square", 0.2, 8, noise=0.5)]), 0.5)
        self._make("dash", self._seq([self._tone(0.18, 700, 240, "sine", 0.14, 9, noise=0.6)]), 0.5)
        self._make("wave", self._seq([self._tone(0.4, 196, 196, "tri", 0.14, 2.0), self._tone(0.5, 294, 294, "tri", 0.13, 2.2)]), 0.5)
        self._make("boss", self._seq([self._tone(0.7, 110, 55, "saw", 0.2, 2.4, noise=0.35)]), 0.6)
        self._make("death", self._seq([self._tone(0.9, 300, 40, "sine", 0.24, 2.2, noise=0.25)]), 0.6)
        self._make("ui", self._seq([self._tone(0.06, 1200, 1200, "tri", 0.1, 30)]), 0.5)
        self._make("combo", self._seq([self._tone(0.07, 1046, 1568, "tri", 0.1, 24)]), 0.4)

    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.ok:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        try:
            snd.set_volume(max(0.0, min(1.0, volume)))
            snd.play()
        except pygame.error:
            pass
