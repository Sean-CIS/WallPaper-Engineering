"""
HUD / overlay UI for the wallpaper engine.

Renders on-screen controls, track info, visualizer bars,
and effect selection overlay.
"""

import math
import time
import pygame


class HUD:
    """Heads-up display overlay for the wallpaper engine."""

    def __init__(self, screen_width, screen_height):
        self.width = screen_width
        self.height = screen_height
        self.visible = True
        self.auto_hide_time = 4.0  # seconds before auto-hide
        self.last_activity = time.time()
        self.opacity = 255
        self.fade_speed = 5

        # Fonts
        pygame.font.init()
        self.font_large = pygame.font.SysFont("Arial", 28, bold=True)
        self.font_medium = pygame.font.SysFont("Arial", 20)
        self.font_small = pygame.font.SysFont("Arial", 14)

        # Visualizer bars
        self.bar_count = 40
        self.bar_heights = [0.0] * self.bar_count

        # Effect menu
        self.show_effects_menu = False
        self.effects_list = [
            ("wave", "Ocean Waves"),
            ("aurora", "Aurora Borealis"),
            ("particles", "Floating Particles"),
            ("gradient_pulse", "Gradient Pulse"),
            ("matrix", "Digital Rain"),
        ]
        self.selected_effect_index = 0

    def activity(self):
        """Signal user activity to keep HUD visible."""
        self.last_activity = time.time()
        self.visible = True
        self.opacity = 255

    def toggle_effects_menu(self):
        """Toggle the effects selection menu."""
        self.show_effects_menu = not self.show_effects_menu
        self.activity()

    def render(self, track_info, volume, is_playing, is_paused, audio_level,
               current_effect, fps):
        """Render the full HUD overlay. Returns a surface to blit."""
        now = time.time()
        idle_time = now - self.last_activity

        # Auto-fade after idle
        if idle_time > self.auto_hide_time and not self.show_effects_menu:
            self.opacity = max(0, self.opacity - self.fade_speed)
            if self.opacity == 0:
                self.visible = False

        if not self.visible and not self.show_effects_menu:
            return None

        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        alpha = self.opacity

        # Bottom bar background
        bar_rect = pygame.Rect(0, self.height - 120, self.width, 120)
        pygame.draw.rect(overlay, (0, 0, 0, min(180, alpha)), bar_rect)

        # Audio visualizer bars along the bottom
        self._render_visualizer(overlay, audio_level, alpha)

        # Track info
        self._render_track_info(overlay, track_info, is_playing, is_paused, alpha)

        # Volume indicator
        self._render_volume(overlay, volume, alpha)

        # Controls hint
        self._render_controls_hint(overlay, alpha)

        # FPS counter (top-right)
        fps_text = self.font_small.render(f"FPS: {fps:.0f}", True, (200, 200, 200, alpha))
        overlay.blit(fps_text, (self.width - 80, 10))

        # Effect name (top-left)
        effect_text = self.font_small.render(f"Effect: {current_effect}", True,
                                              (200, 200, 200, alpha))
        overlay.blit(effect_text, (10, 10))

        # Effects selection menu
        if self.show_effects_menu:
            self._render_effects_menu(overlay)

        return overlay

    def _render_visualizer(self, surface, audio_level, alpha):
        """Render audio visualizer bars."""
        bar_width = max(2, (self.width - 40) // self.bar_count)
        max_height = 50
        x_start = 20

        for i in range(self.bar_count):
            t = time.time()
            target = audio_level * (0.5 + 0.5 * abs(math.sin(t * 3 + i * 0.5)))
            target *= (0.6 + 0.4 * abs(math.sin(i * 0.3 + t)))

            # Smooth animation
            self.bar_heights[i] = self.bar_heights[i] * 0.7 + target * 0.3

            h = int(self.bar_heights[i] * max_height)
            h = max(2, min(max_height, h))

            x = x_start + i * (bar_width + 2)
            y = self.height - 15 - h

            # Color gradient based on height
            ratio = h / max_height
            r = int(50 + 200 * ratio)
            g = int(200 - 100 * ratio)
            b = int(255 - 150 * ratio)

            color = (min(255, r), max(0, g), max(0, b), min(200, alpha))
            pygame.draw.rect(surface, color, (x, y, bar_width, h), border_radius=1)

    def _render_track_info(self, surface, track_info, is_playing, is_paused, alpha):
        """Render current track info."""
        y_base = self.height - 105

        # Play state icon
        if is_paused:
            state = "II  PAUSED"
        elif is_playing:
            state = ">>  NOW PLAYING"
        else:
            state = "[]  STOPPED"

        state_surf = self.font_small.render(state, True, (180, 180, 180, alpha))
        surface.blit(state_surf, (20, y_base))

        # Track name
        name = track_info.get("name", "No track")
        if len(name) > 50:
            name = name[:47] + "..."
        name_surf = self.font_large.render(name, True, (255, 255, 255, alpha))
        surface.blit(name_surf, (20, y_base + 18))

        # Track position in playlist
        idx = track_info.get("index", 0)
        total = track_info.get("total", 0)
        pos_text = f"Track {idx}/{total}" if total > 0 else ""
        pos_surf = self.font_small.render(pos_text, True, (150, 150, 150, alpha))
        surface.blit(pos_surf, (20, y_base + 52))

    def _render_volume(self, surface, volume, alpha):
        """Render volume bar."""
        y_base = self.height - 85
        x_base = self.width - 200

        vol_text = self.font_small.render(f"Vol: {int(volume * 100)}%", True,
                                           (180, 180, 180, alpha))
        surface.blit(vol_text, (x_base, y_base))

        # Volume bar
        bar_bg = pygame.Rect(x_base, y_base + 20, 160, 6)
        pygame.draw.rect(surface, (60, 60, 60, alpha), bar_bg, border_radius=3)

        bar_fill = pygame.Rect(x_base, y_base + 20, int(160 * volume), 6)
        pygame.draw.rect(surface, (100, 200, 255, alpha), bar_fill, border_radius=3)

    def _render_controls_hint(self, surface, alpha):
        """Render keyboard shortcut hints."""
        hints = "SPACE: Play/Pause  |  N: Next  |  P: Prev  |  +/-: Volume  |  E: Effects  |  H: Hide  |  Q: Quit"
        hint_surf = self.font_small.render(hints, True, (120, 120, 120, min(150, alpha)))
        x = (self.width - hint_surf.get_width()) // 2
        surface.blit(hint_surf, (x, self.height - 15))

    def _render_effects_menu(self, surface):
        """Render the effects selection popup."""
        menu_w, menu_h = 300, 40 + len(self.effects_list) * 40
        menu_x = (self.width - menu_w) // 2
        menu_y = (self.height - menu_h) // 2

        # Background
        pygame.draw.rect(surface, (20, 20, 40, 230),
                         (menu_x, menu_y, menu_w, menu_h), border_radius=10)
        pygame.draw.rect(surface, (80, 80, 120, 200),
                         (menu_x, menu_y, menu_w, menu_h), width=2, border_radius=10)

        # Title
        title = self.font_medium.render("Select Effect", True, (255, 255, 255))
        surface.blit(title, (menu_x + (menu_w - title.get_width()) // 2, menu_y + 8))

        # Effect options
        for i, (key, name) in enumerate(self.effects_list):
            y = menu_y + 40 + i * 40
            selected = i == self.selected_effect_index

            if selected:
                pygame.draw.rect(surface, (60, 60, 120, 180),
                                 (menu_x + 10, y, menu_w - 20, 35), border_radius=5)

            color = (100, 200, 255) if selected else (180, 180, 180)
            text = self.font_medium.render(f"  {name}", True, color)
            surface.blit(text, (menu_x + 20, y + 7))

            # Shortcut key
            key_text = self.font_small.render(f"[{i+1}]", True, (100, 100, 100))
            surface.blit(key_text, (menu_x + menu_w - 50, y + 10))

    def handle_effects_input(self, key):
        """Handle keyboard input for effects menu. Returns effect name or None."""
        if key == pygame.K_UP:
            self.selected_effect_index = (self.selected_effect_index - 1) % len(self.effects_list)
            return None
        elif key == pygame.K_DOWN:
            self.selected_effect_index = (self.selected_effect_index + 1) % len(self.effects_list)
            return None
        elif key == pygame.K_RETURN:
            effect_key = self.effects_list[self.selected_effect_index][0]
            self.show_effects_menu = False
            return effect_key
        elif key == pygame.K_ESCAPE:
            self.show_effects_menu = False
            return None

        # Number keys 1-5
        for i in range(min(5, len(self.effects_list))):
            if key == pygame.K_1 + i:
                self.selected_effect_index = i
                effect_key = self.effects_list[i][0]
                self.show_effects_menu = False
                return effect_key

        return None
