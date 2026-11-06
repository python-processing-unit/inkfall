"""Seeded balance sweep: measure how far a scripted player gets over many runs."""

from __future__ import annotations

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from inkfall import config as C  # noqa: E402
from inkfall.game import Game  # noqa: E402
from check import Bot  # noqa: E402


def one_run(seed: int, seconds: float = 240.0) -> dict:
    random.seed(seed)
    pygame.event.clear()
    bot = Bot()
    bot.install()
    game = Game(pygame.display.get_surface())
    game.state = Game.STATE_PLAY
    game.start_wave()
    boss_seen = False
    for frame in range(int(seconds * 60)):
        bot.drive(game)
        game.update(1 / 60)
        game.draw()
        if any(e.kind == "boss" for e in game.enemies):
            boss_seen = True
        if game.state == Game.STATE_OVER:
            return {"seed": seed, "wave": game.wave, "score": int(game.score), "died": True, "t": frame / 60, "boss": boss_seen}
    return {
        "wave": game.wave,
        "score": int(game.score),
        "kills": game.kills,
        "boss": boss_seen,
        "died": False,
        "t": seconds,
    } if (r := {"seed": seed}) is not None else {}


def main() -> int:
    pygame.init()
    pygame.display.set_mode((C.WIDTH, C.HEIGHT))
    results = [one_run(s, 200) for s in range(1, 13)]
    for r in results:
        print(r)
    waves = [r["wave"] for r in results]
    deaths = sum(1 for r in results if r["died"])
    print(f"runs={len(results)} deaths={deaths} wave_mean={sum(waves) / len(waves):.1f} "
          f"wave_min={min(waves)} wave_max={max(waves)}")
    print(f"boss_waves_reached={sum(1 for r in results if r['wave'] >= 5)}")
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
