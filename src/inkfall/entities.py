"""Particles, droplets, puddles, orbs, and the creatures drawn on the page."""

from __future__ import annotations

import math
import random

import pygame
from pygame import Vector2

from . import config as C
from .config import clamp, lerp_color
from .draw import aa_circle, aa_polygon, add_glow, blob_points, shade_blob


def norm(v: Vector2) -> Vector2:
    length = v.length()
    return v / length if length > 0.0001 else Vector2(1, 0)


# ==========================================================================
# particles
# ==========================================================================
class Particle:
    __slots__ = ("pos", "vel", "life", "max_life", "radius", "color", "end_color", "drag", "kind")

    def __init__(self, pos, vel, life, radius, color, end_color=None, drag=2.2, kind="dot"):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = life
        self.max_life = life
        self.radius = radius
        self.color = color
        self.end_color = end_color or color
        self.drag = drag
        self.kind = kind


class Particles:
    def __init__(self) -> None:
        self.items: list[Particle] = []

    def add(self, pos, vel, life, radius, color, end_color=None, drag=2.2, kind="dot") -> None:
        if len(self.items) >= C.MAX_PARTICLES:
            self.items.pop(0)
        self.items.append(Particle(pos, vel, life, radius, color, end_color, drag, kind))

    def burst(self, pos, count, speed, life, radius, color, end_color=None, drag=2.6, spread=math.tau, direction=0.0):
        for _ in range(count):
            a = direction + random.uniform(-spread / 2, spread / 2)
            s = random.uniform(speed * 0.3, speed)
            self.add(
                pos,
                (math.cos(a) * s, math.sin(a) * s),
                random.uniform(life * 0.55, life),
                random.uniform(radius * 0.5, radius),
                color,
                end_color,
                drag,
                "streak" if random.random() < 0.35 else "dot",
            )

    def update(self, dt: float) -> None:
        alive = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            p.vel *= math.exp(-p.drag * dt)
            p.pos += p.vel * dt
            alive.append(p)
        self.items = alive

    def draw(self, surf: pygame.Surface) -> None:
        for p in self.items:
            t = p.life / p.max_life
            col = lerp_color(p.end_color, p.color, t)
            r = p.radius * (0.3 + 0.7 * t)
            if p.kind == "streak" and p.vel.length_squared() > 400:
                d = norm(p.vel) * min(11.0, p.vel.length() * 0.022)
                n = Vector2(-d.y, d.x) * 0.45
                aa_polygon(
                    surf,
                    [
                        (p.pos.x + n.x, p.pos.y + n.y),
                        (p.pos.x - d.x * 0.3, p.pos.y - d.y * 0.3),
                        (p.pos.x - n.x, p.pos.y - n.y),
                        (p.pos.x - d.x, p.pos.y - d.y),
                    ],
                    col,
                )
            else:
                pygame.draw.circle(surf, col, (int(p.pos.x), int(p.pos.y)), max(1, int(r)))


# ==========================================================================
# droplets
# ==========================================================================
class Drop:
    """A droplet in flight. Friendly drops stain the paper when they land."""

    def __init__(self, pos, vel, radius, damage, friendly=True, life=1.4, heavy=False, color=C.INK, stains=None):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.radius = radius
        self.damage = damage
        self.friendly = friendly
        self.life = life
        self.heavy = heavy
        self.color = color
        # A friendly droplet always stains. A hostile one only does if the
        # firer wants its ink back, which is how the boss plays by the same
        # rules as the player.
        self.stains = friendly if stains is None else stains
        self.dead = False
        self.phase = random.uniform(0, 6.28)
        self.trail = 0.0

    def update(self, dt: float, game) -> None:
        self.life -= dt
        self.pos += self.vel * dt
        if self.friendly:
            self.vel *= math.exp(-0.5 * dt)
            self.trail += dt
            if self.trail > 0.032 and self.vel.length() > 120:
                self.trail = 0.0
                game.particles.add(
                    self.pos, -self.vel * 0.12, 0.22, self.radius * 0.5, C.INK_SOFT, C.INK_PALE, 3.0
                )
        self.phase += dt * 9.0
        if self.life <= 0:
            self.dead = True
            self.splat(game)
        elif not (-50 < self.pos.x < C.WIDTH + 50 and -50 < self.pos.y < C.HEIGHT + 50):
            # Intentional, not a missing splat() call. A droplet that leaves
            # the page is gone and leaves nothing behind, so ink fired into a
            # wall is spent and cannot be reclaimed. That is the scarcity the
            # rest of the design assumes: shooting wildly at the boundary
            # should cost you, exactly as the README's "shoot only what you
            # must, then drink the mess you made" loop implies.
            #
            # The 50px margin is part of it too, not an off-by-something: it
            # is the point past which the droplet is clearly off the page and
            # not merely touching the frame.
            self.dead = True

    def splat(self, game) -> None:
        if self.stains:
            game.add_puddle(
                self.pos,
                self.radius * (2.4 if self.heavy else 1.7),
                0.026 if not self.heavy else 0.09,
                self.color,
            )
        game.particles.burst(
            self.pos,
            7 if not self.heavy else 18,
            150 if not self.heavy else 300,
            0.34,
            self.radius * 0.8,
            C.INK,
            C.INK_SOFT,
        )
        if self.heavy:
            game.shake(6.0)
            game.ring(self.pos, self.radius * 9, C.INK_MID, 0.3)

    def draw(self, surf: pygame.Surface) -> None:
        spd = self.vel.length()
        n = norm(self.vel)
        t = Vector2(-n.y, n.x)
        r = self.radius
        stretch = 1.0 + min(0.9, spd / 1200)
        pts = []
        for i in range(12):
            a = math.tau * i / 12
            rr = r * (1.0 + 0.14 * math.sin(a * 3 + self.phase))
            sx = math.sin(a) * rr * stretch
            sy = math.cos(a) * rr * 0.8
            pts.append((self.pos.x + n.x * sx + t.x * sy, self.pos.y + n.y * sx + t.y * sy))
        if self.heavy:
            add_glow(surf, self.pos.x, self.pos.y, int(r * 3.4), C.INK_MID, 110)
        aa_polygon(surf, pts, self.color)


