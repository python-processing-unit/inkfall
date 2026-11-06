"""Headless soak test: runs the real game loop with a fake mouse and keys.

Not shipped gameplay. Run with: uv run python tools/smoke.py
"""

from __future__ import annotations

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
from inkfall.game import Game  # noqa: E402


class Fake:
    def __init__(self) -> None:
        self.keys = set()
        self.buttons = (False, False, False)
        self.mouse = (C.WIDTH // 2, C.HEIGHT // 2)

    def install(self) -> None:
        pygame.key.get_pressed = lambda: self._pressed()
        pygame.mouse.get_pressed = lambda: self.buttons
        pygame.mouse.get_pos = lambda: self.mouse

    def _pressed(self):
        held = self.keys

        class Keys(dict):
            def __missing__(self, key):
                return False

        return Keys({k: True for k in held})


def main() -> int:
    pygame.init()
    pygame.display.set_mode((C.WIDTH, C.HEIGHT))
    fake = Fake()
    fake.install()

    game = Game(pygame.display.get_surface())
    game.state = Game.STATE_PLAY
    game.start_wave()

    names = [k for k in dir(pygame) if k.startswith("K_")]
    held = [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_LSHIFT]
    frames = 0
    dt = 1 / 60

    screens_seen = set()
    for frame in range(60 * 240):
        frames += 1
        # wander inputs
        if frame % 40 == 0:
            fake.keys = set(random.sample(held[:4], random.randint(0, 2)))
        if frame % 17 == 0:
            fake.keys.add(pygame.K_LSHIFT)
        if frame % 53 == 0:
            fake.keys.discard(pygame.K_LSHIFT)
        if frame % 9 == 0:
            fake.mouse = (random.randint(0, C.WIDTH), random.randint(0, C.HEIGHT))
        fake.buttons = (random.random() < 0.75, False, random.random() < 0.06)

        game.update(dt)
        game.draw()
        screens_seen.add(game.state)

        if game.state == Game.STATE_OVER:
            if frame % 30 == 0:
                game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if frame % 900 == 0:
            game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
            game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        if frame % 1200 == 0:
            game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h))
            game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h))
        # journal the run state
        if frame % 600 == 0:
            print(
                f"t={frame / 60:5.1f}s wave={game.wave:2d} mass={game.player.mass:.2f} "
                f"enemies={len(game.enemies):2d} puddles={len(game.puddles):2d} "
                f"drops={len(game.drops):2d} orbs={len(game.orbs):2d} parts={len(game.particles.items):3d} "
                f"score={int(game.score):6d} state={game.state}"
            )

    print(f"frames={frames} states={sorted(screens_seen)} wave={game.wave} score={int(game.score)}")
    print("SMOKE OK")
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
