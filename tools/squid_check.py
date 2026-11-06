"""Freeze both actors and measure the Squid's true grab trigger distance.

Run with: uv run python tools/squid_check.py
"""

from __future__ import annotations

import math
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from pygame import Vector2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from inkfall import config as C  # noqa: E402
from inkfall.entities import Squid  # noqa: E402
from inkfall.game import Game  # noqa: E402


def drawn_art_reach(squid: Squid) -> float:
    """Longest the tendril art can be drawn, in pixels from body centre."""
    r = squid.effective_radius
    longest = 0.0
    for i in range(5):
        length = r * (squid.TENDRIL_BASE + 0.8 * math.sin(squid.seed + i)) * squid.TENDRIL_STRETCH
        longest = max(longest, length + r * 0.5)
    return longest


def triggers_at(dist: float) -> bool:
    """Place a squid at `dist`, freeze everything, and ask if it starts a grab."""
    random.seed(7)
    game = Game(pygame.display.get_surface())
    game.state = Game.STATE_PLAY
    game.wave = 4
    game.player.pos = Vector2(C.WIDTH / 2, C.HEIGHT / 2)
    game.player.vel = Vector2()
    squid = Squid(game.player.pos + Vector2(dist, 0), wave=4)
    squid.spawn_anim = 1.0
    squid.lash_cd = 0.0

    # drive only the squid's own logic against a pinned player
    start = game.player.mass
    for _ in range(int(1.5 * 60)):
        game.player.pos = Vector2(C.WIDTH / 2, C.HEIGHT / 2)
        squid.pos = game.player.pos + Vector2(dist, 0)
        squid.think(1 / 60, game)
        if squid.windup > 0 or squid.latched > 0:
            return True
    return game.player.mass < start


def main() -> int:
    pygame.init()
    pygame.display.set_mode((C.WIDTH, C.HEIGHT))

    squid = Squid((400, 300), wave=4)
    squid.spawn_anim = 1.0
    art = drawn_art_reach(squid)
    print(f"screen width   = {C.WIDTH}px")
    print(f"squid radius   = {squid.effective_radius:.1f}px")
    print(f"hitbox reach   = {squid.lash_reach:.1f}px")
    print(f"drawn art max  = {art:.1f}px")
    print(f"hitbox / art   = {squid.lash_reach / art:.2f}x  (must be <= 1.0)")
    old = 320.0
    print(f"was 320.0px before, which was {old / art:.2f}x the drawn art\n")

    print("frozen grab test (both positions pinned):")
    last_hit = None
    first_miss = None
    for dist in range(20, 401, 20):
        hit = triggers_at(float(dist))
        print(f"  {dist:3d}px: {'grab' if hit else 'no grab'}")
        if hit:
            last_hit = dist
        elif first_miss is None and last_hit is not None:
            first_miss = dist

    if last_hit and first_miss:
        print(f"\ngrab boundary between {last_hit}px and {first_miss}px; art reaches {art:.0f}px")
        ok = first_miss <= art
        print(f"hitbox within art reach: {'PASS' if ok else 'FAIL'}")
    else:
        print("\ncould not bracket the boundary")

    # player can escape a committed lash by dashing out during the windup
    print("\nescape test: player steps out during the 0.34s windup")
    random.seed(3)
    game = Game(pygame.display.get_surface())
    game.state = Game.STATE_PLAY
    game.player.pos = Vector2(C.WIDTH / 2, C.HEIGHT / 2)
    s = Squid(game.player.pos + Vector2(100, 0), wave=4)
    s.spawn_anim = 1.0
    s.lash_cd = 0.0
    g_start = game.player.mass
    grabbed = False
    for frame in range(180):
        s.think(1 / 60, game)
        if 1 <= frame <= 18:
            game.player.pos += Vector2(-26, 0)  # step away during the tell
        if s.latched > 0:
            grabbed = True
            break
    print(f"  latched after retreating: {grabbed}")
    print(f"  mass {g_start:.2f} -> {game.player.mass:.2f}")

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
