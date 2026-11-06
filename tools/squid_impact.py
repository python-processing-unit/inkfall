"""Compare runs with and without Squids to isolate their contribution.

Run with: uv run python tools/squid_impact.py
"""

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


def run(seed: int, seconds: float, allow_squid: bool) -> dict:
    random.seed(seed)
    pygame.event.clear()
    bot = Bot()
    bot.install()
    game = Game(pygame.display.get_surface())
    game.state = Game.STATE_PLAY
    game.start_wave()

    if not allow_squid:
        original = game._make_enemy

        def filtered(kind: str):
            if kind == "squid":
                kind = "quill"
            return original(kind)

        game._make_enemy = filtered

    for frame in range(int(seconds * 60)):
        bot.drive(game)
        game.update(1 / 60)
        game.draw()
        if game.state == Game.STATE_OVER:
            return {"wave": game.wave, "score": int(game.score), "died": True, "t": frame / 60}
    return {"wave": game.wave, "score": int(game.score), "died": False, "t": seconds}


def summarise(label: str, results: list[dict]) -> None:
    waves = [r["wave"] for r in results]
    deaths = sum(1 for r in results if r["died"])
    print(
        f"{label:16s} runs={len(results):2d} deaths={deaths:2d} "
        f"wave_mean={sum(waves) / len(waves):.2f} wave_min={min(waves)} wave_max={max(waves)}"
    )


def main() -> int:
    pygame.init()
    pygame.display.set_mode((C.WIDTH, C.HEIGHT))
    seconds = 200.0
    seeds = list(range(1, 17))

    with_squid = [run(s, seconds, True) for s in seeds]
    without = [run(s, seconds, False) for s in seeds]

    summarise("with squid", with_squid)
    summarise("squid->quill", without)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
