"""Exercise the music system: modes, crossfade, pause, mute, channel budget.

Run with: uv run python tools/music_check.py
"""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from inkfall import config as C  # noqa: E402
from inkfall.game import Game  # noqa: E402


def frame(game: Game, n: int = 1, dt: float = 1 / 60) -> None:
    for _ in range(n):
        game.update(dt)
        game.draw()


def main() -> int:
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    pygame.display.set_mode((C.WIDTH, C.HEIGHT))

    t0 = time.perf_counter()
    game = Game(pygame.display.get_surface())
    boot_ms = (time.perf_counter() - t0) * 1000
    m = game.music
    print(f"audio ok={game.audio.ok} music ok={m.ok}  boot={boot_ms:.0f}ms")
    if not m.ok:
        print("FAIL: music not available")
        return 1
    print(f"loop length = {m.length:.2f}s  mixer={pygame.mixer.get_init()}  "
          f"channels={pygame.mixer.get_num_channels()}")

    from inkfall import music as M
    t1 = time.perf_counter()
    M.render(M._calm(), 44100, wet=0.55)
    M.render(M._combat(), 44100, wet=0.40)
    M.render(M._boss(), 44100, wet=0.30)
    print(f"music synthesis: {(time.perf_counter() - t1) * 1000:.0f}ms for all three loops")

    # ---------------------------------------------------------------- modes
    print("\nmode follows state:")
    for label, setup in (
        ("title", lambda: setattr(game, "state", Game.STATE_TITLE)),
        ("play/empty", lambda: (setattr(game, "state", Game.STATE_PLAY), setattr(game, "boss_active", False), setattr(game, "enemies", []), game.spawn_queue.clear())),
        ("play/busy", lambda: setattr(game, "spawn_queue", [[9.0, "blot"]] * 6)),
        ("boss", lambda: setattr(game, "boss_active", True)),
        ("over", lambda: (setattr(game, "state", Game.STATE_OVER), setattr(game, "boss_active", False))),
    ):
        setup()
        frame(game)
        print(f"  {label:12s} -> {m.mode}")

    # ---------------------------------------------------------------- fade
    # Drive Music.update directly here: running game.update() would advance
    # waves and trigger further mode switches, muddying the measurement.
    print("\ncrossfade (driven directly):")
    game.state = Game.STATE_PLAY
    game.boss_active = False
    game.enemies = []
    game.spawn_queue.clear()
    game._sync_music()
    before = m.mode
    game.boss_active = True
    game._sync_music()
    print(f"  switched {before} -> {m.mode}")
    for i in range(1, 17):
        m.update(0.1)
        a = m._channels[m._live].get_volume()
        b = m._channels[m._prev].get_volume() if m._prev >= 0 else 0.0
        if i % 2 == 0 or m._prev < 0:
            print(f"  t={i * 0.1:4.1f}s  incoming={a:.3f}  outgoing={b:.3f}")
        if m._fade >= 1.0 and m._prev < 0:
            print(f"  fade complete at t={i * 0.1:.1f}s, outgoing channel released")
            break

    # ---------------------------------------------------------------- pause
    # get_busy() stays True for a paused channel, so prove the pause by
    # holding a short sound paused for longer than its own duration.
    print("\npause/resume (short sound held paused past its own length):")
    ch = pygame.mixer.Channel(2)
    snd = game.audio.sounds["ui"]
    length = snd.get_length()
    ch.play(snd)
    ch.pause()
    time.sleep(length + 0.35)
    still_there = ch.get_busy()
    ch.unpause()
    time.sleep(length + 0.25)
    finished = not ch.get_busy()
    print(f"  sound length={length:.2f}s; busy after pause+{length + 0.35:.2f}s={still_there} "
          f"(paused audio held: {still_there}); finished after resume={finished}")

    print("  music follows game pause state:")
    game.state = Game.STATE_PLAY
    frame(game)
    playing = m._channels[m._live].get_busy()
    game.state = Game.STATE_PAUSE
    frame(game, 5)
    game.state = Game.STATE_PLAY
    frame(game, 5)
    after = m._channels[m._live].get_busy()
    print(f"  music channel busy before={playing} and after a pause cycle={after}")

    # ---------------------------------------------------------------- mute
    print("\nmute:")
    game.state = Game.STATE_PLAY
    frame(game, 3)
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m))
    frame(game, 3)
    print(f"  after M: audio.ok={game.audio.ok} music.muted={m.muted} "
          f"channel_volume={m._channels[m._live].get_volume():.3f}")
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m))
    frame(game, 3)
    print(f"  after M again: audio.ok={game.audio.ok} music.muted={m.muted} "
          f"channel_volume={m._channels[m._live].get_volume():.3f}")

    # ---------------------------------------------------------------- budget
    print("\nchannel budget (music must not steal effect channels):")
    total = pygame.mixer.get_num_channels()
    for i in range(8):
        game.audio.play("shoot", 0.5)
    state = [pygame.mixer.Channel(c).get_busy() for c in range(total)]
    print(f"  channels busy after 8 effect plays: {state}")
    effects = sum(1 for c in range(2, total) if pygame.mixer.Channel(c).get_busy())
    print(f"  effect channels used: {effects} of {total - 2}")
    print(f"  music channels still running: {[ch.get_busy() for ch in m._channels]}")

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
