"""INKFALL: a small, strange arcade game about being wet in a dry world.

Run with:  uv run inkfall
"""

from __future__ import annotations

import sys

import pygame

from .config import CAPTION, HEIGHT, WIDTH


def main() -> None:
    pygame.init()
    pygame.display.set_caption(CAPTION)
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    except pygame.error as exc:  # pragma: no cover - environment dependent
        print(f"could not open a window: {exc}", file=sys.stderr)
        raise SystemExit(1)

    from .game import Game

    game = Game(screen)
    try:
        game.run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
