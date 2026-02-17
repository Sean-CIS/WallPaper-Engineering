"""
Animated wallpaper renderer using pygame.

Supports:
- Static images (PNG, JPG, BMP)
- Animated GIFs (frame-by-frame playback)
- Procedural animations (shader-like effects)
- Video-style frame sequences
"""

import os
import math
import time
import pygame
from PIL import Image


class WallpaperRenderer:
    """Core renderer for animated wallpapers."""

    def __init__(self, screen, wallpaper_path=None):
        self.screen = screen
        self.width, self.height = screen.get_size()
        self.clock = pygame.time.Clock()
        self.fps = 30
        self.time_offset = 0.0
        self.start_time = time.time()

        # GIF animation state
        self.gif_frames = []
        self.gif_delays = []
        self.current_frame = 0
        self.last_frame_time = 0

        # Active effect
        self.effect = "wave"  # default procedural effect
        self.wallpaper_surface = None
        self.wallpaper_path = None

        if wallpaper_path:
            self.load_wallpaper(wallpaper_path)

    def load_wallpaper(self, path):
        """Load a wallpaper file (image or animated GIF)."""
        self.wallpaper_path = path
        if not os.path.exists(path):
            print(f"Wallpaper not found: {path}")
            return False

        ext = os.path.splitext(path)[1].lower()

        if ext == ".gif":
            return self._load_gif(path)
        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            return self._load_static_image(path)
        else:
            print(f"Unsupported format: {ext}")
            return False

    def _load_gif(self, path):
        """Load animated GIF frames using Pillow."""
        try:
            pil_image = Image.open(path)
            self.gif_frames = []
            self.gif_delays = []
            self.current_frame = 0

            frame_count = 0
            while True:
                try:
                    pil_image.seek(frame_count)
                    frame = pil_image.convert("RGBA")
                    frame = frame.resize((self.width, self.height), Image.LANCZOS)

                    raw = frame.tobytes()
                    surface = pygame.image.fromstring(raw, frame.size, "RGBA")
                    self.gif_frames.append(surface)

                    delay = pil_image.info.get("duration", 100) / 1000.0
                    self.gif_delays.append(max(delay, 0.02))

                    frame_count += 1
                except EOFError:
                    break

            if self.gif_frames:
                self.effect = "gif"
                self.last_frame_time = time.time()
                print(f"Loaded GIF: {frame_count} frames")
                return True

        except Exception as e:
            print(f"Error loading GIF: {e}")
        return False

    def _load_static_image(self, path):
        """Load a static image and scale it to screen size."""
        try:
            img = pygame.image.load(path)
            self.wallpaper_surface = pygame.transform.scale(img, (self.width, self.height))
            self.effect = "static_parallax"
            print(f"Loaded static image: {path}")
            return True
        except Exception as e:
            print(f"Error loading image: {e}")
            return False

    def set_effect(self, effect_name):
        """Switch the active visual effect."""
        self.effect = effect_name

    def render(self, audio_level=0.0):
        """Render one frame of the current wallpaper/effect."""
        t = time.time() - self.start_time + self.time_offset

        if self.effect == "gif":
            self._render_gif()
        elif self.effect == "static_parallax":
            self._render_static_parallax(t, audio_level)
        elif self.effect == "wave":
            self._render_wave(t, audio_level)
        elif self.effect == "aurora":
            self._render_aurora(t, audio_level)
        elif self.effect == "particles":
            self._render_particles(t, audio_level)
        elif self.effect == "gradient_pulse":
            self._render_gradient_pulse(t, audio_level)
        elif self.effect == "matrix":
            self._render_matrix(t, audio_level)
        else:
            self._render_wave(t, audio_level)

    def _render_gif(self):
        """Render the current GIF frame."""
        if not self.gif_frames:
            return
        now = time.time()
        if now - self.last_frame_time >= self.gif_delays[self.current_frame]:
            self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
            self.last_frame_time = now
        self.screen.blit(self.gif_frames[self.current_frame], (0, 0))

    def _render_static_parallax(self, t, audio_level):
        """Render static image with subtle parallax/breathing effect."""
        if self.wallpaper_surface is None:
            return
        scale = 1.02 + 0.01 * math.sin(t * 0.5) + audio_level * 0.02
        w = int(self.width * scale)
        h = int(self.height * scale)
        scaled = pygame.transform.scale(self.wallpaper_surface, (w, h))
        ox = (w - self.width) // 2 + int(5 * math.sin(t * 0.3))
        oy = (h - self.height) // 2 + int(5 * math.cos(t * 0.4))
        self.screen.blit(scaled, (-ox, -oy))

    def _render_wave(self, t, audio_level):
        """Procedural ocean wave animation with audio reactivity."""
        boost = 1.0 + audio_level * 2.0
        for y in range(0, self.height, 2):
            for x in range(0, self.width, 4):
                wave = math.sin(x * 0.01 + t * 2) * 20 * boost
                wave += math.sin(y * 0.02 + t * 1.5) * 10
                r = int(10 + 20 * math.sin(t * 0.3 + x * 0.005))
                g = int(30 + 40 * math.sin(t * 0.2 + y * 0.008))
                b = int(80 + 60 * math.sin(t * 0.5 + (x + y) * 0.003))
                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))
                yy = int(y + wave)
                if 0 <= yy < self.height:
                    pygame.draw.rect(self.screen, (r, g, b), (x, yy, 4, 2))

    def _render_aurora(self, t, audio_level):
        """Northern lights / aurora borealis effect."""
        self.screen.fill((5, 5, 20))
        boost = 1.0 + audio_level * 3.0
        for layer in range(5):
            speed = 0.3 + layer * 0.15
            amplitude = (40 + layer * 20) * boost
            y_base = self.height * 0.3 + layer * 30
            for x in range(0, self.width, 3):
                wave_y = y_base + amplitude * math.sin(x * 0.008 + t * speed + layer)
                wave_y += amplitude * 0.5 * math.sin(x * 0.015 + t * speed * 1.3)
                height = int(60 + 40 * math.sin(t * 0.4 + x * 0.01))
                green = int(100 + 100 * math.sin(t * 0.2 + layer * 0.5))
                blue = int(80 + 80 * math.sin(t * 0.3 + layer * 0.7))
                alpha = max(20, min(120, int(80 * math.sin(x * 0.005 + t * 0.5))))
                color = (20, max(0, min(255, green)), max(0, min(255, blue)))
                surf = pygame.Surface((3, height), pygame.SRCALPHA)
                surf.fill((*color, alpha))
                self.screen.blit(surf, (x, int(wave_y)))

    def _render_particles(self, t, audio_level):
        """Floating particle system with audio reactivity."""
        self.screen.fill((10, 10, 30))
        num_particles = 200
        boost = 1.0 + audio_level * 5.0
        for i in range(num_particles):
            seed = i * 137.508
            px = (seed * 13.37 + t * (20 + i % 5) * boost) % self.width
            py = (seed * 7.13 + t * (10 + i % 3)) % self.height
            size = int(2 + 3 * math.sin(t + i) + audio_level * 4)
            brightness = int(100 + 100 * math.sin(t * 0.5 + i * 0.3))
            r = max(0, min(255, brightness + int(50 * math.sin(i * 0.1))))
            g = max(0, min(255, brightness + int(50 * math.sin(i * 0.15 + 1))))
            b = max(0, min(255, int(200 + 55 * math.sin(i * 0.2 + 2))))
            pygame.draw.circle(self.screen, (r, g, b), (int(px), int(py)), max(1, size))

    def _render_gradient_pulse(self, t, audio_level):
        """Pulsing gradient effect that reacts to music."""
        boost = 1.0 + audio_level * 2.0
        for y in range(0, self.height, 4):
            ratio = y / self.height
            pulse = 0.5 + 0.5 * math.sin(t * 1.5 * boost + ratio * 3)
            r = int(40 * pulse + 60 * math.sin(t * 0.7 + ratio * 2))
            g = int(20 * pulse + 100 * ratio * math.sin(t * 0.5))
            b = int(120 * pulse + 80 * (1 - ratio))
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            pygame.draw.rect(self.screen, (r, g, b), (0, y, self.width, 4))

    def _render_matrix(self, t, audio_level):
        """Matrix-style digital rain effect."""
        self.screen.fill((0, 0, 0))
        columns = self.width // 14
        boost = 1.0 + audio_level * 3.0
        for col in range(columns):
            seed = col * 97.31
            x = col * 14
            speed = (2 + (seed % 5)) * boost
            y_start = int((seed * 3.7 + t * speed * 30) % (self.height + 300)) - 300
            trail_len = int(10 + seed % 15)
            for j in range(trail_len):
                y = y_start - j * 16
                if 0 <= y < self.height:
                    fade = 1.0 - (j / trail_len)
                    char_code = int((seed + t * 5 + j * 13) % 94) + 33
                    green = int(255 * fade)
                    font = pygame.font.SysFont("monospace", 14)
                    char_surf = font.render(chr(char_code), True, (0, green, int(green * 0.3)))
                    self.screen.blit(char_surf, (x, y))