# ==========================================================================
# orbs
# ==========================================================================
class Orb:
    """A bead of released ink. Drifts to you if you are close."""

    def __init__(self, pos, value=0.05):
        self.pos = Vector2(pos)
        a = random.uniform(0, math.tau)
        s = random.uniform(60, 200)
        self.vel = Vector2(math.cos(a), math.sin(a)) * s
        self.value = value
        self.life = 13.0
        self.radius = 3.2 + clamp(value, 0, 0.2) * 52
        self.phase = random.uniform(0, 6.28)
        self.dead = False
        self.collected = False

    def update(self, dt: float, player) -> None:
        self.life -= dt
        self.phase += dt * 4.2
        to = player.pos - self.pos
        d = to.length()
        reach = C.ORB_MAGNET + player.radius
        if 1.0 < d < reach:
            pull = 1.0 - d / reach
            self.vel += norm(to) * (1500 * pull * pull) * dt
        self.vel *= math.exp(-2.3 * dt)
        self.pos += self.vel * dt
        self.pos.x = clamp(self.pos.x, -20, C.WIDTH + 20)
        self.pos.y = clamp(self.pos.y, -20, C.HEIGHT + 20)
        if d < player.radius * 0.95:
            self.collected = True
            self.dead = True

    def draw(self, surf: pygame.Surface) -> None:
        pulse = 1.0 + 0.16 * math.sin(self.phase * 2)
        add_glow(surf, self.pos.x, self.pos.y, int(self.radius * 4.5), C.INK_MID, 65)
        aa_circle(surf, self.pos.x, self.pos.y, self.radius * pulse, C.INK)
        aa_circle(surf, self.pos.x - self.radius * 0.3, self.pos.y - self.radius * 0.35, self.radius * 0.3, C.INK_PALE)


# ==========================================================================
# puddles
# ==========================================================================
class Puddle:
    """Spilled ink. You can drink it back; so can everything else."""

    def __init__(self, pos, radius, ink, ink_color=C.INK):
        self.pos = Vector2(pos)
        self.base_radius = radius
        self.radius = radius
        self.ink = ink
        self.base_ink = ink
        self.ink_color = ink_color
        self.age = 0.0
        self.seed = random.uniform(0, 40)
        self.phase = random.uniform(0, 6.28)
        self.dead = False
        self.squish = random.uniform(0.72, 1.0)
        self.spawn = 0.0
        self.flash = 0.0

    @property
    def wet(self) -> float:
        return clamp(self.ink / max(1e-6, self.base_ink), 0.0, 1.0)

    def drink(self, amount: float) -> float:
        amount = min(amount, self.ink)
        self.ink -= amount
        self.flash = min(1.0, self.flash + amount * 6.0)
        if self.ink <= 1e-4:
            self.dead = True
        return amount

    def update(self, dt: float) -> None:
        self.age += dt
        self.spawn = min(1.0, self.spawn + dt * 5.5)
        self.phase += dt * 1.1
        self.flash = max(0.0, self.flash - dt * 2.4)
        self.radius = self.base_radius * (0.55 + 0.45 * math.sqrt(self.wet))
        if self.age > C.PUDDLE_DRY_TIME:
            self.dead = True

    def draw(self, surf: pygame.Surface) -> None:
        grow = self.spawn
        r = self.radius * (0.65 + 0.35 * grow)
        dry = clamp(self.age / C.PUDDLE_DRY_TIME, 0.0, 1.0)
        col = lerp_color(C.PAPER_SHADE, self.ink_color, (1.0 - dry * 0.72) * grow)
        pts = blob_points(self.pos.x, self.pos.y, r, 7, self.phase, self.seed, (1.0, self.squish), 22)
        aa_polygon(surf, pts, col)
        if r > 6:
            inner = blob_points(
                self.pos.x, self.pos.y, r * 0.66, 6, -self.phase * 1.5, self.seed + 9, (1.0, self.squish), 18
            )
            aa_polygon(surf, inner, lerp_color(col, C.INK_PALE, 0.22 + 0.3 * self.flash))
            shine = blob_points(
                self.pos.x - r * 0.26,
                self.pos.y - r * 0.3,
                r * 0.28,
                4,
                self.phase * 2.2,
                self.seed + 3,
                (1.0, self.squish * 0.8),
                12,
            )
            aa_polygon(surf, shine, lerp_color(col, C.WHITE, 0.55))


# ==========================================================================
# effects
# ==========================================================================
class Ring:
    def __init__(self, pos, radius, color, life=0.35, width=2):
        self.pos = Vector2(pos)
        self.radius = radius
        self.color = color
        self.life = life
        self.max_life = life
        self.width = width

    def update(self, dt: float) -> bool:
        self.life -= dt
        return self.life > 0

    def draw(self, surf: pygame.Surface) -> None:
        t = 1.0 - self.life / self.max_life
        r = self.radius * (0.25 + 0.75 * t)
        col = lerp_color(self.color, C.PAPER, t)
        if r > 2:
            pygame.draw.circle(surf, col, (int(self.pos.x), int(self.pos.y)), int(r), max(1, int(self.width * (1 - t) + 1)))


class FloatText:
    def __init__(self, pos, text, color=C.INK, life=0.9, size=18):
        self.pos = Vector2(pos)
        self.text = text
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size

    def update(self, dt: float) -> bool:
        self.life -= dt
        self.pos.y -= 40 * dt
        return self.life > 0


