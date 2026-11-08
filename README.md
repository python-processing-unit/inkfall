# INKFALL

A small, strange arcade game.

You are the last wet blot on a sheet of paper. Your body is both your health and
your ammunition: every droplet you throw tears a piece off you. The droplets
stain the page, and anything that walks through a stain gets stronger. So you
throw, you run, and you drink your own spill back before it dries or before
something else drinks it first.

Built with Python 3.15.2, [uv](https://docs.astral.sh/uv/), and pygame-ce. No
image, sound, or music files: every shape is drawn procedurally, every sound is
synthesised at boot, and the music is composed in code as well.

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
| `M` | Mute or unmute (effects and music) |
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

## Music

The soundtrack is an original composition, written and synthesised by
`src/inkfall/music.py`. Nothing is sampled, transcribed, or derived from any
existing piece of music, and no audio file is shipped. It is generated from
arrays of note numbers when the game starts, in about four tenths of a second.

The tempo is not a style choice, it is read from the game: 142.86 BPM, where one
beat equals `DASH_COOLDOWN` and one sixteenth equals `SHOT_COOLDOWN`. A dash
lands exactly on the beat and a shot at full fire rate lands exactly on the
grid, because those two numbers are already in a 4:1 ratio.

Three loops share one sixteen-bar form in A minor, so they cross-fade without
clashing. Sixteen bars is 27 seconds; at eight it repeated every 13 seconds,
which the ear memorises in a couple of passes and then finds tiring. The form
is an eight-bar statement followed by a variation that leans toward C major
before resolving home, and the percussion drops out for bars 5, 6, 13, and 14
so the return has somewhere to land. The pad swells and recedes across the
form rather than sitting at one level. Calm plays a single low thud per bar
under a sparse mallet line. Combat adds a backbeat and pushes the bass.

The boss is the main theme itself rather than separate material: the same
melody doubled an octave down and an octave up, over a heavier pattern that
never drops out. By the time the boss appears the player has heard that tune
for four waves, so hearing it turn sour reads as the same world going wrong
instead of as a different piece of music starting.

Separating the music from the effects took measurement rather than taste. The
effects span the whole spectrum, so no register is free: `heavy` is 85% in
120-250 Hz, `absorb` is 77% in 250-500 Hz, `wave` splits across both, and
`shoot` and `orb` peak near 1 kHz. Three things keep the effects legible.
The volume is low to begin with. The shared band is shelved down about 3 dB.
And loud effects duck the music, recovering over 0.16 seconds; quiet ones at
the shot cadence do not duck at all, because ducking ten times a second would
be a flutter-rate tremolo and more tiring than the masking it fixes.

Notes ringing past the final step are wrapped to the start of the buffer, so
the loop seam is a continuation rather than a click. `tools/music_audit.py`
checks that every event sits on the grid, that no two overlapping notes form a
semitone clash, that the parts stay in separate octaves, and how much of the
music competes with each effect.

Mode changes are driven by game state: calm on the title and the quiet moments,
combat once more than a few enemies are alive, boss while THE BLOT is up, and
calm again on the results screen. Switching cross-fades over 1.4 seconds on two
mixer channels reserved ahead of the effect voices. `M` mutes the music along
with the effects, and pausing the game pauses the loop in place.

## Architecture

| File | Responsibility |
| --- | --- |
| `src/inkfall/config.py` | Dimensions, palette, tuning constants, math helpers |
| `src/inkfall/draw.py` | Anti-aliased blobs, cached soft glows, the paper background |
| `src/inkfall/entities.py` | Particles, droplets, puddles, orbs, enemies, the boss |
| `src/inkfall/player.py` | The player blot: movement, firing, dashing, absorption |
| `src/inkfall/audio.py` | Procedural sound synthesis and playback |
| `src/inkfall/music.py` | Original background music: composition, synthesis, cross-fade |
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
uv run python tools/music_check.py     # music modes, crossfade, pause, mute, channels
uv run python tools/music_audit.py     # grid alignment, harmony, and mix levels
uv run python tools/profile_frame.py  # cProfile the crowded-board frame
uv run python tools/startup.py        # real window and audio startup check
uv run python tools/entry.py          # exercise the console entry point
```

Screenshots land in `tools/_shot_*.png`. `tools/_sandbox_libs` holds a staged
copy of the wheels used for headless testing in a sandbox without `uv`; it is
not needed to play the game.


## Note

This game was generated autonomously by an agent with little human interaction.
