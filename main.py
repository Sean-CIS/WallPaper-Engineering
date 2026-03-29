#!/usr/bin/env python3
"""
WallPaper Engine - Animated Desktop Wallpapers with Music

A Python-based animated wallpaper that renders BEHIND your desktop icons,
just like Wallpaper Engine. On Windows it uses the Win32 WorkerW trick
to embed the pygame surface into the desktop layer.

Features a clock widget, dual-layer audio (ambient + music playing
simultaneously), and audio-reactive procedural effects.

Controls:
    SPACE       - Play / Pause music
    N           - Next track
    P           - Previous track
    + / =       - Volume up
    - / _       - Volume down
    A           - Toggle ambient sound
    C           - Toggle clock display
    E           - Open effects menu
    1-5         - Quick select effect
    H           - Toggle HUD overlay
    Q / ESC     - Quit

Usage:
    python main.py                          # Desktop wallpaper (default)
    python main.py --window                 # Regular foreground window
    python main.py --ambient ocean.ogg      # Layer an ambient sound under music
    python main.py --effect aurora          # Desktop wallpaper with aurora effect
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
        description="WallPaper Engine - Animated desktop wallpapers with music",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Effects:
  wave            Ocean wave animation
  aurora          Northern lights / aurora borealis
  particles       Floating particle field
  gradient_pulse  Pulsing color gradients
  matrix          Digital rain (Matrix style)

Examples:
  python main.py                              # Desktop wallpaper mode (default)
  python main.py --window                     # Regular window mode
  python main.py --effect matrix              # Matrix rain on desktop
  python main.py --ambient ocean_waves.ogg    # Layer ambient under music
  python main.py --wallpaper scene.gif        # GIF on desktop
  python main.py --window --width 1280 --height 720   # Windowed at custom size
        """
    )
    parser.add_argument("--wallpaper", "-w", type=str, default=None,
                        help="Path to wallpaper file (GIF, PNG, JPG)")
    parser.add_argument("--scene", "-s", type=str, default=None,
                        help="Path to Wallpaper Engine scene.pkg file")
    parser.add_argument("--music", "-m", type=str, default="assets/music",
                        help="Path to music folder (default: assets/music)")
    parser.add_argument("--ambient", "-a", type=str, default=None,
                        help="Path to ambient sound file (loops under music)")
    parser.add_argument("--ambient-dir", type=str, default="assets/ambient",
                        help="Folder to auto-scan for ambient sounds (default: assets/ambient)")
    parser.add_argument("--ambient-volume", type=float, default=0.5,
                        help="Ambient volume 0.0-1.0 (default: 0.5)")
    parser.add_argument("--effect", "-e", type=str, default="aurora",
                        choices=["wave", "aurora", "particles", "gradient_pulse", "matrix"],
                        help="Procedural effect to use (default: aurora)")
    parser.add_argument("--width", type=int, default=1280,
                        help="Window width in --window mode (default: 1280)")
    parser.add_argument("--height", type=int, default=720,
                        help="Window height in --window mode (default: 720)")
    parser.add_argument("--fps", type=int, default=30,
                        help="Target FPS (default: 30)")
    parser.add_argument("--window", action="store_true",
                        help="Run as a regular window instead of a desktop wallpaper")
    parser.add_argument("--fullscreen", "-f", action="store_true",
                        help="Fullscreen window (only in --window mode)")
    parser.add_argument("--no-hud", action="store_true",
                        help="Start with HUD hidden")
    parser.add_argument("--no-clock", action="store_true",
                        help="Start with the clock hidden")
    return parser.parse_args()


def _can_embed_desktop():
    """Check if we're on Windows and can do the desktop embed."""
    if sys.platform != "win32":
        return False
    try:
        from wallpaper_engine.desktop import embed_pygame_window
        return True
    except ImportError:
        return False