# ==========================================================================
# creatures
# ==========================================================================
class Enemy:
    kind = "blot"
    hp = 3.0
    speed = 62.0
    radius = 15.0
    damage = 0.085
    score = 100
    ink_reward = 0.055
    drink_rate = 0.28
    body = (146, 138, 172)
    ink_puddle = C.PAPER_SHADE

    def __init__(self, pos, wave=1):
        self.pos = Vector2(pos)
        self.vel = Vector2()
        ang = random.uniform(0, math.tau)
        self.wander = Vector2(math.cos(ang), math.sin(ang))
        self.max_hp = self.hp * (1.0 + 0.10 * (wave - 1))
        self.hp = self.max_hp
        self.growth = 0.0
        self.hit_flash = 0.0
        self.ink_coat = 0.0
        self.phase = random.uniform(0, 6.28)
        self.seed = random.uniform(0, 40)
        self.dead = False
        self.spawn_anim = 0.0
        self.drunk = 0.0
        self.stun = 0.0
        self.aim = Vector2(0, 1)
        self.squash = Vector2(1, 1)
        self.wave = wave

    @property
    def effective_radius(self) -> float:
        return self.radius * (1.0 + self.growth * 0.55) * (0.4 + 0.6 * self.spawn_anim)

    def steering(self, game, dt: float) -> Vector2:
        to = game.player.pos - self.pos
        d = max(1.0, to.length())
        self.wander += Vector2(random.uniform(-1, 1), random.uniform(-1, 1)) * dt * 2.4
        if self.wander.length_squared() < 0.01:
            self.wander = Vector2(1, 0)
        self.wander = norm(self.wander)
        return norm(to / d + self.wander * 0.45)

    def update(self, dt: float, game) -> None:
        self.phase += dt * (2.4 + self.vel.length() * 0.02)
        self.spawn_anim = min(1.0, self.spawn_anim + dt * 3.2)
        self.hit_flash = max(0.0, self.hit_flash - dt * 5.0)
        self.stun = max(0.0, self.stun - dt)
        self.ink_coat = max(0.0, self.ink_coat - dt * 0.05)
        self.squash += (Vector2(1, 1) - self.squash) * min(1.0, dt * 8)

        if self.stun <= 0:
            steer = self.steering(game, dt)
            slow = 1.0 - 0.45 * min(1.0, self.ink_coat)
            target = steer * self.speed * slow
            self.vel += (target - self.vel) * min(1.0, dt * 4.2)
        self.vel *= math.exp(-1.4 * dt)
        self.pos += self.vel * dt
        to = game.player.pos - self.pos
        self.aim = norm(to) if to.length_squared() > 1 else Vector2(0, 1)
        self.drink(game, dt)
        self.think(dt, game)

        m = self.effective_radius
        if self.pos.x < m:
            self.pos.x = m
            self.vel.x = abs(self.vel.x) * 0.4
        elif self.pos.x > C.WIDTH - m:
            self.pos.x = C.WIDTH - m
            self.vel.x = -abs(self.vel.x) * 0.4
        if self.pos.y < m:
            self.pos.y = m
            self.vel.y = abs(self.vel.y) * 0.4
        elif self.pos.y > C.HEIGHT - m:
            self.pos.y = C.HEIGHT - m
            self.vel.y = -abs(self.vel.y) * 0.4

    def drink(self, game, dt: float) -> None:
        for p in game.puddles:
            if p.dead or p.ink <= 0:
                continue
            reach = self.effective_radius * 0.7 + p.radius * 0.8
            if (p.pos - self.pos).length_squared() < reach * reach:
                got = p.drink(self.drink_rate * dt)
                self.growth = min(1.5, self.growth + got * 0.55)
                self.drunk += got
                if got > 0.0008 and random.random() < 0.14:
                    game.particles.add(
                        p.pos + Vector2(random.uniform(-4, 4), random.uniform(-4, 4)),
                        (0, -30),
                        0.3,
                        2.0,
                        C.INK,
                        C.INK_SOFT,
                        2.0,
                    )
                if self.growth > 0.8:
                    self.hp = min(self.max_hp, self.hp + got * 1.2)
                break

    def think(self, dt: float, game) -> None:
        pass

    def take_damage(self, amount: float, game, knockback=None, coat=0.5) -> None:
        if self.dead:
            return
        mult = 1.0 + 0.45 * min(1.0, self.ink_coat)
        self.hp -= amount * mult
        self.hit_flash = 1.0
        self.ink_coat = min(1.6, self.ink_coat + coat)
        self.vel += knockback if knockback is not None else Vector2()
        self.squash = Vector2(1.22, 0.82)
        if self.hp <= 0:
            self.die(game)

    def die(self, game) -> None:
        if self.dead:
            return
        self.dead = True
        game.particles.burst(
            self.pos, int(14 + self.effective_radius * 0.6), 260, 0.6, self.effective_radius * 0.35, C.INK, C.INK_SOFT, 2.0
        )
        game.spawn_orbs(self.pos, self.ink_reward + min(0.25, self.drunk * 0.5), int(2 + self.growth * 4))
        game.add_puddle(self.pos, self.effective_radius * 1.0, self.ink_reward * 0.6 * (1 + self.growth), self.ink_puddle)
        game.on_kill(self)

    def draw(self, surf: pygame.Surface) -> None:
        r = self.effective_radius
        if r < 1:
            return
        sx = self.squash.x * (0.92 + 0.16 * math.sin(self.phase))
        sy = self.squash.y * (1.08 - 0.16 * math.sin(self.phase))
        body = self.body
        if self.ink_coat > 0.03:
            body = lerp_color(body, C.INK, min(1.0, self.ink_coat * 0.9))
        pts = blob_points(self.pos.x, self.pos.y, r, 6, self.phase, self.seed, (sx, sy), 20)
        aa_polygon(surf, pts, body)
        if self.hit_flash > 0.02:
            flash = blob_points(self.pos.x, self.pos.y, r * 0.92, 6, self.phase, self.seed, (sx, sy), 20)
            aa_polygon(surf, flash, lerp_color(body, C.WHITE, self.hit_flash * 0.85))
        self.draw_face(surf, r)
        if self.growth > 0.15:
            pygame.draw.circle(surf, C.VERMILION, (int(self.pos.x), int(self.pos.y)), int(r) + 2, 1)

    def draw_face(self, surf: pygame.Surface, r: float) -> None:
        look = self.aim * (r * 0.22)
        eye_r = max(1.6, r * 0.14)
        for side in (-1, 1):
            ex = self.pos.x + look.x + side * r * 0.34
            ey = self.pos.y + look.y - r * 0.1
            pygame.draw.circle(surf, C.WHITE, (int(ex), int(ey)), max(1, int(eye_r + 0.9)))
            pygame.draw.circle(surf, C.INK, (int(ex + look.x * 0.3), int(ey + look.y * 0.3)), max(1, int(eye_r * 0.55)))
        my = self.pos.y + look.y + r * 0.42
        pygame.draw.line(
            surf,
            C.INK,
            (self.pos.x - r * 0.3, my),
            (self.pos.x + r * 0.3, my),
            max(1, int(r * 0.09)),
        )


class Skitter(Enemy):
    """Small, twitchy, weak. Comes in packs."""

    kind = "skitter"
    hp = 1.5
    speed = 122.0
    radius = 9.5
    damage = 0.05
    score = 70
    ink_reward = 0.035
    drink_rate = 0.16
    body = (172, 163, 192)

    def steering(self, game, dt):
        base = super().steering(game, dt)
        jitter = Vector2(math.sin(self.phase * 3.1 + self.seed), math.cos(self.phase * 2.7 + self.seed))
        return norm(base + jitter * 0.9)

    def draw_face(self, surf, r):
        look = self.aim * (r * 0.26)
        for side in (-1, 1):
            ex = self.pos.x + look.x + side * r * 0.3
            ey = self.pos.y + look.y
            pygame.draw.circle(surf, C.INK, (int(ex), int(ey)), max(1, int(r * 0.2)))


