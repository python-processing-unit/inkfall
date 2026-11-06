"""Startup check with real video and audio drivers; quits after a few frames."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame

from inkfall import config as C
from inkfall.audio import Audio
from inkfall.game import Game


def main() -> int:
    pygame.init()
    print("video driver:", pygame.display.get_driver())
    screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
    print("window:", screen.get_size(), "depth", screen.get_bitsize())
    audio = Audio()
    print("audio ok:", audio.ok, "sounds:", sorted(audio.sounds)[:6])

    game = Game(screen)
    game.state = Game.STATE_PLAY
    game.start_wave()
    for i in range(180):
        pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(400 + i, 300), rel=(1, 0), buttons=(0, 0, 0)))
        game.update(1 / 60)
        game.draw()
        pygame.display.flip()
    print("real-driver frames ok, wave", game.wave, "enemies", len(game.enemies))
    pygame.image.save(screen, os.path.join(ROOT, "tools/_shot_play.png"))
    game.audio.play("combo", 0.5)
    pygame.time.wait(120)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