class WallpaperEngine:
    """Main application class that orchestrates rendering and audio."""

    def __init__(self, args):
        pygame.init()
        pygame.display.set_caption("WallPaper Engine")

        self.target_fps = args.fps
        self.desktop_mode = False
        self.pygame_hwnd = None

        # Decide mode: desktop wallpaper (default on Windows) or regular window
        use_desktop = not args.window and _can_embed_desktop()

        if use_desktop:
            self._init_desktop_mode()
        elif args.fullscreen:
            self._init_fullscreen_mode()
        else:
            self._init_window_mode(args.width, args.height)

        self.clock = pygame.time.Clock()

        # Initialize subsystems
        self.renderer = WallpaperRenderer(self.screen)
        self.music = MusicPlayer()
        self.hud = HUD(self.width, self.height)

        # Load wallpaper or scene
        if args.scene:
            if not self.renderer.load_scene(args.scene):
                print("[wallpaper] Scene load failed, falling back to effect")
                self.renderer.set_effect(args.effect)
        elif args.wallpaper:
            self.renderer.load_wallpaper(args.wallpaper)
        else:
            self.renderer.set_effect(args.effect)

        # Load audio from scene or from CLI args
        if args.scene and self.renderer.scene_renderer:
            self._load_scene_audio()
        else:
            # Scan for music
            music_dir = os.path.abspath(args.music)
            self.music.scan_music_folder(music_dir)

            # Load ambient sound — explicit file takes priority, else scan folder
            self.music.set_ambient_volume(args.ambient_volume)
            if args.ambient:
                self.music.load_ambient(os.path.abspath(args.ambient))
            else:
                ambient_dir = os.path.abspath(args.ambient_dir)
                self.music.scan_ambient_folder(ambient_dir)

        # HUD / clock visibility
        if args.no_hud:
            self.hud.visible = False
        if args.no_clock:
            self.hud.show_clock = False

        self.running = True

    def _init_desktop_mode(self):
        """Set up the window and embed it as the desktop wallpaper."""
        from wallpaper_engine.desktop import get_worker_w_size, embed_pygame_window

        # Get the actual WorkerW size in physical pixels (DPI-aware)
        self._worker_w, ww_width, ww_height = get_worker_w_size()

        if not self._worker_w:
            print("[wallpaper] WARNING: Could not find WorkerW, falling back to window")
            self._init_window_mode(1920, 1080)
            return

        # Use the WorkerW's real physical pixel size
        self.width, self.height = ww_width, ww_height

        # Create a borderless window at the WorkerW's real resolution
        os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
        flags = pygame.NOFRAME | pygame.DOUBLEBUF | pygame.HWSURFACE
        self.screen = pygame.display.set_mode((self.width, self.height), flags)

        # Get the pygame window handle and embed it behind icons
        wm_info = pygame.display.get_wm_info()
        self.pygame_hwnd = wm_info.get("window")

        if self.pygame_hwnd and embed_pygame_window(self.pygame_hwnd, self._worker_w,
                                                     self.width, self.height):
            self.desktop_mode = True
            print(f"[wallpaper] Desktop mode active ({self.width}x{self.height})")
        else:
            print("[wallpaper] WARNING: Desktop embed failed, falling back to borderless window")
            self.desktop_mode = False

    def _load_scene_audio(self):
        """Load audio extracted from a WE scene into the music player."""
        audio_info = self.renderer.scene_renderer.get_audio_paths()
        for info in audio_info:
            name = info.get("name", "")
            path = info.get("path", "")
            volume = info.get("volume", 1.0)

            if "ambien" in name.lower() or "wave" in name.lower() or "ocean" in name.lower():
                # Treat as ambient
                self.music.load_ambient(path)
                self.music.set_ambient_volume(volume)
            else:
                # Treat as music
                self.music.playlist.append(path)
                self.music.volume = volume

    def _init_fullscreen_mode(self):
        """Set up a regular fullscreen window."""
        info = pygame.display.Info()
        self.width, self.height = info.current_w, info.current_h
        flags = pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE
        self.screen = pygame.display.set_mode((self.width, self.height), flags)

    def _init_window_mode(self, width, height):
        """Set up a regular resizable window."""
        self.width = width
        self.height = height
        flags = pygame.RESIZABLE | pygame.DOUBLEBUF | pygame.HWSURFACE
        self.screen = pygame.display.set_mode((self.width, self.height), flags)

    def run(self):
        """Main application loop."""
        mode_str = "DESKTOP WALLPAPER" if self.desktop_mode else "WINDOW"
        print("\n" + "=" * 50)
        print("  WallPaper Engine v1.0")
        print(f"  Mode: {mode_str} ({self.width}x{self.height})")
        print("=" * 50)
        print("\nControls:")
        print("  SPACE  - Play/Pause    N/P - Next/Prev track")
        print("  +/-    - Volume        A   - Toggle ambient")
        print("  C      - Toggle clock  E   - Effects menu")
        if not self.desktop_mode:
            print("  F      - Fullscreen    H   - Toggle HUD")
        else:
            print("  H      - Toggle HUD")
        print("  1-5    - Quick effect   Q  - Quit")
        print("=" * 50 + "\n")

        # Auto-play music if available
        if self.music.playlist:
            self.music.play()

        # Auto-play ambient if loaded
        if self.music.ambient_sound:
            self.music.play_ambient()

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

            if event.type == pygame.VIDEORESIZE and not self.desktop_mode:
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

        elif key == pygame.K_a:
            self.music.toggle_ambient()

        elif key == pygame.K_c:
            self.hud.toggle_clock()

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

        elif key == pygame.K_f and not self.desktop_mode:
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
        """Toggle between fullscreen and windowed mode (window mode only)."""
        self.fullscreen = not getattr(self, "fullscreen", False)
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

    def _update(self):
        """Update game state."""
        pass

    def _render(self):
        """Render everything."""
        self.screen.fill((0, 0, 0))

        # Get audio level for reactive visuals
        audio_level = self.music.get_audio_level()

        # Render wallpaper/effect
        self.renderer.render(audio_level)

        # Render HUD overlay (includes clock)
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
        # Clean up scene renderer
        if self.renderer.scene_renderer:
            self.renderer.scene_renderer.cleanup()
        # Detach from desktop if we were embedded
        if self.desktop_mode and self.pygame_hwnd:
            try:
                from wallpaper_engine.desktop import detach_pygame_window
                detach_pygame_window(self.pygame_hwnd)
            except Exception:
                pass
        self.music.cleanup()
        pygame.quit()


def main():
    args = parse_args()
    engine = WallpaperEngine(args)
    engine.run()


if __name__ == "__main__":
    main()