class Blot(Enemy):
    """The baseline bad thought."""

    kind = "blot"
    hp = 4.4
    speed = 68.0
    radius = 17.0
    damage = 0.095
    score = 120
    ink_reward = 0.06
    drink_rate = 0.34

    def think(self, dt, game):
        d = (game.player.pos - self.pos).length()
        if d < 180 and self.stun <= 0:
            self.vel += norm(game.player.pos - self.pos) * 34 * dt * 18


class Sponge(Enemy):
    """Slow, thick, and thirsty. Drinks your ink faster than you can."""

    kind = "sponge"
    hp = 12.0
    speed = 42.0
    radius = 26.0
    damage = 0.13
    score = 220
    ink_reward = 0.09
    drink_rate = 1.1
    body = (160, 152, 176)

    def die(self, game):
        if self.dead:
            return
        super().die(game)
        if self.growth > 0.5:
            game.burst_text(self.pos, "SPLIT", C.VERMILION)
            for i in range(3):
                a = math.tau * i / 3
                game.add_enemy(Skitter(self.pos + Vector2(math.cos(a), math.sin(a)) * 26, self.wave))

    def draw_face(self, surf, r):
        for i in range(7):
            a = self.seed + math.tau * i / 7
            rr = r * (0.32 + 0.16 * math.sin(i * 2.3))
            pygame.draw.circle(
                surf,
                C.INK_SOFT,
                (int(self.pos.x + math.cos(a) * rr), int(self.pos.y + math.sin(a) * rr)),
                max(1, int(r * 0.09)),
            )
        super().draw_face(surf, r)


class Quill(Enemy):
    """Keeps its distance and flicks ink needles at you."""

    kind = "quill"
    hp = 5.2
    speed = 74.0
    radius = 14.0
    damage = 0.06
    score = 170
    ink_reward = 0.07
    drink_rate = 0.2
    body = (150, 142, 176)
    preferred = 250.0

    def __init__(self, pos, wave=1):
        super().__init__(pos, wave)
        self.fire_cd = random.uniform(1.0, 2.0)
        self.charge = 0.0

    def steering(self, game, dt):
        to = game.player.pos - self.pos
        d = max(1.0, to.length())
        forward = to / d
        side = 1.0 if math.sin(self.phase * 0.6 + self.seed) > 0 else -1.0
        strafe = Vector2(-forward.y, forward.x) * side
        err = clamp((d - self.preferred) / self.preferred, -1.0, 1.0)
        return norm(strafe * 0.9 + forward * err)

    def think(self, dt, game):
        self.fire_cd -= dt
        self.charge = max(0.0, self.charge - dt * 3.0)
        d = (game.player.pos - self.pos).length()
        if self.fire_cd <= 0 and d < 430:
            self.fire_cd = max(0.5, 1.7 - self.wave * 0.05) + random.uniform(-0.2, 0.35)
            self.charge = 1.0
            aim = norm(game.player.pos - self.pos)
            game.add_drop(
                Drop(
                    self.pos + self.aim * self.effective_radius,
                    aim * 330,
                    4.0,
                    0.055,
                    friendly=False,
                    life=2.6,
                    color=C.VERM_DARK,
                )
            )
            game.particles.burst(self.pos + aim * self.effective_radius, 4, 120, 0.2, 2.0, C.VERMILION, C.VERM_PALE)

    def draw(self, surf: pygame.Surface) -> None:
        r = self.effective_radius
        super().draw(surf)
        tip = self.pos + self.aim * (r * 1.9)
        side = Vector2(-self.aim.y, self.aim.x)
        base_l = self.pos + side * (r * 0.42) + self.aim * r * 0.5
        base_r = self.pos - side * (r * 0.42) + self.aim * r * 0.5
        aa_polygon(surf, [tip, base_l, base_r], C.INK)
        if self.charge > 0.05:
            add_glow(surf, tip.x, tip.y, int(10 + 14 * self.charge), C.VERMILION, 120)


