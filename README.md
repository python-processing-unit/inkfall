# INKFALL

A small, strange arcade game about being wet in a dry world.

You are the last wet blot on a sheet of paper. Your body is both your health and
your ammunition: every droplet you throw tears a piece off you. The droplets
stain the page, and anything that walks through a stain gets stronger. So you
throw, you run, and you drink your own spill back before it dries or before
something else drinks it first.

Built with Python 3.15.2, [uv](https://docs.astral.sh/uv/), and pygame-ce. No
image or sound files: every shape is drawn procedurally and every sound is
synthesised at boot.

## Run it

```bash
uv run inkfall
```

Or, equivalently:

```bash
uv run python -m inkfall
```

`uv` will create the virtual environment and install pygame-ce and numpy on the
first run. The window is 960x600.

## Controls

| Input | Action |
| --- | --- |
| `W` `A` `S` `D` | Move |
| Mouse | Aim |
| Left mouse | Throw a droplet (costs ink, fires on a short cooldown) |
| Right mouse | Heavy dollop (costs more ink, hits harder and splashes wider) |
| `Shift` | Dash with brief invulnerability (costs ink) |
| `H` | How to play |
| `Esc` | Pause during play; quit from the title or pause screen |
| `M` | Mute or unmute |
| `Space` / `Enter` | Start, or restart after death |

## How it plays

Your mass is your life bar. It starts at 0.70 and you die at 0.12. Firing drains
it, dashing drains it, and being hit drains it hard. You refill by walking over
puddles of your own ink. Fresh puddles refill you fastest, at up to 1.25 mass per
second; older, drier puddles give less. Mass caps at 1.0.

The twist is that puddles are not neutral ground. Blots that touch your spill
swell up: they grow larger and, once fat enough, regenerate health. A grown blot
is a bigger target but also a bigger threat, because its contact damage reaches
further. Your ammunition feeds the enemy. The practical loop is to shoot only
what you must, then immediately walk through the mess you made to reclaim it,
and never leave a large puddle sitting near a wave spawn.

Kills chained within 2.4 seconds build a combo multiplier, up to x3. Every fifth
wave the boss, THE BLOT, surfaces.

### The creatures

- **Skitter** moves in fast, twitchy packs and is the basic pressure unit.
- **Blot** is the common blob; it grows when it feeds on your puddles.
- **Sponge** is slow and very thirsty. It drinks your ink faster than you can,
  and splits into Skitters when it dies fat.
- **Quill** snipes from a distance and punishes standing still.
- **Squid** holds just outside its own reach, then commits to a lash. The lash
  has a visible windup and cannot grab beyond the length of its drawn tendril,
  so stepping or dashing back during the tell escapes it. While latched it
  drains your mass.
- **THE BLOT** is the boss on every fifth wave. It slams, bursts, and spawns
  Skitters.

## Architecture

| File | Responsibility |
| --- | --- |
| `src/inkfall/config.py` | Dimensions, palette, tuning constants, math helpers |
| `src/inkfall/draw.py` | Anti-aliased blobs, cached soft glows, the paper background |
| `src/inkfall/entities.py` | Particles, droplets, puddles, orbs, enemies, the boss |
| `src/inkfall/player.py` | The player blot: movement, firing, dashing, absorption |
| `src/inkfall/audio.py` | Procedural sound synthesis and playback |
| `src/inkfall/game.py` | Game state, waves, HUD, and all screens |
| `src/inkfall/__init__.py` | `main()` entry point |

The game runs at a fixed 60 FPS target. Rendering is hand-tuned: small shapes
drop polygon point counts and outlines are cached, which keeps a crowded board
(25 enemies and 600 particles) at roughly 9 to 13 ms per frame, inside the
16.6 ms budget.

## Development tools

These are not part of the shipped game. They drive the real game loop headless
with a scripted player and fake input.

```bash
uv run python tools/smoke.py          # 240s soak test across all screens
uv run python tools/check.py          # balance run, frame timing, screen shots
uv run python tools/sweep.py          # seeded balance sweep over many runs
uv run python tools/squid_check.py    # squid grab range vs drawn tendril
uv run python tools/squid_impact.py   # isolate squid contribution to difficulty
uv run python tools/profile_frame.py  # cProfile the crowded-board frame
uv run python tools/startup.py        # real window and audio startup check
uv run python tools/entry.py          # exercise the console entry point
```

Screenshots land in `tools/_shot_*.png`. `tools/_sandbox_libs` holds a staged
copy of the wheels used for headless testing in a sandbox without `uv`; it is
not needed to play the game.
