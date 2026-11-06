"""Profile the crowded-board frame to find the real hotspots."""

from __future__ import annotations

import os
import sys
import cProfile
import pstats
import io

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from inkfall import config as C  # noqa: E402
from inkfall.game import Game  # noqa: E402
from check import Bot  # noqa: E402


def main() -> int:
    pygame.init()
    pygame.display.set_mode((C.WIDTH, C.HEIGHT))
    bot = Bot()
    bot.install()
    game = Game(pygame.display.get_surface())
    game.state = Game.STATE_PLAY
    game.start_wave()
    for i in range(26):
        e = game._make_enemy(["blot", "skitter", "sponge", "quill", "squid"][i % 5])
        e.spawn_anim = 1.0
        game.enemies.append(e)
    for i in range(40):
        game.add_puddle((C.WIDTH * (i % 8) / 8 + 40, C.HEIGHT * (i // 8) / 5 + 40), 30, 0.2)
    game.particles.burst((C.WIDTH / 2, C.HEIGHT / 2), 600, 300, 4.0, 3.0, C.INK, C.INK_SOFT, 0.1)

    def body():
        for _ in range(120):
            bot.drive(game)
            game.update(1 / 60)
            game.draw()

    prof = cProfile.Profile()
    prof.enable()
    body()
    prof.disable()
    out = io.StringIO()
    pstats.Stats(prof, stream=out).sort_stats("tottime").print_stats(18)
    print(out.getvalue())
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