class Squid(Enemy):
    """Grapples from mid range and siphons your body while latched."""

    kind = "squid"
    hp = 7.0
    speed = 46.0
    radius = 18.0
    damage = 0.035
    score = 240
    ink_reward = 0.08
    drink_rate = 0.22
    body = (138, 128, 168)
    # sits just outside its own grab, so a lash is a decision it makes
    # by stepping in, rather than an aura it always carries
    preferred = 118.0

    # The tendril art is drawn out to TENDRIL_BASE * TENDRIL_STRETCH body radii,
    # with a further half radius of forward offset. Deriving the grab range from
    # those numbers keeps the hitbox no longer than what the player can see.
    TENDRIL_BASE = 1.6
    TENDRIL_STRETCH = 3.6

    def __init__(self, pos, wave=1):
        super().__init__(pos, wave)
        self.lash_cd = random.uniform(1.2, 2.2)
        self.tendril = 0.0
        self.latched = 0.0
        self.windup = 0.0

    @property
    def lash_reach(self) -> float:
        r = self.effective_radius
        return r * (self.TENDRIL_BASE * self.TENDRIL_STRETCH + 0.5)

    def steering(self, game, dt):
        to = game.player.pos - self.pos
        d = max(1.0, to.length())
        forward = to / d
        err = clamp((d - self.preferred) / self.preferred, -1.0, 1.0)
        return norm(forward * err + self.wander * 0.4)

    def think(self, dt, game):
        self.lash_cd -= dt
        self.tendril = max(0.0, self.tendril - dt * 1.6)
        self.latched = max(0.0, self.latched - dt)
        d = (game.player.pos - self.pos).length()
        reach = self.lash_reach

        # idle reach-out is cosmetic only, and never longer than the grab
        if d < reach:
            self.tendril = max(self.tendril, 0.35)

        if self.latched > 0:
            game.player.vel -= norm(game.player.pos - self.pos) * 40 * dt
            if game.player.mass > C.MASS_DEATH + 0.003:
                game.player.mass -= 0.03 * dt
                game.player.siphoned = 0.3
                if random.random() < 0.25:
                    game.particles.add(
                        self.pos, norm(game.player.pos - self.pos) * -60, 0.4, 2.2, C.INK, C.INK_SOFT, 1.0
                    )

        if self.windup > 0:
            # committed: the tendril is already out, so a player who dashes or
            # steps out of reach during the tell escapes the grab
            self.windup -= dt
            self.tendril = 1.0
            if self.windup <= 0 and d < reach:
                self.latched = 1.2
                game.player.hurt(0.07, game, norm(game.player.pos - self.pos) * 120)
                game.player.vel += norm(self.pos - game.player.pos) * 260
        elif self.lash_cd <= 0 and d < reach:
            self.windup = 0.34
            self.lash_cd = random.uniform(2.6, 4.0)
            game.ring(self.pos, reach, C.VERMILION, 0.34, 2)

    def draw(self, surf: pygame.Surface) -> None:
        r = self.effective_radius
        # tendrils first, behind the head
        for i in range(5):
            a = self.phase * 0.9 + i * 0.5
            length = r * (self.TENDRIL_BASE + 0.8 * math.sin(self.seed + i)) * (1.0 + self.tendril * (self.TENDRIL_STRETCH - 1.0))
            pts = [self.pos]
            for step in range(1, 7):
                t = step / 6
                wob = math.sin(a + t * 4.0 + self.phase * 2.0) * r * 0.5 * t
                d = self.aim if self.tendril > 0.4 else Vector2(math.cos(a), math.sin(a))
                side = Vector2(-d.y, d.x) * wob
                pts.append(self.pos + d * (length * t) + side + self.aim * (r * 0.5))
            col = C.VERMILION if self.windup > 0 else C.INK_MID
            pygame.draw.lines(surf, col, False, [(int(x), int(y)) for x, y in pts], max(1, int(2 + r * 0.12)))
        super().draw(surf)
        if self.latched > 0:
            add_glow(surf, self.pos.x, self.pos.y, int(r * 4), C.VERMILION, 70)

    def draw_face(self, surf, r):
        look = self.aim * (r * 0.2)
        for side in (-1, 1):
            ex = self.pos.x + look.x + side * r * 0.24
            ey = self.pos.y + look.y - r * 0.12
            pygame.draw.circle(surf, C.WHITE, (int(ex), int(ey)), max(1, int(r * 0.16)))
            pygame.draw.circle(surf, C.INK, (int(ex), int(ey)), max(1, int(r * 0.08)))


class Arm:
    """One of the eight tentacles.

    Slow-drifting, open to fire whenever the head is closed, and it shoots at
    the player on its own clock like a Quill. Killing one is the only way to
    get at the head, so the arms are the puzzle and the head is the reward.
    """

    __slots__ = (
        "boss", "index", "base_angle", "phase", "drift_speed", "amp",
        "length", "hp", "max_hp", "alive", "fire_cd", "hit_flash",
        "seed", "recoil", "charging", "curl_dir",
    )

    def __init__(self, boss, index: int) -> None:
        self.boss = boss
        self.index = index
        self.base_angle = (
            math.tau * index / boss.ARM_COUNT + random.uniform(-0.16, 0.16)
        )
        self.phase = random.uniform(0, math.tau)
        self.drift_speed = random.uniform(0.30, 0.55)
        self.amp = random.uniform(0.16, 0.28)
        self.length = random.uniform(130.0, 200.0)
        self.hp = boss.ARM_HP
        self.max_hp = boss.ARM_HP
        self.alive = True
        # staggered so eight arms do not volley together
        self.fire_cd = random.uniform(0.9, boss.FIRE_BASE)
        self.hit_flash = 0.0
        self.seed = random.uniform(0, 40)
        self.recoil = 0.0
        self.charging = 0.0
        self.curl_dir = random.choice((-1.0, 1.0))

    @property
    def angle(self) -> float:
        return self.base_angle + math.sin(self.phase) * self.amp

    def tip(self) -> Vector2:
        a = self.angle
        d = self.boss.effective_radius + self.length
        return self.boss.pos + Vector2(math.cos(a), math.sin(a)) * d

    def points(self, segments: int = 14):
        """Tapering curve from the body to the tip, for drawing and aiming.

        A single gentle S so the arm reads as a limb rather than a spoke, with
        the bend easing to zero at the root so it stays attached to the body.
        """
        a = self.angle
        near = self.boss.effective_radius * 0.30
        far = self.boss.effective_radius + self.length
        perp = Vector2(-math.sin(a), math.cos(a))
        out = []
        for k in range(segments + 1):
            t = k / segments
            d = near + (far - near) * t
            # Two independent bends, one swimming through the length and one
            # curling steadily away, so each arm trails rather than points.
            wave = math.sin(t * 2.2 + self.phase * 1.5 + self.seed * 0.1) * self.length * 0.11
            # Curl only near the tip, and never enough to bring the arm back
            # inside the mantle, which drew limbs across the face.
            curl = (t ** 3.0) * self.length * 0.16 * self.curl_dir
            bend = (wave + curl) * min(1.0, t * 1.6)
            out.append(self.boss.pos + Vector2(math.cos(a), math.sin(a)) * d + perp * bend)
        return out

    def tip_zone(self, segments: int = 14):
        """The last fifth of the arm, which is the only part that can be hurt.

        Returns the tail of the same curve that is drawn, so the hitbox and the
        artwork cannot drift apart. The arm above this point is a decoy: shots
        that land there pass through without doing anything.
        """
        pts = self.points(segments)
        return pts[int(len(pts) * 0.8):]


