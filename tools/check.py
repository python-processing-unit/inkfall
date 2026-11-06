"""Balance, performance and screen-content checks with a scripted player.

Run with: uv run python tools/check.py
"""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from pygame import Vector2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from inkfall import config as C  # noqa: E402
from inkfall.game import Game  # noqa: E402


class Bot:
    def __init__(self) -> None:
        self.keys: set[int] = set()
        self.buttons = (False, False, False)
        self.mouse = (C.WIDTH // 2, C.HEIGHT // 2)

    def install(self) -> None:
        pygame.key.get_pressed = self._pressed
        pygame.mouse.get_pressed = lambda: self.buttons
        pygame.mouse.get_pos = lambda: self.mouse

    def _pressed(self):
        held = self.keys

        class Keys(dict):
            def __missing__(self, key):
                return False

        return Keys({k: True for k in held})

    def drive(self, game: Game) -> None:
        pl = game.player
        target = None
        best = 1e9
        for e in game.enemies:
            d = (e.pos - pl.pos).length() - e.effective_radius
            if d < best:
                best = d
                target = e

        self.keys.clear()
        goal = None
        if pl.mass < 0.42 and game.puddles:
            puddle = min(game.puddles, key=lambda p: (p.pos - pl.pos).length() - p.radius)
            if (puddle.pos - pl.pos).length() > puddle.radius * 0.5:
                goal = puddle.pos
        if goal is None and target is not None:
            aim_radius = 200.0
            want = target.pos
            if best < aim_radius * 0.55:
                want = target.pos + (pl.pos - target.pos) * 0.6
            goal = want

        if goal is not None:
            delta = goal - pl.pos
            if delta.length() > 12:
                if delta.x > 8:
                    self.keys.add(pygame.K_d)
                elif delta.x < -8:
                    self.keys.add(pygame.K_a)
                if delta.y > 8:
                    self.keys.add(pygame.K_s)
                elif delta.y < -8:
                    self.keys.add(pygame.K_w)

        if target is not None:
            lead = 0.11
            predict = target.pos + target.vel * lead
            self.mouse = (int(predict.x), int(predict.y))
            aim = Vector2(self.mouse) - pl.pos
            tvec = target.pos - pl.pos
            aligned = False
            if aim.length_squared() > 1 and tvec.length_squared() > 1:
                aligned = (aim / aim.length()).dot(tvec / tvec.length()) > 0.955
            distance = tvec.length()
            fire = aligned and distance < 420 and pl.mass > 0.3
            self.buttons = (fire and game.player.shot_cd <= 0, False, pl.mass > 0.6 and distance < 300)
        else:
            self.buttons = (False, False, False)

        # emergency dash away from crowds
        nearby = [e for e in game.enemies if (e.pos - pl.pos).length() < 80]
        if len(nearby) >= 2 and pl.dash_cd <= 0 and pl.mass > 0.25:
            away = Vector2()
            for e in nearby:
                away += pl.pos - e.pos
            if away.length_squared() > 1:
                d = away / away.length()
                if d.x > 0.4:
                    self.keys.add(pygame.K_d)
                elif d.x < -0.4:
                    self.keys.add(pygame.K_a)
                if d.y > 0.4:
                    self.keys.add(pygame.K_s)
                elif d.y < -0.4:
                    self.keys.add(pygame.K_w)
                game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT))


def run_balance(seconds: float, verbose: bool = True) -> dict:
    bot = Bot()
    bot.install()
    game = Game(pygame.display.get_surface())
    game.state = Game.STATE_PLAY
    game.start_wave()
    dt = 1 / 60
    worst = 0.0
    deaths = 0
    for frame in range(int(seconds * 60)):
        bot.drive(game)
        game.update(dt)
        game.draw()
        if game.state == Game.STATE_OVER:
            deaths += 1
            if verbose:
                print(f"  died at {frame / 60:.0f}s, wave {game.wave}, score {int(game.score)}")
            break
        if frame % 600 == 0 and verbose:
            print(
                f"  t={frame / 60:4.0f}s wave={game.wave:2d} hp={game.player.mass:.2f} "
                f"score={int(game.score):6d} kills={game.kills:3d} combo={game.combo:2d} "
                f"enemies={len(game.enemies):2d} puddles={len(game.puddles):2d}"
            )
    return {
        "wave": game.wave,
        "score": int(game.score),
        "kills": game.kills,
        "mass": game.player.mass,
        "died": deaths > 0,
        "best_combo": game.best_combo,
    }


def main() -> int:
    pygame.init()
    pygame.display.set_mode((C.WIDTH, C.HEIGHT))

    print("balance: scripted competent player, 180s")
    result = run_balance(420)
    print(" result:", result)

    # ---------------------------------------------------------------- perf
    bot = Bot()
    bot.install()
    game = Game(pygame.display.get_surface())
    game.state = Game.STATE_PLAY
    game.start_wave()
    # force a crowded late-game board
    for i in range(26):
        e = game._make_enemy(["blot", "skitter", "sponge", "quill", "squid"][i % 5])
        e.spawn_anim = 1.0
        game.enemies.append(e)
    for i in range(40):
        game.add_puddle((C.WIDTH * (i % 8) / 8 + 40, C.HEIGHT * (i // 8) / 5 + 40), 30, 0.2)
    game.particles.burst((C.WIDTH / 2, C.HEIGHT / 2), 600, 300, 4.0, 3.0, C.INK, C.INK_SOFT, 0.1)

    frames = 240
    start = time.perf_counter()
    for _ in range(frames):
        bot.drive(game)
        game.update(1 / 60)
        game.draw()
        pygame.display.flip()
    elapsed = time.perf_counter() - start
    ms = elapsed / frames * 1000
    print(f"perf: crowded board {len(game.enemies)} enemies, 600 particles: {ms:.2f} ms/frame "
          f"({1000 / ms:.0f} fps equivalent)")

    # ---------------------------------------------------------------- screens
    for state in (Game.STATE_TITLE, Game.STATE_HELP, Game.STATE_PAUSE, Game.STATE_OVER):
        game.state = state
        game.state_time = 1.2 if state == Game.STATE_OVER else 0.0
        game.draw()
        surf = pygame.display.get_surface()
        colors = len({surf.get_at((x, y))[:3] for x in range(0, C.WIDTH, 7) for y in range(0, C.HEIGHT, 7)})
        paper = surf.get_at((C.WIDTH // 2, C.HEIGHT // 2))[:3]
        print(f"screen {state:6s}: distinct colour samples={colors:4d} centre={paper}")
        pygame.image.save(surf, os.path.join(ROOT, f"tools/_shot_{state}.png"))

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
