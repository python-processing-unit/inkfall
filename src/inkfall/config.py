"""Shared constants, palette, and small math helpers for INKFALL."""

from __future__ import annotations

import math

WIDTH, HEIGHT = 960, 600
FPS = 60
CAPTION = "INKFALL  |  a blot's last stand"

# ---------------------------------------------------------------- palette
PAPER = (242, 237, 224)
PAPER_WARM = (232, 224, 206)
PAPER_SHADE = (220, 211, 192)
INK = (28, 23, 44)
INK_MID = (66, 54, 108)
INK_SOFT = (122, 110, 178)
INK_PALE = (178, 170, 210)
VERMILION = (204, 62, 40)
VERM_DARK = (142, 36, 28)
VERM_PALE = (231, 146, 116)
GOLD = (216, 154, 52)
WHITE = (250, 248, 240)

# ---------------------------------------------------------------- player
PLAYER_START_MASS = 0.70
MASS_DEATH = 0.12
MASS_MAX = 1.0
SHOT_COST = 0.020
HEAVY_COST = 0.085
DASH_COST = 0.05
SHOT_COOLDOWN = 0.105
CHARGE_TIME = 0.34
ABSORB_RATE = 1.25
DASH_IMPULSE = 640.0
DASH_IFRAMES = 0.26
DASH_COOLDOWN = 0.42
HIT_IFRAMES = 0.70

# ---------------------------------------------------------------- world
PUDDLE_DRY_TIME = 16.0
ORB_MAGNET = 150.0
COMBO_WINDOW = 2.4
MAX_PARTICLES = 900
MAX_PUDDLES = 60


def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(a, b, t: float):
    t = clamp(t, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def ease_out(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 3


def ease_in(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t


_ANGLE_CACHE: dict[int, tuple[tuple[float, float, float], ...]] = {}


def angles(points: int):
    """Cached (cos, sin, angle) triples, so outlines do not redo trig per point."""
    table = _ANGLE_CACHE.get(points)
    if table is None:
        table = tuple(
            (math.cos(math.tau * i / points), math.sin(math.tau * i / points), math.tau * i / points)
            for i in range(points)
        )
        _ANGLE_CACHE[points] = table
    return table


def wobble(radius: float, lobes: int, phase: float, seed: float, points: int = 22):
    """Organic closed outline: a circle with breathing lobes.

    Point count shrinks for small shapes, where the lobes are invisible and
    polygon fill cost dominates.
    """
    if radius < 9.0:
        points = 8
    elif radius < 20.0:
        points = max(10, min(points, 14))
    p1 = phase + seed
    p2 = -phase * 1.7 + seed * 2.3
    l2 = lobes + 3
    sin = math.sin
    out = []
    append = out.append
    for ca, sa, a in angles(points):
        r = radius * (1.0 + 0.085 * sin(lobes * a + p1) + 0.045 * sin(l2 * a + p2))
        append((ca * r, sa * r))
    return out
