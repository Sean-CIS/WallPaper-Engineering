"""
Text overlay rendering for Wallpaper Engine scenes.

Renders clock, date, and day-of-week overlays using Python datetime
instead of the original JavaScript. Extracts OTF/TTF fonts from PKG.
"""

import os
import tempfile
from datetime import datetime

import pygame


class TextOverlay:
    """Renders text overlays (clock, date, etc.) onto a pygame surface."""

    def __init__(self, scene_config, pkg_reader, scene_width, scene_height,
                 target_width, target_height):
        self.scene_config = scene_config
        self.pkg = pkg_reader
        self.scene_width = scene_width
        self.scene_height = scene_height
        self.target_width = target_width
        self.target_height = target_height
        self._fonts = {}
        self._temp_files = []

        # Scale factor from scene coordinates to target pixels
        self.scale_x = target_width / scene_width
        self.scale_y = target_height / scene_height

        # Extract and register fonts
        self._init_fonts()

    def _init_fonts(self):
        """Extract fonts from PKG and create pygame fonts."""
        for text_obj in self.scene_config.texts:
            font_path = text_obj.font_path
            if not font_path or font_path in self._fonts:
                continue

            # Try to extract font from PKG
            if self.pkg and self.pkg.has_file(font_path):
                font_data = self.pkg.read_file(font_path)
                # Write to temp file (pygame needs a file path)
                tmp = tempfile.NamedTemporaryFile(
                    suffix=os.path.splitext(font_path)[1],
                    delete=False
                )
                tmp.write(font_data)
                tmp.close()
                self._temp_files.append(tmp.name)

                try:
                    # Scale point size to target resolution
                    base_size = int(text_obj.point_size)
                    scale = text_obj.scale[0] if text_obj.scale else 1.0
                    pixel_size = int(base_size * scale * self.scale_y * 3)
                    pixel_size = max(12, min(200, pixel_size))
                    font = pygame.font.Font(tmp.name, pixel_size)
                    self._fonts[font_path] = font
                except Exception as e:
                    print(f"[text] Failed to load font {font_path}: {e}")

    def render(self, surface):
        """
        Render all text overlays onto the given pygame surface.

        Uses Python datetime for clock/date text generation.
        """
        now = datetime.now()

        for text_obj in self.scene_config.texts:
            name = text_obj.name.strip().lower()
            text = self._generate_text(name, now)
            if not text:
                continue

            font = self._fonts.get(text_obj.font_path)
            if not font:
                font = pygame.font.SysFont("segoeui", 24)

            # Render text
            brightness = min(2.5, text_obj.brightness)
            color_val = int(min(255, 255 * brightness))
            color = (color_val, color_val, color_val)

            try:
                text_surface = font.render(text, True, color)
            except Exception:
                continue

            # Position: scene coordinates -> target pixels
            # Origin is the center of the text object in scene coords
            ox = text_obj.origin[0] * self.scale_x
            oy = text_obj.origin[1] * self.scale_y

            # Center the text on its origin
            x = int(ox - text_surface.get_width() / 2)
            y = int(oy - text_surface.get_height() / 2)

            surface.blit(text_surface, (x, y))

    def _generate_text(self, name, now):
        """Generate text content based on the overlay name."""
        if "clock" in name:
            return now.strftime("%H:%M")
        elif "day" in name:
            return now.strftime("%A")
        elif "date" in name:
            return now.strftime("%B %d, %Y")
        return None

    def cleanup(self):
        """Remove temporary font files."""
        for path in self._temp_files:
            try:
                os.unlink(path)
            except Exception:
                pass
