#!/usr/bin/env python3
"""
WallPaper Engine - Animated Wallpapers with Music

A Python-based animated wallpaper player with integrated music playback.
Supports animated GIFs, static images with parallax, and procedural
shader-like effects that react to music.

Controls:
    SPACE       - Play / Pause music
    N           - Next track
    P           - Previous track
    + / =       - Volume up
    - / _       - Volume down
    E           - Open effects menu
    1-5         - Quick select effect
    F           - Toggle fullscreen
    H           - Toggle HUD overlay
    L           - Load wallpaper file
    Q / ESC     - Quit

Usage:
    python main.py                          # Start with default procedural effect
    python main.py --wallpaper path.gif     # Start with a specific wallpaper
    python main.py --music ~/Music          # Specify music folder
    python main.py --effect aurora          # Start with specific effect
    python main.py --width 1920 --height 1080  # Custom resolution
"""

import os
import sys
import argparse
import pygame

from wallpaper_engine.renderer import WallpaperRenderer
from wallpaper_engine.audio import MusicPlayer
from wallpaper_engine.ui import HUD


def parse_args():
    parser = argparse.ArgumentParser(
        description="WallPaper Engine - Animated wallpapers with music",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Effects:
  wave            Ocean wave animation
  aurora          Northern lights / aurora borealis
  particles       Floating particle field
  gradient_pulse  Pulsing color gradients
  matrix          Digital rain (Matrix style)

Examples:
  python main.py --effect aurora
  python main.py --wallpaper assets/wallpapers/scene.gif --music assets/music/
  python main.py --width 1920 --height 1080 --fullscreen
        """
    )
    parser.add_argument("--wallpaper", "-w", type=str, default=None,
                        help="Path to wallpaper file (GIF, PNG, JPG)")
    parser.add_argument("--music", "-m", type=str, default="assets/music",
                        help="Path to music folder (default: assets/music)")
    parser.add_argument("--effect", "-e", type=str, default="aurora",
                        choices=["wave", "aurora", "particles", "gradient_pulse", "matrix"],
                        help="Procedural effect to use (default: aurora)")
    parser.add_argument("--width", type=int, default=1280,
                        help="Window width (default: 1280)")
    parser.add_argument("--height", type=int, default=720,
                        help="Window height (default: 720)")
    parser.add_argument("--fps", type=int, default=30,
                        help="Target FPS (default: 30)")
    parser.add_argument("--fullscreen", "-f", action="store_true",
                        help="Start in fullscreen mode")
    parser.add_argument("--no-hud", action="store_true",
                        help="Start with HUD hidden")
    return parser.parse_args()


class WallpaperEngine:
    """Main application class that orchestrates rendering and audio."""

    def __init__(self, args):
        pygame.init()
        pygame.display.set_caption("WallPaper Engine")

        self.target_fps = args.fps
        self.fullscreen = args.fullscreen

        # Set up display
        flags = pygame.DOUBLEBUF | pygame.HWSURFACE
        if self.fullscreen:
            info = pygame.display.Info()
            self.width, self.height = info.current_w, info.current_h
            flags |= pygame.FULLSCREEN
        else:
            self.width = args.width
            self.height = args.height
            flags |= pygame.RESIZABLE

        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        self.clock = pygame.time.Clock()

        # Initialize subsystems
        self.renderer = WallpaperRenderer(self.screen)
        self.music = MusicPlayer()
        self.hud = HUD(self.width, self.height)

        # Load wallpaper if specified
        if args.wallpaper:
            self.renderer.load_wallpaper(args.wallpaper)
        else:
            self.renderer.set_effect(args.effect)

        # Scan for music
        music_dir = os.path.abspath(args.music)
        self.music.scan_music_folder(music_dir)

        # HUD visibility
        if args.no_hud:
            self.hud.visible = False

        self.running = True

    def run(self):
        """Main application loop."""
        print("\n" + "=" * 50)
        print("  WallPaper Engine v1.0")
        print("  Animated Wallpapers with Music")
        print("=" * 50)
        print("\nControls:")
        print("  SPACE  - Play/Pause    N/P - Next/Prev track")
        print("  +/-    - Volume        E   - Effects menu")
        print("  F      - Fullscreen    H   - Toggle HUD")
        print("  1-5    - Quick effect   Q  - Quit")
        print("=" * 50 + "\n")

        # Auto-play music if available
        if self.music.playlist:
            self.music.play()

        while self.running:
            self._handle_events()
            self._update()
            self._render()
            self.clock.tick(self.target_fps)

        self._cleanup()

    def _handle_events(self):
        """Process all pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            # Forward music events
            self.music.handle_event(event)

            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

            if event.type == pygame.VIDEORESIZE:
                self._handle_resize(event.w, event.h)

            # Any mouse or key activity shows HUD
            if event.type in (pygame.MOUSEMOTION, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.hud.activity()

    def _handle_keydown(self, key):
        """Handle keyboard input."""
        # If effects menu is open, route input there first
        if self.hud.show_effects_menu:
            effect = self.hud.handle_effects_input(key)
            if effect:
                self.renderer.set_effect(effect)
            return

        if key == pygame.K_q or key == pygame.K_ESCAPE:
            self.running = False

        elif key == pygame.K_SPACE:
            self.music.toggle_pause()

        elif key == pygame.K_n:
            self.music.next_track()

        elif key == pygame.K_p:
            self.music.prev_track()

        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.music.volume_up()

        elif key in (pygame.K_MINUS, pygame.K_UNDERSCORE, pygame.K_KP_MINUS):
            self.music.volume_down()

        elif key == pygame.K_e:
            self.hud.toggle_effects_menu()

        elif key == pygame.K_h:
            if self.hud.visible:
                self.hud.visible = False
                self.hud.opacity = 0
            else:
                self.hud.visible = True
                self.hud.opacity = 255
                self.hud.activity()

        elif key == pygame.K_f:
            self._toggle_fullscreen()

        elif key == pygame.K_l:
            self._open_file_dialog()

        # Quick effect selection (1-5)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
            idx = key - pygame.K_1
            effects = ["wave", "aurora", "particles", "gradient_pulse", "matrix"]
            if idx < len(effects):
                self.renderer.set_effect(effects[idx])
                self.hud.selected_effect_index = idx
                self.hud.activity()

    def _toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode."""
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            info = pygame.display.Info()
            self.width, self.height = info.current_w, info.current_h
            self.screen = pygame.display.set_mode(
                (self.width, self.height),
                pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE
            )
        else:
            self.width, self.height = 1280, 720
            self.screen = pygame.display.set_mode(
                (self.width, self.height),
                pygame.RESIZABLE | pygame.DOUBLEBUF | pygame.HWSURFACE
            )
        self.renderer.screen = self.screen
        self.renderer.width = self.width
        self.renderer.height = self.height
        self.hud = HUD(self.width, self.height)

    def _handle_resize(self, w, h):
        """Handle window resize."""
        self.width, self.height = w, h
        self.screen = pygame.display.set_mode(
            (w, h), pygame.RESIZABLE | pygame.DOUBLEBUF | pygame.HWSURFACE
        )
        self.renderer.screen = self.screen
        self.renderer.width = w
        self.renderer.height = h
        self.hud = HUD(w, h)

    def _open_file_dialog(self):
        """Simple file path input via terminal."""
        print("\nEnter wallpaper file path (or press Enter to cancel): ", end="", flush=True)
        # Note: In a full app this would use a proper file dialog (tkinter, etc.)
        # For now, wallpapers can be specified via --wallpaper flag

    def _update(self):
        """Update game state."""
        pass

    def _render(self):
        """Render everything."""
        # Clear screen
        self.screen.fill((0, 0, 0))

        # Get audio level for reactive visuals
        audio_level = self.music.get_audio_level()

        # Render wallpaper/effect
        self.renderer.render(audio_level)

        # Render HUD overlay
        track_info = self.music.get_track_info()
        fps = self.clock.get_fps()
        hud_surface = self.hud.render(
            track_info=track_info,
            volume=self.music.volume,
            is_playing=self.music.is_playing,
            is_paused=self.music.is_paused,
            audio_level=audio_level,
            current_effect=self.renderer.effect,
            fps=fps
        )
        if hud_surface:
            self.screen.blit(hud_surface, (0, 0))

        pygame.display.flip()

    def _cleanup(self):
        """Clean shutdown."""
        self.music.cleanup()
        pygame.quit()


def main():
    args = parse_args()
    engine = WallpaperEngine(args)
    engine.run()


if __name__ == "__main__":
    main()
