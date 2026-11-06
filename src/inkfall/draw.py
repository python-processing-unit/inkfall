"""Low-level drawing helpers: anti-aliased blobs, cached soft glows, paper."""

from __future__ import annotations

import math
import random

import pygame
from pygame import gfxdraw

from .config import PAPER, PAPER_SHADE, PAPER_WARM, wobble

_GLOW_CACHE: dict[tuple[int, tuple[int, int, int]], pygame.Surface] = {}


def aa_polygon(surface: pygame.Surface, points, color) -> None:
    """Filled polygon with a 1px anti-aliased outline."""
    if len(points) < 3:
        return
    pts = [(int(x), int(y)) for x, y in points]
    gfxdraw.filled_polygon(surface, pts, color)
    gfxdraw.aapolygon(surface, pts, color)


def aa_circle(surface: pygame.Surface, x: float, y: float, radius: float, color) -> None:
    r = int(radius)
    if r < 1:
        return
    gfxdraw.filled_circle(surface, int(x), int(y), r, color)
    gfxdraw.aacircle(surface, int(x), int(y), r, color)


def glow(radius: int, color: tuple[int, int, int], strength: int = 190) -> pygame.Surface:
    """Radial falloff sprite, cache-keyed by size and colour."""
    radius = max(2, int(radius))
    key = (radius, color, strength)
    cached = _GLOW_CACHE.get(key)
    if cached is not None:
        return cached
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    steps = max(8, radius)
    for i in range(steps, 0, -1):
        t = i / steps
        alpha = int(strength * (1.0 - t) ** 2.1)
        if alpha <= 0:
            continue
        gfxdraw.filled_circle(surf, radius, radius, int(radius * t), (*color, alpha))
    _GLOW_CACHE[key] = surf
    return surf


def blit_glow(surface: pygame.Surface, x: float, y: float, radius: int, color, strength: int = 190) -> None:
    sprite = glow(radius, color, strength)
    surface.blit(sprite, (int(x) - radius, int(y) - radius), special_flags=pygame.BLEND_PREMULTIPLIED)


def add_glow(surface: pygame.Surface, x: float, y: float, radius: int, color, strength: int = 190) -> None:
    sprite = glow(radius, color, strength)
    surface.blit(sprite, (int(x) - radius, int(y) - radius), special_flags=pygame.BLEND_RGB_ADD)


def blob_points(
    cx: float,
    cy: float,
    radius: float,
    lobes: int,
    phase: float,
    seed: float,
    squash: tuple[float, float] = (1.0, 1.0),
    points: int = 26,
):
    raw = wobble(radius, lobes, phase, seed, points)
    sx, sy = squash
    return [(cx + px * sx, cy + py * sy) for px, py in raw]


def shade_blob(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    radius: float,
    phase: float,
    seed: float,
    color,
    highlight=None,
    lobes: int = 5,
    squash: tuple[float, float] = (1.0, 1.0),
    points: int = 26,
) -> None:
    """A wet ink mass: solid body, softer rim, and an off-centre sheen."""
    body = blob_points(cx, cy, radius, lobes, phase, seed, squash, points)
    aa_polygon(surface, body, color)
    if highlight is not None and radius > 4:
        inner = blob_points(
            cx - radius * 0.26,
            cy - radius * 0.30,
            radius * 0.55,
            lobes,
            phase * 1.3 + 1.1,
            seed + 4.0,
            squash,
            18,
        )
        aa_polygon(surface, inner, highlight)


def make_paper(width: int, height: int, seed: int = 7) -> pygame.Surface:
    """Procedural laid paper with fibres, grain, and a warm vignette."""
    rng = random.Random(seed)
    paper = pygame.Surface((width, height))
    paper.fill(PAPER)
    wash = pygame.Surface((width, height))
    wash.fill(PAPER_WARM)
    paper.blit(wash, (0, 0), special_flags=pygame.BLEND_MULT)

    grain = pygame.Surface((width, height), pygame.SRCALPHA)
    for _ in range(9000):
        x = rng.randrange(width)
        y = rng.randrange(height)
        a = rng.randrange(6, 22)
        tone = PAPER_SHADE if rng.random() < 0.6 else (255, 255, 255)
        grain.set_at((x, y), (*tone, a))
    paper.blit(grain, (0, 0))

    for _ in range(260):
        x = rng.uniform(0, width)
        y = rng.uniform(0, height)
        length = rng.uniform(6, 46)
        angle = rng.uniform(-0.35, 0.35) + (0.0 if rng.random() < 0.7 else math.pi / 2)
        pts = []
        for i in range(6):
            t = i / 5
            pts.append((x + math.cos(angle) * length * t, y + math.sin(angle) * length * t + math.sin(t * 6) * 1.2))
        pygame.draw.aalines(paper, (*PAPER_SHADE, 255), False, pts)

    vignette = pygame.Surface((width, height), pygame.SRCALPHA)
    cx, cy = width / 2, height / 2
    maxd = math.hypot(cx, cy)
    for i in range(26):
        t = i / 25
        alpha = int(46 * t * t)
        if alpha <= 0:
            continue
        inset = int((1 - t) * maxd * 0.34)
        rect = pygame.Rect(inset, inset, width - inset * 2, height - inset * 2)
        pygame.draw.rect(vignette, (58, 44, 30, alpha), rect, 0, border_radius=40)
    paper.blit(vignette, (0, 0))
    return paper
