# WallPaper Engine

A Python-based animated **desktop wallpaper** with integrated music playback. Renders behind your desktop icons on Windows — just like Wallpaper Engine — using the Win32 WorkerW API. Features a live clock, dual-layer audio (ambient + music playing simultaneously), procedural shader-like effects that react to your music, animated GIF support, and a Steam Workshop importer.

## Features

- **True Desktop Wallpaper** — Renders behind your icons, not as a foreground window (Windows)
- **Live Clock** — Date and time always visible on the desktop
- **Dual-Layer Audio** — Ambient sounds (ocean waves, rain, etc.) loop underneath your music — both play at the same time
- **5 Procedural Effects** — Aurora Borealis, Ocean Waves, Floating Particles, Gradient Pulse, Digital Rain (Matrix)
- **Audio-Reactive Visuals** — All effects pulse and react to the music being played
- **Music Player** — Built-in playlist with play/pause, skip, and volume control
- **GIF & Image Wallpapers** — Load animated GIFs or static images with parallax breathing
- **HUD Overlay** — Visualizer bars, track info, and controls that auto-fade
- **Steam Workshop Import** — Pull preview assets from your Wallpaper Engine subscriptions
- **Window Mode** — Optional `--window` flag for testing or non-Windows platforms

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

By default on Windows this embeds directly into your desktop — the animation plays behind your icons with a clock in the corner. You can still interact with your desktop normally.

### Dual Audio Setup

Drop your files into the asset folders:
- **Music** (playlist) -> `assets/music/` (MP3, OGG, WAV)
- **Ambient** (loops underneath) -> `assets/ambient/` (ocean waves, rain, etc.)

Both play simultaneously. The ambient track loops forever under your music.

```bash
# Explicit ambient file
python main.py --ambient path/to/ocean_waves.ogg

# Or just drop files in assets/ambient/ and it auto-detects
python main.py
```

To run as a regular window instead (for testing or on non-Windows):

```bash
python main.py --window
```

## Usage

```
python main.py [options]

Options:
  --wallpaper, -w PATH    Path to wallpaper file (GIF, PNG, JPG)
  --music, -m PATH        Path to music folder (default: assets/music)
  --ambient, -a PATH      Path to ambient sound file (loops under music)
  --ambient-dir PATH      Folder to auto-scan for ambient (default: assets/ambient)
  --ambient-volume FLOAT  Ambient volume 0.0-1.0 (default: 0.5)
  --effect, -e NAME       Procedural effect to use (default: aurora)
  --window                Run as a regular window instead of desktop wallpaper
  --width INT             Window width in --window mode (default: 1280)
  --height INT            Window height in --window mode (default: 720)
  --fps INT               Target FPS (default: 30)
  --fullscreen, -f        Fullscreen (only in --window mode)
  --no-hud                Start with the HUD hidden
  --no-clock              Start with the clock hidden
```

### Examples

```bash
python main.py                                        # Desktop wallpaper (default)
python main.py --effect matrix                        # Matrix rain on your desktop
python main.py --ambient ocean.ogg                    # Ambient ocean + music layered
python main.py --ambient rain.ogg --ambient-volume 0.3  # Quiet rain under music
python main.py -w my_wallpaper.gif -m ~/Music         # GIF wallpaper + music
python main.py --window                               # Regular window mode
python main.py --no-clock                             # Hide the clock
```

## How It Works (Windows Desktop Mode)

The app uses the same technique as Wallpaper Engine:

1. Finds the `Progman` shell window
2. Sends the undocumented `0x052C` message to spawn a `WorkerW` layer
3. Locates the `WorkerW` that sits between the desktop and the icon layer
4. Re-parents the pygame window into that `WorkerW`

The result is your animation renders as the actual desktop background, behind all icons and windows.

## Controls

| Key | Action |
|-----|--------|
| `SPACE` | Play / Pause music |
| `N` | Next track |
| `P` | Previous track |
| `+` / `-` | Volume up / down |
| `A` | Toggle ambient sound on/off |
| `C` | Toggle clock display |
| `E` | Open effects menu |
| `1`-`5` | Quick select effect |
| `F` | Toggle fullscreen (window mode only) |
| `H` | Toggle HUD overlay |
| `Q` / `ESC` | Quit |

## Effects

| # | Effect | Description |
|---|--------|-------------|
| 1 | **Wave** | Procedural ocean wave animation |
| 2 | **Aurora** | Northern lights / aurora borealis |
| 3 | **Particles** | Floating particle field |
| 4 | **Gradient Pulse** | Pulsing color gradients |
| 5 | **Matrix** | Digital rain |

All effects respond to the audio level — bass hits make the visuals pulse harder.

## Project Structure

```
WallPaper-Engineering/
├── main.py                     # Entry point & main loop
├── wallpaper_engine/
│   ├── desktop.py              # Win32 desktop wallpaper embedding (WorkerW)
│   ├── renderer.py             # Wallpaper rendering & procedural effects
│   ├── audio.py                # Dual-layer audio (music + ambient)
│   ├── ui.py                   # HUD overlay, clock widget, visualizer bars
│   └── workshop.py             # Steam Workshop content importer
├── assets/
│   ├── wallpapers/             # Place GIF/PNG/JPG wallpapers here
│   ├── music/                  # Place MP3/OGG/WAV music files here
│   ├── ambient/                # Place ambient loops here (ocean, rain, etc.)
│   └── shaders/                # Reserved for custom shaders
├── config/
│   └── default.json            # Default configuration
└── requirements.txt
```

## Requirements

- **Windows 10/11** (for desktop wallpaper mode)
- Python 3.8+
- pygame or pygame-ce >= 2.5.0
- Pillow >= 10.0.0

> **Note:** If `pip install pygame` fails on Python 3.13+, install `pygame-ce` instead:
> ```bash
> pip install pygame-ce Pillow
> ```
> pygame-ce is a community fork that's actively maintained and supports newer Python versions.

## Steam Workshop Import

If you have Wallpaper Engine installed via Steam, you can import workshop items:

```python
from wallpaper_engine.workshop import list_workshop_items, import_workshop_item

items = list_workshop_items()
for item in items:
    print(f"{item['id']}: {item.get('title', 'Unknown')}")

import_workshop_item("3418185490")  # Imports the preview asset
```

The importer auto-detects your Steam workshop folder and extracts usable wallpaper assets (preview GIFs, images) from subscribed items.
