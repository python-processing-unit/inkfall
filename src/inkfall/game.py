"""INKFALL: game state, waves, HUD, and screens."""

from __future__ import annotations

import math
import random

import pygame
from pygame import Vector2

from . import config as C
from .audio import Audio
from .music import Music
from .config import clamp, lerp_color
from .draw import aa_circle, aa_polygon, add_glow, blob_points, make_paper
from .entities import Blot, Boss, Drop, FloatText, Orb, Particles, Puddle, Quill, Ring, Skitter, Sponge, Squid, norm
from .player import Player


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    path = pygame.font.match_font("bahnschrift,segoeuisemibold,trebuchetms,dejavusans")
    if path:
        font = pygame.font.Font(path, size)
        font.set_bold(bold)
        return font
    return pygame.font.SysFont("arial", size, bold=bold)


class Game:
    STATE_TITLE = "title"
    STATE_PLAY = "play"
    STATE_PAUSE = "pause"
    STATE_OVER = "over"
    STATE_HELP = "help"

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.paper = make_paper(C.WIDTH, C.HEIGHT)
        self.overlay = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        self.audio = Audio()
        self.music = Music(self.audio)
        self.audio.ducker = self.music
        self.font_small = load_font(15)
        self.font = load_font(19)
        self.font_mid = load_font(30)
        self.font_big = load_font(64)
        self.font_huge = load_font(100)
        self.state = Game.STATE_TITLE
        self.state_time = 0.0
        self.running = True
        self.best = 0
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.player = Player((C.WIDTH / 2, C.HEIGHT / 2))
        self.enemies: list = []
        self.drops: list[Drop] = []
        self.orbs: list[Orb] = []
        self.puddles: list[Puddle] = []
        self.particles = Particles()
        self.rings: list[Ring] = []
        self.texts: list[FloatText] = []
        self.time = 0.0
        self.wave = 0
        self.wave_timer = 1.4
        self.spawn_queue: list[list] = []
        self.score = 0.0
        self.combo = 0
        self.combo_timer = 0.0
        self.best_combo = 0
        self.ink_drunk = 0.0
        self.kills = 0
        self.hitstop = 0.0
        self.shake_amount = 0.0
        self.wave_banner = 0.0
        self.boss_active = False
        self.flash = 0.0
        self.death_time = 0.0
        self.ambient = 0.0

    # ------------------------------------------------------------------
    # world helpers used by entities
    # ------------------------------------------------------------------
    def add_drop(self, drop: Drop) -> None:
        self.drops.append(drop)

    def add_enemy(self, enemy) -> None:
        self.enemies.append(enemy)

    def add_puddle(self, pos, radius: float, ink: float, ink_color=C.INK) -> None:
        radius = clamp(radius, 5.0, 90.0)
        ink = clamp(ink, 0.004, 0.55)
        for p in self.puddles:
            if p.dead or p.ink_color != ink_color:
                continue
            if (p.pos - Vector2(pos)).length() < max(p.radius, radius) * 0.7:
                p.ink = min(0.8, p.ink + ink)
                p.base_ink = max(p.base_ink, p.ink)
                p.base_radius = clamp(max(p.base_radius, radius * 0.9), 5.0, 90.0)
                p.age = min(p.age, 2.0)
                p.spawn = 1.0
                return
        if len(self.puddles) >= C.MAX_PUDDLES:
            self.puddles.pop(0)
        self.puddles.append(Puddle(pos, radius, ink, ink_color))

    def spawn_orbs(self, pos, total: float, count: int) -> None:
        count = max(1, count)
        for _ in range(count):
            self.orbs.append(Orb(pos, total / count))

    def ring(self, pos, radius, color, life=0.35, width=2) -> None:
        self.rings.append(Ring(pos, radius, color, life, width))

    def burst_text(self, pos, text, color=C.INK, size=18) -> None:
        self.texts.append(FloatText(pos, text, color, 0.95, size))

    def shake(self, amount: float) -> None:
        self.shake_amount = min(22.0, self.shake_amount + amount)

    def break_combo(self) -> None:
        self.combo = 0
        self.combo_timer = 0.0

    def on_kill(self, enemy) -> None:
        self.kills += 1
        self.combo += 1
        self.combo_timer = C.COMBO_WINDOW
        self.best_combo = max(self.best_combo, self.combo)
        mult = 1.0 + min(2.0, self.combo * 0.1)
        self.score += enemy.score * mult
        self.audio.play("kill", 0.7)
        if self.combo >= 3:
            self.burst_text(enemy.pos + Vector2(0, -18), f"x{self.combo}", C.VERMILION, 20)
        if self.combo in (5, 10, 20, 35):
            self.audio.play("combo", 0.6)
            self.ring(enemy.pos, 95, C.GOLD, 0.45, 3)

    def on_player_death(self) -> None:
        self.state = Game.STATE_OVER
        self.state_time = 0.0
        self.best = max(self.best, int(self.score))
        self.audio.play("death", 0.9)
        self.shake(18.0)
        self.particles.burst(self.player.pos, 60, 420, 1.2, 4.0, C.INK, C.INK_SOFT, 1.4)
        self.add_puddle(self.player.pos, 70, 0.4)
        self.flash = 1.0

    # ------------------------------------------------------------------
    # waves
    # ------------------------------------------------------------------
    def start_wave(self) -> None:
        self.wave += 1
        self.wave_banner = 2.6
        w = self.wave
        self.spawn_queue.clear()
        self.boss_active = False

        if w % 5 == 0:
            self.boss_active = True
            self.spawn_queue.append([0.7, "boss"])
            self.audio.play("boss", 0.9)
            for i in range(2 + w // 5):
                self.spawn_queue.append([2.6 + i * 0.55, "skitter"])
            return

        self.audio.play("wave", 0.5)
        total = 4 + w * 2
        t = 0.75
        i = 0
        while i < total:
            group = 1 + (1 if random.random() < 0.35 + 0.03 * w else 0) + (1 if random.random() < 0.2 else 0)
            for _ in range(min(group, total - i)):
                roll = random.random()
                if w >= 4 and roll < 0.14 + 0.02 * w:
                    kind = "squid"
                elif w >= 3 and roll < 0.28 + 0.03 * w:
                    kind = "quill"
                elif w >= 2 and roll < 0.42 + 0.03 * w:
                    kind = "sponge"
                elif roll < 0.58:
                    kind = "skitter"
                else:
                    kind = "blot"
                if w == 1:
                    kind = "blot" if i % 3 else "skitter"
                self.spawn_queue.append([t, kind])
                i += 1
            t += max(0.55, 1.55 - w * 0.06)

    def _spawn_point(self) -> Vector2:
        best = None
        for _ in range(20):
            p = Vector2(random.uniform(70, C.WIDTH - 70), random.uniform(90, C.HEIGHT - 70))
            d = (p - self.player.pos).length()
            if d > 190:
                return p
            if best is None or d > (best - self.player.pos).length():
                best = p
        return best or Vector2(C.WIDTH / 2, 100)

    def _make_enemy(self, kind: str):
        pos = self._spawn_point()
        table = {"skitter": Skitter, "sponge": Sponge, "quill": Quill, "squid": Squid, "blot": Blot}
        if kind == "boss":
            return Boss(Vector2(C.WIDTH / 2, 120), self.wave)
        return table.get(kind, Blot)(pos, self.wave)

    def _pool(self) -> None:
        _, kind = self.spawn_queue.pop(0)
        e = self._make_enemy(kind)
        self.enemies.append(e)
        self.particles.burst(e.pos, 16, 200, 0.55, 4.0, C.INK, C.PAPER, 2.0)
        self.ring(e.pos, 60, C.INK_MID, 0.4, 2)

    # ------------------------------------------------------------------
    # main update
    # ------------------------------------------------------------------
    def _sync_music(self) -> None:
        """Pick a loop from the current state, and stop it when frozen."""
        if not self.music.ok:
            return
        if self.state in (Game.STATE_PAUSE, Game.STATE_HELP):
            self.music.pause()
            return
        self.music.resume()
        if self.state == Game.STATE_OVER:
            self.music.set("calm", gain=0.55)
        elif self.boss_active:
            self.music.set("boss", gain=0.9)
        elif self.state == Game.STATE_PLAY:
            busy = len(self.enemies) + len(self.spawn_queue)
            self.music.set("combat" if busy > 3 else "calm", gain=0.75)
        else:
            self.music.set("calm", gain=0.8)

    def update(self, dt: float) -> None:
        self.state_time += dt
        self._sync_music()
        self.music.update(dt)

        if self.state == Game.STATE_TITLE:
            self.ambient += dt
            self.particles.update(dt)
            if random.random() < 0.4:
                self.particles.add(
                    (random.uniform(0, C.WIDTH), -10),
                    (0, random.uniform(40, 90)),
                    3.0,
                    random.uniform(1.0, 3.0),
                    C.INK_SOFT,
                    C.PAPER,
                    0.2,
                )
            return

        if self.state in (Game.STATE_PAUSE, Game.STATE_HELP):
            self.ambient += dt * 0.4
            return

        if self.state == Game.STATE_OVER:
            self.death_time += dt
            self.ambient += dt
            self.particles.update(dt * 0.5)
            for p in self.puddles:
                p.update(dt * 0.4)
            self.rings = [r for r in self.rings if r.update(dt)]
            self.texts = [t for t in self.texts if t.update(dt)]
            self.shake_amount *= math.exp(-6 * dt)
            self.flash = max(0.0, self.flash - dt * 1.6)
            return

        if self.hitstop > 0:
            self.hitstop -= dt
            dt *= 0.12

        self.time += dt
        self.ambient += dt
        self.wave_banner = max(0.0, self.wave_banner - dt)
        self.flash = max(0.0, self.flash - dt * 2.0)
        self.shake_amount *= math.exp(-8 * dt)

        self.player.update(dt, self)

        # wave flow
        if not self.spawn_queue:
            if not any(not e.dead for e in self.enemies):
                self.wave_timer -= dt
                if self.wave_timer <= 0:
                    self.wave_timer = 2.2
                    self.start_wave()
            else:
                self.wave_timer = 1.2
        else:
            self.spawn_queue[0][0] -= dt
            if self.spawn_queue[0][0] <= 0:
                self._pool()

        for e in self.enemies:
            e.update(dt, self)
        self._collide_enemies()

        for d in self.drops:
            d.update(dt, self)
        self._collide_drops()

        for o in self.orbs:
            o.update(dt, self.player)
            if o.collected:
                self.player.mass = min(C.MASS_MAX, self.player.mass + o.value)
                self.ink_drunk += o.value
                self.score += 6
                self.audio.play("orb", 0.3)
                self.particles.burst(o.pos, 3, 70, 0.2, 1.8, C.INK_SOFT, C.PAPER)
        self.orbs = [o for o in self.orbs if not o.dead]

        for p in self.puddles:
            p.update(dt)
        self.puddles = [p for p in self.puddles if not p.dead]
        self.enemies = [e for e in self.enemies if not e.dead]
        self.drops = [d for d in self.drops if not d.dead]

        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0

        self.particles.update(dt)
        self.rings = [r for r in self.rings if r.update(dt)]
        self.texts = [t for t in self.texts if t.update(dt)]

        if random.random() < 0.05:
            self.audio.play("absorb", 0.1)

    def _collide_enemies(self) -> None:
        pl = self.player
        for e in self.enemies:
            if e.dead:
                continue
            d = pl.pos - e.pos
            dist = d.length()
            if dist < e.effective_radius + pl.radius * 0.85:
                push = d / dist if dist > 0.5 else Vector2(1, 0)
                if pl.hurt(e.damage, self, push * 340):
                    e.vel -= push * 170
                    self.audio.play("hurt", 0.65)
                overlap = e.effective_radius + pl.radius * 0.85 - dist
                pl.pos += push * overlap * 0.7
                e.pos -= push * overlap * 0.3

    def _collide_drops(self) -> None:
        pl = self.player
        for d in self.drops:
            if d.dead or not d.friendly:
                continue
            for e in self.enemies:
                if e.dead:
                    continue
                if (e.pos - d.pos).length_squared() < (e.effective_radius + d.radius) ** 2:
                    e.take_damage(
                        d.damage,
                        self,
                        (norm(d.vel) if d.vel.length_squared() > 1 else Vector2(0, -1)) * (260 if d.heavy else 110),
                        0.6 if d.heavy else 0.3,
                    )
                    d.dead = True
                    d.splat(self)
                    break

        for d in self.drops:
            if d.dead or d.friendly:
                continue
            if (pl.pos - d.pos).length_squared() < (pl.radius + d.radius) ** 2:
                knock = norm(d.vel) * 180 if d.vel.length_squared() > 1 else Vector2()
                if pl.hurt(d.damage, self, knock):
                    self.audio.play("hurt", 0.55)
                d.dead = True
                self.particles.burst(d.pos, 6, 150, 0.3, 2.4, C.VERM_DARK, C.VERM_PALE)

    # ------------------------------------------------------------------
    # events
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state == Game.STATE_PLAY:
                    self.state = Game.STATE_PAUSE
                    self.state_time = 0.0
                    self.audio.play("ui", 0.4)
                elif self.state in (Game.STATE_PAUSE, Game.STATE_HELP):
                    self.state = Game.STATE_PLAY if self.state == Game.STATE_PAUSE else Game.STATE_TITLE
                    self.state_time = 0.0
                else:
                    self.running = False
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                if self.state == Game.STATE_TITLE:
                    self.reset()
                    self.state = Game.STATE_PLAY
                    self.start_wave()
                elif self.state == Game.STATE_OVER and self.state_time > 0.7:
                    self.reset()
                    self.state = Game.STATE_PLAY
                    self.start_wave()
            elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT) and self.state == Game.STATE_PLAY:
                self.player.dash(self)
                self.audio.play("dash", 0.45)
            elif event.key == pygame.K_h:
                if self.state == Game.STATE_HELP:
                    self.state = Game.STATE_TITLE
                    self.state_time = 0.0
                elif self.state in (Game.STATE_TITLE, Game.STATE_PAUSE):
                    self.state = Game.STATE_HELP
                    self.state_time = 0.0
                self.audio.play("ui", 0.4)
            elif event.key == pygame.K_m:
                self.audio.ok = not self.audio.ok
                self.music.muted = not self.audio.ok

        if event.type == pygame.MOUSEBUTTONDOWN and self.state == Game.STATE_PLAY:
            if event.button == 3:
                self.player.fire(self, heavy=True)
        if event.type == pygame.MOUSEBUTTONDOWN and self.state == Game.STATE_TITLE:
            self.reset()
            self.state = Game.STATE_PLAY
            self.start_wave()

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def draw(self) -> None:
        surf = self.screen
        surf.blit(self.paper, (0, 0))

        cam = Vector2()
        if self.shake_amount > 0.2:
            cam = Vector2(random.uniform(-1, 1), random.uniform(-1, 1)) * self.shake_amount

        world = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        self._draw_stains(world)
        for p in self.puddles:
            p.draw(world)
        for r in self.rings:
            r.draw(world)
        self.particles.draw(world)
        for o in self.orbs:
            o.draw(world)
        for e in self.enemies:
            e.draw(world)
        for d in self.drops:
            d.draw(world)

        if self.state == Game.STATE_OVER:
            self._draw_ghost(world)
        elif self.state != Game.STATE_TITLE:
            self.player.draw_charge(world)
            self.player.draw(world)

        for t in self.texts:
            self._draw_float_text(world, t)

        surf.blit(world, cam)

        if self.state == Game.STATE_TITLE:
            self._draw_title(surf)
        elif self.state == Game.STATE_HELP:
            self._draw_help(surf)
        else:
            self._draw_hud(surf)
            if self.state == Game.STATE_PAUSE:
                self._draw_pause(surf)
            elif self.state == Game.STATE_OVER:
                self._draw_over(surf)

        self._draw_cursor(surf)

        if self.flash > 0:
            self.overlay.fill((250, 246, 236, int(120 * self.flash)))
            surf.blit(self.overlay, (0, 0))

        pygame.draw.rect(surf, (34, 27, 40), surf.get_rect(), 2)

    def _draw_stains(self, surf) -> None:
        for i in range(9):
            x = C.WIDTH * (0.1 + 0.8 * ((i * 0.37) % 1.0)) + math.sin(self.ambient * 0.08 + i) * 12
            y = C.HEIGHT * (0.12 + 0.76 * ((i * 0.61) % 1.0)) + math.cos(self.ambient * 0.07 + i * 1.3) * 10
            r = 26 + (i * 13) % 46
            pts = blob_points(x, y, r, 7, self.ambient * 0.05 + i, i * 3.1, (1.0, 0.8), 18)
            aa_polygon(surf, pts, (223, 215, 197) if i % 3 else (228, 218, 200))
            if i % 4 == 0:
                pygame.draw.lines(surf, (206, 196, 178), True, [(int(px), int(py)) for px, py in pts], 1)

    def _draw_ghost(self, surf) -> None:
        t = clamp(self.death_time / 1.4, 0, 1)
        pos = self.player.pos
        vel = self.player.vel
        for i in range(8):
            f = 1.0 - i / 8
            x = pos.x + vel.x * i * 0.018
            y = pos.y + vel.y * i * 0.018
            pts = blob_points(x, y, self.player.radius * f * (1.0 - t * 0.55), 5, self.ambient * 2, 1.7, (1, 1), 16)
            aa_polygon(surf, pts, lerp_color(C.INK_SOFT, C.PAPER, i / 8 + t * 0.4))

    def _draw_float_text(self, surf, t: FloatText) -> None:
        a = clamp(t.life / t.max_life, 0, 1)
        font = self.font_small if t.size < 18 else self.font
        img = font.render(t.text, True, t.color)
        img.set_alpha(int(255 * a))
        surf.blit(img, (t.pos.x - img.get_width() / 2, t.pos.y - img.get_height() / 2))

    # ------------------------------------------------------------------ HUD
    def _draw_hud(self, surf) -> None:
        mx, my, mw, mh = 34, C.HEIGHT - 54, 250, 26
        pygame.draw.rect(surf, (40, 33, 56), (mx - 3, my - 3, mw + 6, mh + 6), border_radius=14)
        pygame.draw.rect(surf, C.PAPER_WARM, (mx, my, mw, mh), border_radius=12)
        frac = clamp(self.player.mass / C.MASS_MAX, 0, 1)
        fill_w = int(mw * frac)
        if fill_w > 4:
            col = lerp_color(C.VERM_DARK, C.INK, clamp((frac - 0.12) / 0.35, 0, 1))
            pygame.draw.rect(surf, col, (mx, my, fill_w, mh), border_radius=12)
            pygame.draw.rect(
                surf,
                lerp_color(col, C.WHITE, 0.35),
                (mx + 2, my + 3, max(1, fill_w - 6), 5),
                border_radius=4,
            )
        dx = int(mx + mw * (C.MASS_DEATH / C.MASS_MAX))
        pygame.draw.line(surf, C.VERMILION, (dx, my - 6), (dx, my + mh + 6), 2)
        surf.blit(self.font_small.render("INK", True, C.INK), (mx, my - 24))
        surf.blit(self.font_small.render(f"{int(frac * 100):3d}%", True, C.INK), (mx + mw + 14, my + 4))

        for i in range(3):
            ready = self.player.dash_cd <= i * C.DASH_COOLDOWN / 3
            cx = mx + 8 + i * 16
            cy = my + mh + 16
            pygame.draw.circle(surf, C.INK if ready else C.PAPER_SHADE, (cx, cy), 5)
            pygame.draw.circle(surf, C.INK_MID, (cx, cy), 5, 1)

        sc = self.font_mid.render(f"{int(self.score):,}", True, C.INK)
        surf.blit(sc, (C.WIDTH - 34 - sc.get_width(), 24))
        lbl = self.font_small.render("STAINED", True, C.INK_SOFT)
        surf.blit(lbl, (C.WIDTH - 34 - lbl.get_width(), 10))

        wv = self.font.render(f"WAVE {self.wave}", True, C.INK)
        surf.blit(wv, (C.WIDTH / 2 - wv.get_width() / 2, 18))
        rem = sum(1 for e in self.enemies if not e.dead) + len(self.spawn_queue)
        sub = self.font_small.render(f"{rem} blot{'s' if rem != 1 else ''} left", True, C.INK_SOFT)
        surf.blit(sub, (C.WIDTH / 2 - sub.get_width() / 2, 42))

        if self.combo >= 2:
            t = clamp(self.combo_timer / C.COMBO_WINDOW, 0, 1)
            col = lerp_color(C.VERMILION, C.GOLD, 1 - t)
            surf.blit(self.font_mid.render(f"x{self.combo}", True, col), (32, 22))
            pygame.draw.rect(surf, col, (32, 58, int(90 * t), 4), border_radius=2)

        boss = next((e for e in self.enemies if e.kind == "boss"), None)
        if boss is not None:
            bw = 420
            bx = C.WIDTH / 2 - bw / 2
            by = C.HEIGHT - 92
            pygame.draw.rect(surf, (40, 33, 56), (bx - 3, by - 3, bw + 6, 18), border_radius=8)
            pygame.draw.rect(surf, C.PAPER_SHADE, (bx, by, bw, 12), border_radius=6)
            f = clamp(boss.hp / boss.max_hp, 0, 1)
            if f > 0:
                pygame.draw.rect(surf, C.VERM_DARK, (bx, by, int(bw * f), 12), border_radius=6)
            nm = self.font_small.render("THE BLOT", True, C.INK)
            surf.blit(nm, (C.WIDTH / 2 - nm.get_width() / 2, by - 20))

        if self.wave_banner > 0:
            fade = clamp(self.wave_banner / 0.55, 0, 1)
            txt = "THE BLOT SURFACES" if self.boss_active else f"WAVE {self.wave}"
            img = self.font_big.render(txt, True, C.INK)
            img.set_alpha(int(215 * fade))
            surf.blit(img, (C.WIDTH / 2 - img.get_width() / 2, 150))

    def _draw_cursor(self, surf) -> None:
        mx, my = pygame.mouse.get_pos()
        if self.state == Game.STATE_PLAY:
            col = C.VERMILION
            pygame.draw.circle(surf, col, (mx, my), 9, 1)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                pygame.draw.line(surf, col, (mx + dx * 13, my + dy * 13), (mx + dx * 5, my + dy * 5), 1)
            pygame.draw.circle(surf, col, (mx, my), 2)
        else:
            pygame.draw.circle(surf, C.INK_MID, (mx, my), 4, 1)

    # ------------------------------------------------------------------ screens
    def _draw_title(self, surf) -> None:
        cx, cy = C.WIDTH / 2, 172
        bob = math.sin(self.ambient * 1.4) * 6
        add_glow(surf, cx, cy + bob, 140, C.INK_MID, 40)
        pts = blob_points(cx, cy + bob, 56, 5, self.ambient * 1.2, 2.2, (1.0, 1.05), 30)
        aa_polygon(surf, pts, C.INK)
        for side in (-1, 1):
            aa_circle(surf, cx + side * 17, cy + bob - 8, 9, C.WHITE)
            pygame.draw.circle(surf, C.INK, (int(cx + side * 17), int(cy + bob - 10)), 4)
        drop_t = (self.ambient * 0.55) % 1.0
        pygame.draw.circle(surf, C.INK, (int(cx + 26), int(cy + 46 + drop_t * 62)), max(1, int(5 * (1 - drop_t))))

        title = self.font_huge.render("INKFALL", True, C.INK)
        surf.blit(title, (C.WIDTH / 2 - title.get_width() / 2, 248))
        sub = self.font.render("you are the last wet blot on the page", True, C.INK_MID)
        surf.blit(sub, (C.WIDTH / 2 - sub.get_width() / 2, 348))

        pulse = 0.5 + 0.5 * math.sin(self.ambient * 3.2)
        prompt = self.font.render("press  SPACE  to drip in", True, lerp_color(C.INK_MID, C.VERMILION, pulse))
        surf.blit(prompt, (C.WIDTH / 2 - prompt.get_width() / 2, 422))

        for i, line in enumerate(
            [
                "WASD move    MOUSE aim    LEFT throw ink    RIGHT heavy dollop",
                "SHIFT dash (costs ink)    walk over your puddles to drink them back",
                "H how to play    ESC pause / quit    M mute everything",
            ]
        ):
            img = self.font_small.render(line, True, C.INK_SOFT)
            surf.blit(img, (C.WIDTH / 2 - img.get_width() / 2, 482 + i * 22))

        if self.best:
            b = self.font_small.render(f"best stain: {self.best:,}", True, C.GOLD)
            surf.blit(b, (C.WIDTH / 2 - b.get_width() / 2, 556))

    def _draw_help(self, surf) -> None:
        panel_w, panel_h = 760, 436
        left = C.WIDTH / 2 - panel_w / 2
        top = 82
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((250, 246, 232, 238))
        pygame.draw.rect(panel, C.INK_MID, panel.get_rect(), 2, border_radius=6)
        surf.blit(panel, (left, top))

        h = self.font_big.render("how to stay wet", True, C.INK)
        surf.blit(h, (C.WIDTH / 2 - h.get_width() / 2, 96))

        rows = [
            ("you are ink", "Your body is your ammo and health. Every shot shrinks you."),
            ("throw, then drink", "Droplets stain the page. Walk over puddles to reabsorb."),
            ("but so do they", "Blots touching your puddles swell up and hit harder."),
            ("keep moving", "Shift dashes with brief invulnerability. It costs ink."),
            ("combo", "Chain kills within a couple of seconds for a multiplier."),
            ("waves", "Clear every blot. Every fifth wave, THE BLOT surfaces."),
            ("know them", "Skitter: fast pack. Sponge: drinks. Quill: snipes."),
        ]
        head_x = left + 26
        body_x = left + 236
        y = 172
        for head, body in rows:
            surf.blit(self.font.render(head, True, C.VERM_DARK), (head_x, y))
            surf.blit(self.font_small.render(body, True, C.INK), (body_x, y + 5))
            y += 38

        foot = self.font_small.render("H or ESC to go back", True, C.INK_SOFT)
        surf.blit(foot, (C.WIDTH / 2 - foot.get_width() / 2, y + 12))

    def _draw_pause(self, surf) -> None:
        veil = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        veil.fill((244, 239, 226, 200))
        surf.blit(veil, (0, 0))
        t = self.font_big.render("paused", True, C.INK)
        surf.blit(t, (C.WIDTH / 2 - t.get_width() / 2, 220))
        line = self.font.render("ESC resume    H help    M mute", True, C.INK_MID)
        surf.blit(line, (C.WIDTH / 2 - line.get_width() / 2, 312))

    def _draw_over(self, surf) -> None:
        veil = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        veil.fill((244, 239, 226, 196))
        surf.blit(veil, (0, 0))
        t = self.font_big.render("the page dries", True, C.INK)
        surf.blit(t, (C.WIDTH / 2 - t.get_width() / 2, 140))
        sub = self.font.render(f"you survived {self.wave} wave{'s' if self.wave != 1 else ''}", True, C.INK_MID)
        surf.blit(sub, (C.WIDTH / 2 - sub.get_width() / 2, 224))

        stats = [
            ("ink stained", f"{int(self.score):,}"),
            ("blots undone", str(self.kills)),
            ("best chain", f"x{self.best_combo}"),
            ("ink reclaimed", f"{self.ink_drunk:.1f}"),
        ]
        y = 288
        for label, value in stats:
            surf.blit(self.font_small.render(label, True, C.INK_SOFT), (C.WIDTH / 2 - 170, y + 3))
            surf.blit(self.font.render(value, True, C.INK), (C.WIDTH / 2 + 60, y))
            y += 34

        if self.best and int(self.score) >= self.best:
            b = self.font.render("a personal best", True, C.GOLD)
            surf.blit(b, (C.WIDTH / 2 - b.get_width() / 2, y + 4))

        if self.state_time > 0.7:
            alpha = 0.5 + 0.5 * math.sin(self.state_time * 4)
            p = self.font.render("SPACE to stain again", True, lerp_color(C.INK_MID, C.VERMILION, alpha))
            surf.blit(p, (C.WIDTH / 2 - p.get_width() / 2, 508))

    # ------------------------------------------------------------------
    def run(self) -> None:
        while self.running:
            dt = min(0.05, self.clock.tick(C.FPS) / 1000.0)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