class Boss(Enemy):
    """OCTOPUS: eight arms, one head, and a lock that only opens from outside.

    The head is armoured and cannot be hurt. The arms are the only lever, and
    only their tips are vulnerable: the last fifth of each arm can be shot, and
    anything that lands further up the limb passes straight through. That makes
    the arms a moving target rather than a wall, because the player has to hit
    the whip end while it sweeps.

    Sever an arm and the head opens, and stays open until the player lands
    exactly one increment of damage, one eighth of the head. It then re-armours,
    pauses, and comes back angrier: faster firing, darker, more ragged. Eight
    arms and eight increments, so every arm is worth exactly one step and the
    fight ends when the last one is spent.

    Arms never grow back. There is no softlock from that: the head stays open
    until its increment is paid, so the player can never run out of levers with
    a closed head. Nothing here heals, and the body darkens toward ink as the
    fight goes on, ending the same colour every other corpse does.
    """

    kind = "boss"
    ARM_COUNT = 8
    # Each arm is a permanent resource that never returns, and a hit requires
    # catching a moving tip zone rather than any point of a wide disc. Raised
    # from 6.0 because a competent player was stripping arms faster than the
    # patience ramp below ever had time to matter.
    ARM_HP = 8.0
    HEAD_HP = 28.0

    # One arm per checkpoint. Severing an arm opens the head for exactly one
    # increment, so eight arms is eight steps and the pool is spent on the last.
    CHECKPOINTS = 8

    # Only the last fifth of the arm can be hit. Everything above it is a
    # decoy that drops absorb without effect.
    TIP_FRACTION = 0.2
    ARM_HIT_RADIUS = 15.0
    ARM_WIDTH = 15.0        # widest part of a limb, at the root
    TIP_INK = 0.070         # ink left by a tip hit, which must fund the fight
    STAGGER = 2.4           # pause after each step, before the arms resume
    FIRE_BASE = 6.0         # arm fire cooldown at full health
    # Per checkpoint. Halved from 0.13 when the count went from 4 to 8, so the
    # run of eight reaches a similar final rate instead of pinning at the
    # 0.85s floor by the sixth step and then escalating no further.
    FIRE_STEP = 0.055

    # Impatience. The longer the player goes without taking an arm, the faster
    # the surviving arms fire, so stalling is punished and the fight keeps
    # moving. Reset to zero by every sever, so the ramp is about pressure
    # between successes rather than about total fight length.
    #
    # The ramp keeps climbing rather than saturating, because the request is
    # that it tracks how long it has been since the last kill. It is curved
    # (0.6 power) so the opening seconds recover quickly after a sever, and it
    # is capped by FIRE_FLOOR so it can never become an unwinnable wall.
    PATIENCE = 10.0         # seconds of quiet per unit of the ramp
    PATIENCE_FIRE = 0.80    # fraction of cooldown removed per unit of ramp
    FIRE_FLOOR = 2.2        # shortest possible cooldown, however impatient

    damage = 0.09
    radius = 50.0
    speed = 96.0
    score = 2200
    ink_reward = 0.55
    drink_rate = 0.0        # deliberately no healing

    def __init__(self, pos, wave=1):
        super().__init__(pos, wave)
        self.head_max = self.HEAD_HP * (1.0 + 0.05 * (wave - 1))
        self.head_hp = self.head_max
        self.hp = self.head_hp
        self.max_hp = self.head_max
        self.phase_n = 0
        self.armored = True
        self.stagger = 0.0
        self.spin = 0.0
        self.wince = 0.0
        self.arms = [Arm(self, i) for i in range(self.ARM_COUNT)]
        self.severed = 0
        # Damage banked during the current open window, toward one increment.
        self.open_damage = 0.0
        # Seconds since the player last took an arm. Drives the fire ramp.
        self.since_sever = 0.0

    # ------------------------------------------------------------------
    @property
    def effective_radius(self) -> float:
        return self.radius * (0.55 + 0.45 * self.spawn_anim)

    @property
    def reach(self) -> float:
        """How far the animal actually extends, for clamping and hit tests.

        Measured from the drawn curve rather than from the arm's nominal
        length: the sideways bend and the arm's own thickness both add to the
        footprint, and using the nominal length let the outsides of the limbs
        draw past the page edge.
        """
        span = self.effective_radius
        for arm in self.arms:
            if not arm.alive:
                continue
            span = max(span, max((q - self.pos).length() for q in arm.points()))
        return span + self.ARM_WIDTH * 0.5

    @property
    def open(self) -> bool:
        """True while the head is waiting for its one increment of damage.

        There is no timer. The head stays open until the player lands a hit,
        which is what guarantees the fight can always be finished: a severed
        arm can never be wasted by being too slow.
        """
        return not self.armored

    @property
    def arm_count(self) -> int:
        return sum(1 for a in self.arms if a.alive)

    def _step(self) -> float:
        return self.head_max / self.CHECKPOINTS

    @property
    def impatience(self) -> float:
        """How long it has been since an arm was taken, in ramps.

        0 immediately after a sever and growing without a hard ceiling; the
        cooldown floor in think() is what finally bounds it.
        """
        return max(0.0, self.since_sever / max(1e-6, self.PATIENCE))

    def steering(self, game, dt):
        """Follows you at a distance, which is what lets you bait it.

        It is fast enough to keep up but not to catch you, so a player can lead
        it to one side of the page and double back to drink the spill it left
        behind. If it just sat on its own ink there would be no way to reclaim
        anything.
        """
        to = game.player.pos - self.pos
        d = max(1.0, to.length())
        radial = to / d
        # Keep the whole animal on the page. The reach is the mantle plus the
        # longest arm, so it never draws half off-screen or under the HUD.
        pad = self.reach + 8.0
        off = Vector2()
        if self.pos.x < pad:
            off.x += (pad - self.pos.x) / pad
        elif self.pos.x > C.WIDTH - pad:
            off.x -= (self.pos.x - (C.WIDTH - pad)) / pad
        if self.pos.y < pad:
            off.y += (pad - self.pos.y) / pad
        elif self.pos.y > C.HEIGHT - pad:
            off.y -= (self.pos.y - (C.HEIGHT - pad)) / pad
        if off.length_squared() > 0.02:
            return norm(off) * 1.4
        if d > 250:
            return radial
        if d < 150:
            return -radial * 0.8
        # Otherwise circle, which keeps it moving rather than parked.
        tangent = Vector2(-radial.y, radial.x) * (1.0 if self.phase_n % 2 == 0 else -1.0)
        return tangent * 0.55

    def think(self, dt, game):
        self.spin += dt * 0.5
        self.wince = max(0.0, self.wince - dt * 2.0)
        self.since_sever += dt

        if self.stagger > 0:
            self.stagger -= dt
            if self.stagger <= 0:
                self.stagger = 0.0
                # Do not re-armour here. A player who severs another arm during
                # the pause opens the head again, and closing it on the stagger
                # timer threw that window away without paying for it, so an arm
                # could be spent for nothing and the boss could stall with arms
                # still to give. Only paying an increment closes the head.

        can_fire = self.armored and self.stagger <= 0 and not self.open

        for arm in self.arms:
            if not arm.alive:
                # Arms are gone for good. Nothing regrows.
                continue
            arm.phase += dt * arm.drift_speed
            arm.hit_flash = max(0.0, arm.hit_flash - dt * 5.0)
            arm.recoil = max(0.0, arm.recoil - dt * 5.0)
            if can_fire:
                arm.fire_cd -= dt
                arm.charging = 1.0 if arm.fire_cd < 0.5 else 0.0
                if arm.fire_cd <= 0:
                    self._arm_fire(arm, game)
                    base = self.FIRE_BASE * (1.0 - self.FIRE_STEP * self.phase_n)
                    # Impatience shortens the cooldown, so a player who stops
                    # taking arms faces steadily more shots, with no plateau.
                    # The 0.6 power keeps the first seconds after a sever close
                    # to calm, and FIRE_FLOOR keeps it survivable.
                    base /= 1.0 + self.PATIENCE_FIRE * (self.impatience ** 0.6)
                    arm.fire_cd = max(self.FIRE_FLOOR, base * random.uniform(0.78, 1.25))
                    arm.charging = 0.0
            else:
                arm.charging = 0.0

        self.clamp_to_page()



    # ------------------------------------------------------------------
    def _arm_fire(self, arm, game):
        target = game.player.pos
        direction = norm(target - arm.tip())
        speed = 300.0 + 45.0 * self.phase_n
        game.add_drop(
            Drop(
                arm.tip(),
                direction * speed,
                5.2,
                0.026,
                False,
                1.3,
                color=C.VERM_DARK,
                stains=True,
            )
        )
        arm.recoil = 1.0
        game.audio.play("shoot", 0.16)

    def _sever(self, arm, game):
        arm.alive = False
        self.severed += 1
        # Taking an arm buys calm: the patience ramp starts over.
        self.since_sever = 0.0
        # The head opens and stays open until the increment is paid.
        self.armored = False
        tip = arm.tip()
        game.particles.burst(tip, 22, 260, 0.6, 3.4, C.VERM_DARK, C.VERM_PALE, 2.0)
        game.add_puddle(tip, 18, 0.05, C.VERM_DARK)
        game.ring(tip, 52, C.VERMILION, 0.35, 3)
        game.audio.play("kill", 0.6)
        game.burst_text(tip + Vector2(0, -14), "OPEN", C.GOLD, 20)
        game.shake(6.0)

    def _checkpoint(self, game):
        """Reached the next eighth: armour up, pause, get angrier."""
        self.armored = True
        self.stagger = self.STAGGER
        game.particles.burst(self.pos, 34, 300, 0.8, 4.2, C.INK, C.VERM_PALE, 1.8)
        game.ring(self.pos, self.effective_radius * 3.4, C.VERMILION, 0.55, 4)
        game.shake(11.0)
        game.hitstop = max(game.hitstop, 0.07)
        game.audio.play("boss", 0.8)
        label = f"{round(self.phase_n * 100 / self.CHECKPOINTS)}%"
        game.burst_text(self.pos + Vector2(0, -self.effective_radius - 20), label, C.VERMILION, 22)

    # ------------------------------------------------------------------
    def take_arm_hit(self, drop, game) -> bool:
        """Called by the game when a player droplet is inside an arm's reach.

        Only the tip zone takes damage. A shot anywhere else along the limb is
        absorbed and does nothing at all, which is the whole point of the
        zone: the player has to hit the far end while it moves. Returning True
        in that case consumes the droplet, so a wasted shot is a real cost.

        While the head is open the arms are inert, and shots pass through to
        the head instead.
        """
        if self.dead or self.open:
            return False
        touch = (self.ARM_HIT_RADIUS + drop.radius) ** 2
        for arm in self.arms:
            if not arm.alive:
                continue
            pts = arm.points()
            # Where along the limb did the droplet land? Nearest point on the
            # drawn curve, so the hitbox cannot disagree with the artwork.
            best = -1
            best_d = touch
            for i, q in enumerate(pts):
                d = (q - drop.pos).length_squared()
                if d <= best_d:
                    best_d = d
                    best = i
            if best < 0:
                continue
            # Past the tip zone the limb is a decoy and does nothing. It does
            # not swallow the droplet either: a shot travelling out toward a
            # tip has to cross the limb to get there, so consuming it here
            # made tips unreachable in practice and the boss unkillable. The
            # droplet passes through untouched and may still hit the tip on a
            # later frame.
            if best < int(len(pts) * (1.0 - self.TIP_FRACTION)):
                continue
            arm.hp -= drop.damage
            arm.hit_flash = 1.0
            # A tip hit is a hard shot and pays for itself. The fight needs
            # roughly ninety of them, and at the standard splat yield the ink
            # economy could not fund that no matter how well the player drank,
            # so the precision shot is worth more than an ordinary hit.
            game.add_puddle(drop.pos, 11.0, self.TIP_INK, C.INK_MID)
            if arm.hp <= 0:
                self._sever(arm, game)
            else:
                game.particles.burst(drop.pos, 5, 130, 0.26, 2.0, C.VERM_DARK, C.VERM_PALE)
            return True
        return False

    def update(self, dt: float, game) -> None:
        """Move first, then clamp, so the clamp is never a frame stale."""
        super().update(dt, game)
        if not self.dead:
            self.clamp_to_page()

    def clamp_to_page(self) -> None:
        """Keep the whole animal on the page and clear of the HUD.

        The ink bar and the boss health bar occupy the bottom strip, so the
        creature's skirt is measured against that band, not the window edge.
        """
        # Use the full reach on every side. Using a fraction of it on the top
        # and bottom let the arms hang 24px past the page even while the clamp
        # reported success, which is why the boss kept drawing off-screen.
        pad_x = min(self.reach + 6.0, C.WIDTH * 0.45)
        pad_y = min(self.reach + 6.0, C.HEIGHT * 0.45)
        self.pos.x = clamp(self.pos.x, pad_x, C.WIDTH - pad_x)
        self.pos.y = clamp(self.pos.y, pad_y, C.HEIGHT - pad_y)

    def take_damage(self, amount, game, knockback=None, coat=0.5):
        if self.dead:
            return
        if not self.open:
            # Armoured. Still show the hit, so the rule is learnable without a
            # tutorial line: sparks, no number.
            self.hit_flash = 0.35
            game.particles.burst(self.pos, 3, 120, 0.2, 1.6, C.PAPER, C.INK_PALE)
            return
        # An open head takes exactly one increment and no more. Damage is
        # clipped to what is left of the current increment, so a shot that
        # crosses the boundary cannot overkill into the next one.
        #
        # Without this the two ledgers disagreed: head_hp fell by every shot's
        # full damage while phase_n advanced in whole steps, so the surplus
        # from each crossing shot accumulated and the eighth arm was never
        # needed. Clipping keeps them in lockstep, which is what makes each
        # arm worth exactly one step.
        step = self._step()
        room = max(0.0, step - self.open_damage)
        applied = min(amount, room)
        self.open_damage += applied
        self.head_hp = max(0.0, self.head_hp - applied)
        self.hp = self.head_hp
        self.hit_flash = 1.0
        self.wince = 1.0
        self.squash = Vector2(0.88, 1.14)

        if self.open_damage >= step - 1e-9:
            self.open_damage = 0.0
            self.phase_n += 1
            if self.phase_n >= self.CHECKPOINTS or self.head_hp <= 1e-9:
                self.head_hp = 0.0
                self.phase_n = min(self.CHECKPOINTS, self.phase_n)
                self.die(game)
                return
            self._checkpoint(game)

    # ------------------------------------------------------------------
    def _arm_polygon(self, arm, width: float):
        """A filled, tapered ribbon along the arm's curve.

        Drawing the arm as a chain of lines leaves visible steps and a flat
        silhouette, which is what made it look sloppy beside the rest of the
        game. This builds an outline from the curve instead, so it can be
        filled with the same anti-aliased polygon call everything else uses.
        """
        pts = arm.points()
        left, right = [], []
        for k, p in enumerate(pts):
            t = k / max(1, len(pts) - 1)
            if k == 0:
                nxt = pts[1]
                tangent = nxt - p
            elif k == len(pts) - 1:
                tangent = p - pts[k - 1]
            else:
                tangent = pts[k + 1] - pts[k - 1]
            if tangent.length_squared() < 1e-6:
                tangent = Vector2(1, 0)
            n = Vector2(-tangent.y, tangent.x).normalize()
            # thinnest at the tip, thickest at the root
            # Full width at the root, tapering to a point at the tip.
            w = width * (1.0 - 0.86 * t) * (0.55 + 0.45 * math.sin(min(1.0, t * 2.2) * math.pi * 0.5))
            left.append(p + n * max(0.6, w))
            right.append(p - n * max(0.6, w))
        return left + right[::-1]

    def draw(self, surf: pygame.Surface) -> None:
        """Drawn the way everything else in the game is drawn.

        Every other creature is one flat anti-aliased polygon in a muted
        grey-violet, with white eyes and a mouth line. Nothing in this game has
        a gradient, an outline, or a chevron pattern. The boss had all three
        and read as clip art beside the blots, so this is deliberately plain:
        flat tapered limbs, a flat mantle, and the same face construction the
        other enemies use.
        """
        r = self.effective_radius
        if r < 1:
            return

        # Darken toward ink as the fight is paid for, finishing at C.INK, the
        # same colour every other corpse turns. A boss that died still
        # grey-violet looked like it had not been damaged at all.
        level = self.phase_n / max(1, self.CHECKPOINTS - 1)
        progress = 1.0 - (self.head_hp / max(1e-6, self.head_max))
        # progress alone is not enough: the last eighth is paid off in one hit,
        # so the final frames would jump from 7/8 to full. Take the further of
        # the two so the colour tracks whichever is ahead, and hold ink once
        # the fight is over.
        shade = max(level, progress)
        if self.dead:
            shade = 1.0
        body = lerp_color(self.body, C.INK, min(1.0, 0.10 + 0.90 * shade))
        if self.ink_coat > 0.03:
            body = lerp_color(body, C.INK, min(1.0, self.ink_coat * 0.5))
        if self.hit_flash > 0.02:
            body = lerp_color(body, C.WHITE, self.hit_flash * 0.8)
        if self.open:
            # only the open state changes colour at all, and only slightly
            body = lerp_color(body, C.VERM_PALE, 0.22)

        # --- arms: one flat polygon each, nothing else ---
        for arm in self.arms:
            if not arm.alive:
                continue
            col = lerp_color(body, C.VERM_PALE, 0.35 * arm.hit_flash)
            aa_polygon(surf, self._arm_polygon(arm, 15.0 - 3.0 * level), col)

        # --- mantle: flat blob, same squash and point count as Enemy.draw ---
        sx = 0.94 + 0.10 * math.sin(self.spin * 1.7)
        sy = 1.06 - 0.10 * math.sin(self.spin * 1.7)
        # Fewer lobes and a gentler phase than the small creatures use: at
        # this size the wobble amplitude is large in pixels and cut visible
        # notches where the arms meet the body.
        pts = blob_points(
            self.pos.x, self.pos.y, r, 4, self.spin * 0.55, 2.4, (sx, sy), 24
        )
        aa_polygon(surf, pts, body)

        # --- face: identical construction to the other creatures ---
        self.draw_face(surf, r)

        # --- the one piece of state that must be legible: open or shut ---
        if self.open:
            pygame.draw.circle(
                surf, C.VERM_PALE, (int(self.pos.x), int(self.pos.y)), int(r) + 4, 2
            )

    def draw_face(self, surf: pygame.Surface, r: float) -> None:
        look = self.aim * (r * 0.22)
        eye_r = max(1.6, r * 0.14)
        for side in (-1, 1):
            ex = self.pos.x + look.x + side * r * 0.34
            ey = self.pos.y + look.y - r * 0.1
            pygame.draw.circle(surf, C.WHITE, (int(ex), int(ey)), max(1, int(eye_r + 0.9)))
            pygame.draw.circle(
                surf, C.INK, (int(ex + look.x * 0.3), int(ey + look.y * 0.3)),
                max(1, int(eye_r * 0.55)),
            )
        # mouth: a short line, but wavering once it is damaged
        my = self.pos.y + look.y + r * 0.42
        wob = r * 0.06 * level if (level := self.phase_n / max(1, self.CHECKPOINTS - 1)) else 0.0
        pygame.draw.line(
            surf, C.INK,
            (self.pos.x - r * 0.3, my),
            (self.pos.x + r * 0.3, my + math.sin(self.spin * 3.0) * wob),
            max(1, int(r * 0.09)),
        )
    def die(self, game):
        if self.dead:
            return
        self.dead = True
        game.particles.burst(self.pos, 90, 380, 1.0, 5.4, C.INK, C.VERM_PALE, 1.7)
        game.add_puddle(self.pos, 80, 0.45)
        game.spawn_orbs(self.pos, 0.4, 12)
        game.shake(16.0)
        game.on_kill(self)
