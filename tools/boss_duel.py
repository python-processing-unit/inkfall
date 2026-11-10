"""Fight OCTOPUS and check the fight has the shape it is supposed to.

OCTOPUS is eight arms and one head. The head is armoured. Only the last fifth
of an arm can be damaged; shots further up the limb are absorbed. Severing an
arm opens the head, and the head stays open until the player lands exactly one
increment of damage, an eighth of the pool. It then re-armours, pauses, and
fires faster. Arms never regrow, so eight arms is eight steps.

So there are three things to verify, and a bot that ignores any of them is
testing nothing:

  arms    it aims at arms, severs them, and shoots the head while it is open
  body    it fires at the head the whole time, which should do nothing
  passive it never fires, which should lose to the arms

Run with: uv run python tools/boss_duel.py
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
from inkfall.config import clamp  # noqa: E402


def norm(v):
    length = v.length()
    return v / length if length > 1e-6 else Vector2(0, 1)
from inkfall.game import Game  # noqa: E402


class _Keys(dict):
    def __missing__(self, key):
        return False


class Pilot:
    def __init__(self, style: str, drink_below: float = 0.55,
                 fire_above: float = 0.30) -> None:
        self.style = style
        self.drink_below = drink_below
        self.fire_above = fire_above
        self.keys: set[int] = set()
        self.buttons = (False, False, False)
        self.mouse = (C.WIDTH // 2, C.HEIGHT // 2)

    def install(self) -> None:
        pygame.key.get_pressed = lambda: _Keys({k: True for k in self.keys})
        pygame.mouse.get_pressed = lambda: self.buttons
        pygame.mouse.get_pos = lambda: self.mouse

    def _steer(self, to: Vector2) -> None:
        if to.length_squared() < 64:
            return
        if to.x > 6:
            self.keys.add(pygame.K_d)
        elif to.x < -6:
            self.keys.add(pygame.K_a)
        if to.y > 6:
            self.keys.add(pygame.K_s)
        elif to.y < -6:
            self.keys.add(pygame.K_w)

    def _threat(self, game):
        """The incoming droplet most likely to hit, or None."""
        pl = game.player
        best = None
        best_t = 1e9
        for d in game.drops:
            if d.dead or d.friendly:
                continue
            rel = pl.pos - d.pos
            if d.vel.dot(rel) <= 0:
                continue
            speed = max(1.0, d.vel.length())
            miss = abs(rel.cross(d.vel)) / speed
            if miss > 46.0:
                continue
            t = rel.length() / speed
            if t < best_t:
                best_t = t
                best = d
        return best

    def _target(self, pl, boss):
        """Where to point the cursor this frame."""
        if self.style == "body":
            return boss.pos
        if boss.open:
            return boss.pos
        live = [a for a in boss.arms if a.alive]
        if not live:
            return boss.pos
        # Prefer the nearest arm whose tip is reachable without crossing the
        # boss, so shots do not get eaten by the mantle on the way out.
        def cost(a):
            zone = a.tip_zone()
            pt = zone[len(zone) // 2] if zone else a.tip()
            return (pt - pl.pos).length()

        arm = min(live, key=cost)
        zone = arm.tip_zone()
        return zone[len(zone) // 2] if zone else arm.tip()

    def drive(self, game: Game) -> None:
        """Move, drink, aim and fire, all decided every frame.

        Movement and firing are deliberately independent. In the earlier
        version each movement branch returned early, which meant that any
        frame spent dodging or drinking also spent a shot, and the bot fired
        roughly a third as often as it should. That made the harness report a
        boss that could not be killed when the bot had barely shot at it.
        """
        pl = game.player
        boss = next((e for e in game.enemies if e.kind == "boss"), None)
        self.keys.clear()
        if boss is None:
            self.buttons = (False, False, False)
            return

        # --- movement ---
        threat = self._threat(game)
        if threat is not None:
            side = (pl.pos - threat.pos).cross(threat.vel)
            away = Vector2(-threat.vel.y, threat.vel.x)
            if side < 0:
                away = -away
            self._steer(norm(away + (pl.pos - threat.pos).normalize() * 0.7) * 200)
        else:
            to = boss.pos - pl.pos
            dist = max(1.0, to.length())
            # Hold just outside the tips: far enough that an aimed shot has
            # travel time, close enough that the bot's own splats are worth
            # walking back for.
            keep = boss.reach + 40.0
            if dist < keep:
                self._steer(-to)
            elif dist > keep + 90:
                self._steer(to)
            else:
                self._steer(Vector2(-to.y, to.x))

        # --- drinking takes over movement only when genuinely low ---
        if self.style != "passive" and pl.mass < self.drink_below:
            pud = min(
                (q for q in game.puddles if q.ink > 0.03),
                key=lambda q: (q.pos - pl.pos).length() - q.ink * 50.0,
                default=None,
            )
            if pud is not None and (pud.pos - pl.pos).length() > pud.radius * 0.5:
                # _steer only adds keys, so the orbit keys from above have to go
                # first or the two directions cancel and the bot walks nowhere.
                self.keys.clear()
                self._steer(pud.pos - pl.pos)

        # --- aim and fire, unconditionally ---
        if self.style == "passive":
            self.buttons = (False, False, False)
            return
        target = self._target(pl, boss)
        self.mouse = (int(target.x), int(target.y))
        # Fire whenever the trigger is ready and there is ink to spare. The
        # 0.14 floor is mass above the death threshold, not a magazine.
        self.buttons = (pl.shot_cd <= 0 and pl.mass > self.fire_above, False, False)


def fight(style: str, seed: int, limit: float = 200.0) -> dict:
    random.seed(seed)
    pygame.event.clear()
    pilot = Pilot(style)
    pilot.install()
    game = Game(pygame.display.get_surface())
    game.state = Game.STATE_PLAY
    game.wave = 4
    game.start_wave()
    seen = False
    opened = 0
    phases = 0
    last_open = False
    last_phase = 0
    for frame in range(int(limit * 60)):
        pilot.drive(game)
        game.update(1 / 60)
        boss = next((e for e in game.enemies if e.kind == "boss"), None)
        if boss is not None:
            seen = True
            if boss.open and not last_open:
                opened += 1
            last_open = boss.open
            if boss.phase_n != last_phase:
                phases = boss.phase_n
                last_phase = boss.phase_n
        elif seen:
            return {"style": style, "seed": seed, "result": "killed",
                    "t": frame / 60, "opens": opened}
        if game.state == Game.STATE_OVER:
            return {"style": style, "seed": seed, "result": "died",
                    "t": frame / 60, "opens": opened, "phases": phases}
    boss = next((e for e in game.enemies if e.kind == "boss"), None)
    return {"style": style, "seed": seed, "result": "timeout", "t": limit,
            "opens": opened, "phases": phases,
            "head": round(boss.head_hp, 1) if boss else 0}


def main() -> int:
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    pygame.display.set_mode((C.WIDTH, C.HEIGHT))

    from inkfall.entities import Boss

    print(f"arms={Boss.ARM_COUNT} arm_hp={Boss.ARM_HP} head={Boss.HEAD_HP} "
          f"tip={int(Boss.TIP_FRACTION * 100)}% stagger={Boss.STAGGER}s")
    print()

    ok = True
    for style in ("arms", "body", "passive"):
        runs = [fight(style, s) for s in (1, 2, 3, 4)]
        kills = [r for r in runs if r["result"] == "killed"]
        deaths = [r for r in runs if r["result"] == "died"]
        times = [round(r["t"], 1) for r in kills]
        opens = [r["opens"] for r in runs]
        print(f"{style:8s} killed {len(kills)}/4  died {len(deaths)}/4  "
              f"times {times}  head-opens {opens}")

    print()
    arms = [fight("arms", s) for s in (1, 2, 3, 4)]
    body = [fight("body", s) for s in (1, 2, 3, 4)]
    passive = [fight("passive", s) for s in (1, 2, 3, 4)]

    if not all(r["result"] == "killed" for r in arms):
        print("FAIL: a player who targets the arms cannot always finish it")
        ok = False
    else:
        print("OK: targeting arms kills it every time")
    # Aiming only at the head cannot damage the head, but a shot on that line
    # can pass through a tip zone on the way, and under the tip-only hitbox
    # that is a real hit. So the test is that it is far slower, not impossible.
    body_kills = [r["t"] for r in body if r["result"] == "killed"]
    arm_kills = [r["t"] for r in arms if r["result"] == "killed"]
    if body_kills and (not arm_kills or min(body_kills) < max(arm_kills) * 1.5):
        print("FAIL: aiming at the body is as good as aiming at the tips, "
              "so the tip zone means nothing")
        ok = False
    else:
        print(f"OK: aiming at the body is much slower ({[round(t,1) for t in body_kills]} "
              f"vs {[round(t,1) for t in arm_kills]})")
    if any(r["result"] == "killed" for r in passive):
        print("FAIL: a player who never fires can win")
        ok = False
    else:
        print("OK: not fighting back loses")
    if any(r["opens"] == 0 for r in arms):
        print("FAIL: the head never opened in some runs")
        ok = False
    else:
        print(f"OK: the head opened {[r['opens'] for r in arms]} times across runs")
    pygame.quit()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
