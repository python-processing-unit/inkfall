"""The player: a living blot of ink that spends itself to fight."""

from __future__ import annotations

import math
import random

import pygame
from pygame import Vector2

from . import config as C
from .config import clamp, lerp_color
from .draw import aa_circle, aa_polygon, add_glow, blob_points
from .entities import Drop, norm


class Player:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.vel = Vector2()
        self.mass = C.PLAYER_START_MASS
        self.aim = Vector2(0, -1)
        self.radius = self._radius()
        self.phase = random.uniform(0, 6.28)
        self.shot_cd = 0.0
        self.charge = 0.0
        self.dash_cd = 0.0
        self.dash_time = 0.0
        self.iframes = 0.0
        self.hit_flash = 0.0
        self.absorbing = 0.0
        self.siphoned = 0.0
        self.squash = Vector2(1.0, 1.0)
        self.dead = False
        self.recoil = 0.0
        self.trail = 0.0

    def _radius(self) -> float:
        return 8.0 + 30.0 * self.mass

    @property
    def alive(self) -> bool:
        return self.mass > C.MASS_DEATH

    # ------------------------------------------------------------------
    def input_vector(self) -> Vector2:
        keys = pygame.key.get_pressed()
        move = Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        return move.normalize() if move.length_squared() > 0 else move

    def update(self, dt: float, game) -> None:
        self.phase += dt * (2.0 + self.vel.length() * 0.012)
        self.shot_cd = max(0.0, self.shot_cd - dt)
        self.dash_cd = max(0.0, self.dash_cd - dt)
        self.iframes = max(0.0, self.iframes - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt * 4.0)
        self.charge = max(0.0, self.charge - dt)
        self.absorbing = max(0.0, self.absorbing - dt)
        self.siphoned = max(0.0, self.siphoned - dt * 3.0)
        self.recoil = max(0.0, self.recoil - dt * 4.0)
        self.dash_time = max(0.0, self.dash_time - dt)

        move = self.input_vector()
        heavy = self.mass > 0.62
        accel = 2200.0 if heavy else 2950.0
        max_speed = 335.0 - 95.0 * self.mass
        if self.dash_time > 0:
            accel *= 0.15
        self.vel += move * accel * dt
        self.vel *= math.exp(-(5.2 if move.length_squared() > 0 else 8.4) * dt)
        if self.vel.length() > max_speed and self.dash_time <= 0:
            self.vel.scale_to_length(max_speed)

        self.pos += self.vel * dt
        self.radius = self._radius()
        pad = self.radius
        if self.pos.x < pad:
            self.pos.x = pad
            self.vel.x = abs(self.vel.x) * 0.35
        elif self.pos.x > C.WIDTH - pad:
            self.pos.x = C.WIDTH - pad
            self.vel.x = -abs(self.vel.x) * 0.35
        if self.pos.y < pad:
            self.pos.y = pad
            self.vel.y = abs(self.vel.y) * 0.35
        elif self.pos.y > C.HEIGHT - pad:
            self.pos.y = C.HEIGHT - pad
            self.vel.y = -abs(self.vel.y) * 0.35

        aim = Vector2(pygame.mouse.get_pos()) - self.pos
        if aim.length_squared() > 4:
            self.aim = aim.normalize()

        target = Vector2(1.0, 1.0)
        spd = self.vel.length()
        if spd > 20:
            d = norm(self.vel)
            stretch = 0.16 * min(1.0, spd / 320)
            if abs(d.x) > abs(d.y):
                target = Vector2(1.0 + stretch, 1.0 - 0.75 * stretch)
            else:
                target = Vector2(1.0 - 0.75 * stretch, 1.0 + stretch)
        self.squash += (target - self.squash) * min(1.0, dt * 9)

        self.mass -= dt * 0.006
        self.mass = clamp(self.mass, 0.0, C.MASS_MAX)
        self.absorb(game, dt)
        self.spend_ink(game)

        if self.vel.length() > 170:
            self.trail += dt
            if self.trail > 0.07:
                self.trail = 0.0
                game.particles.add(
                    self.pos - norm(self.vel) * self.radius * 0.8,
                    -self.vel * 0.06,
                    0.28,
                    2.4,
                    C.INK_SOFT,
                    C.INK_PALE,
                    3.0,
                )

        if self.mass <= C.MASS_DEATH and not self.dead:
            self.dead = True
            game.on_player_death()

    # ------------------------------------------------------------------
    def absorb(self, game, dt: float) -> None:
        reach = self.radius + 4
        total = 0.0
        for p in game.puddles:
            if p.dead or p.ink <= 0:
                continue
            if (p.pos - self.pos).length() < reach + p.radius * 0.85:
                got = p.drink(C.ABSORB_RATE * (0.55 + 0.45 * p.wet) * dt)
                if got > 0:
                    total += got
                    self.absorbing = 0.25
                    if random.random() < 0.3:
                        a = random.uniform(0, math.tau)
                        game.particles.add(
                            p.pos + Vector2(math.cos(a), math.sin(a)) * p.radius * 0.6,
                            (self.pos - p.pos) * 1.3,
                            0.28,
                            2.2,
                            C.INK,
                            C.INK_PALE,
                            1.5,
                        )
        if total > 0:
            self.mass = min(C.MASS_MAX, self.mass + total)
            game.ink_drunk += total

    def spend_ink(self, game) -> None:
        mouse = pygame.mouse.get_pressed()
        if mouse[0] and self.shot_cd <= 0 and self.mass > C.SHOT_COST + C.MASS_DEATH + 0.02:
            self.fire(game, heavy=False)
        elif mouse[2] and self.shot_cd <= 0 and self.mass > C.HEAVY_COST + C.MASS_DEATH + 0.02:
            self.fire(game, heavy=True)

    def fire(self, game, heavy: bool) -> None:
        cost = C.HEAVY_COST if heavy else C.SHOT_COST
        self.mass = max(0.0, self.mass - cost)
        self.shot_cd = C.SHOT_COOLDOWN * (2.4 if heavy else 1.0)
        self.recoil = 1.0
        self.charge = C.CHARGE_TIME * (2.0 if heavy else 1.0)
        spread = 0.075 if heavy else 0.05
        angle = math.atan2(self.aim.y, self.aim.x) + random.uniform(-spread, spread)
        direction = Vector2(math.cos(angle), math.sin(angle))
        origin = self.pos + direction * (self.radius * 0.95)
        if heavy:
            self.vel -= direction * 70
            game.add_drop(Drop(origin, direction * 520, 10.0 + self.mass * 2.0, 2.6, True, 1.25, heavy=True))
            game.shake(4.0)
            game.particles.burst(origin, 8, 200, 0.22, 3.0, C.INK, C.INK_SOFT)
            game.audio.play("heavy", 0.55)
        else:
            self.vel -= direction * 24
            game.add_drop(Drop(origin, direction * 780, 5.2, 1.0, True, 1.1))
            game.particles.burst(origin, 3, 90, 0.16, 1.8, C.INK, C.INK_SOFT)
            game.audio.play("shoot", 0.4)

    def dash(self, game) -> None:
        if self.dash_cd > 0 or self.mass < C.DASH_COST + C.MASS_DEATH:
            return
        move = self.input_vector()
        if move.length_squared() < 0.1:
            move = self.aim
        move = norm(move)
        self.mass -= C.DASH_COST
        self.vel += move * C.DASH_IMPULSE
        self.dash_time = 0.16
        self.dash_cd = C.DASH_COOLDOWN
        self.iframes = C.DASH_IFRAMES
        game.particles.burst(
            self.pos, 14, 200, 0.4, 3.4, C.INK, C.INK_PALE, 2.0, spread=1.4, direction=math.atan2(-move.y, -move.x)
        )
        game.ring(self.pos, self.radius * 3.4, C.INK_MID, 0.32, 2)
        game.add_puddle(self.pos - move * self.radius * 0.4, self.radius * 0.65, 0.02)

    def hurt(self, amount: float, game, knockback=None) -> bool:
        if self.iframes > 0 or self.dead:
            return False
        self.mass = max(0.0, self.mass - amount)
        self.iframes = C.HIT_IFRAMES
        self.hit_flash = 1.0
        if knockback is not None:
            self.vel += knockback
        game.shake(9.0)
        game.hitstop = max(game.hitstop, 0.055)
        game.break_combo()
        game.add_puddle(self.pos, self.radius * 0.95, amount * 0.8)
        game.particles.burst(self.pos, 16, 300, 0.5, 3.5, C.INK, C.VERM_PALE, 2.2)
        return True

    # ------------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        r = self.radius
        blink = self.iframes > 0 and int(self.iframes * 24) % 2 == 0
        body = C.INK if self.mass >= 0.3 else lerp_color(C.VERM_DARK, C.INK, self.mass / 0.3)
        if self.hit_flash > 0.01:
            body = lerp_color(body, C.PAPER, self.hit_flash * 0.55)
        col = C.PAPER_WARM if blink else body

        add_glow(surf, self.pos.x, self.pos.y, int(r * 3.0), C.INK_MID, 45)

        sx = self.squash.x - self.recoil * 0.1 + (0.05 if self.absorbing > 0 else 0.0)
        sy = self.squash.y + self.recoil * 0.1 - (0.05 if self.absorbing > 0 else 0.0)
        pts = blob_points(self.pos.x, self.pos.y, r, 5, self.phase * 1.6, 1.7, (sx, sy), 24)
        aa_polygon(surf, pts, col)
        if not blink:
            pygame.draw.lines(surf, C.INK_MID, True, [(int(x), int(y)) for x, y in pts], 1)

        look = self.aim * (r * 0.24)
        eye_r = max(1.8, r * 0.16)
        for side in (-1, 1):
            ex = self.pos.x + look.x + side * r * 0.3
            ey = self.pos.y + look.y - r * 0.08
            if blink:
                pygame.draw.circle(surf, C.INK, (int(ex), int(ey)), max(2, int(eye_r + 1)))
            else:
                aa_circle(surf, ex, ey, eye_r + 1.3, C.WHITE)
                pygame.draw.circle(
                    surf, C.INK, (int(ex + look.x * 0.3), int(ey + look.y * 0.3)), max(1, int(eye_r * 0.72))
                )

        if not blink and r > 8:
            aa_circle(surf, self.pos.x - r * 0.3, self.pos.y - r * 0.38, max(1.5, r * 0.13), C.INK_PALE)
        if self.siphoned > 0.02:
            add_glow(surf, self.pos.x, self.pos.y, int(r * 4), C.VERMILION, int(120 * self.siphoned))

    def draw_charge(self, surf: pygame.Surface) -> None:
        if self.charge <= 0:
            return
        t = clamp(self.charge / C.CHARGE_TIME, 0, 1)
        tip = self.pos + self.aim * (self.radius + 12)
        add_glow(surf, tip.x, tip.y, int(6 + 16 * t), C.VERMILION, int(70 + 90 * t))
        pygame.draw.circle(surf, C.INK, (int(tip.x), int(tip.y)), int(2 + 4 * t))
