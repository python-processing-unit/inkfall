"""Exercise the real console entry point (inkfall.main) with a short auto-quit."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

import inkfall  # noqa: E402
from inkfall import game as game_module  # noqa: E402
from inkfall.game import Game  # noqa: E402

frames = 0


def short_run(self) -> None:
    global frames
    self.state = Game.STATE_PLAY
    self.start_wave()
    while self.running and frames < 150:
        self.clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            else:
                self.handle_event(event)
        self.update(1 / 60)
        self.draw()
        pygame.display.flip()
        frames += 1


Game.run = short_run
inkfall.main()
print("entry point ok, frames:", frames)
print("display initialised after main:", pygame.display.get_init())
