# WallPaper Engine

A Python-based animated wallpaper player with integrated music playback. Features procedural shader-like effects that react to your music in real time, animated GIF support, and a Steam Workshop importer.

## Features

- **5 Procedural Effects** — Aurora Borealis, Ocean Waves, Floating Particles, Gradient Pulse, Digital Rain (Matrix)
- **Audio-Reactive Visuals** — All effects pulse and react to the music being played
- **Music Player** — Built-in playlist with play/pause, skip, and volume control
- **GIF & Image Wallpapers** — Load animated GIFs or static images with parallax breathing
- **HUD Overlay** — Visualizer bars, track info, and controls that auto-fade
- **Steam Workshop Import** — Pull preview assets from your Wallpaper Engine subscriptions
- **Fullscreen & Resizable** — Works windowed or fullscreen at any resolution

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Drop music files into `assets/music/` and wallpapers into `assets/wallpapers/`, then run:

```bash
python main.py --wallpaper assets/wallpapers/scene.gif --music assets/music/
```

## Usage

```
python main.py [options]

Options:
  --wallpaper, -w PATH    Path to wallpaper file (GIF, PNG, JPG)
  --music, -m PATH        Path to music folder (default: assets/music)
  --effect, -e NAME       Procedural effect to use (default: aurora)
  --width INT             Window width (default: 1280)
  --height INT            Window height (default: 720)
  --fps INT               Target FPS (default: 30)
  --fullscreen, -f        Start in fullscreen mode
  --no-hud                Start with the HUD hidden
```

### Examples

```bash
python main.py --effect aurora                          # Aurora borealis
python main.py --effect matrix --fullscreen             # Fullscreen matrix rain
python main.py -w my_wallpaper.gif -m ~/Music -f        # GIF + music, fullscreen
python main.py --width 1920 --height 1080 --fps 60      # Custom resolution
```

## Controls

| Key | Action |
|-----|--------|
| `SPACE` | Play / Pause music |
| `N` | Next track |
| `P` | Previous track |
| `+` / `-` | Volume up / down |
| `E` | Open effects menu |
| `1`–`5` | Quick select effect |
| `F` | Toggle fullscreen |
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
│   ├── renderer.py             # Wallpaper rendering & procedural effects
│   ├── audio.py                # Music player with audio-reactive output
│   ├── ui.py                   # HUD overlay & visualizer bars
│   └── workshop.py             # Steam Workshop content importer
├── assets/
│   ├── wallpapers/             # Place GIF/PNG/JPG wallpapers here
│   ├── music/                  # Place MP3/OGG/WAV files here
│   └── shaders/                # Reserved for custom shaders
├── config/
│   └── default.json            # Default configuration
└── requirements.txt
```

## Requirements

- Python 3.8+
- pygame >= 2.5.0
- Pillow >= 10.0.0

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
