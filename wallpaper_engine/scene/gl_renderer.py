"""
Software renderer for Wallpaper Engine scenes using numpy + pygame.

Renders the base image and applies effect animations (water flow,
foliage sway, etc.) on the CPU using numpy UV remapping.
No OpenGL required — works with the existing pygame desktop embed.

Performance: renders effects at a reduced internal resolution and
upscales to output size, keeping 30+ FPS on large displays.
"""

import numpy as np
import pygame
from PIL import Image


# Internal effect resolution — effects are computed at this size
# then upscaled. 960x540 = ~500K pixels vs 8.3M at 4K = 16x faster.
EFFECT_WIDTH = 480
EFFECT_HEIGHT = 270


class SoftwareRenderer:
    """CPU-based renderer using numpy for UV distortion effects."""

    def __init__(self, width, height):
        self.width = width
        self.height = height

        # Effect resolution (lower for performance)
        self.fx_w = EFFECT_WIDTH
        self.fx_h = EFFECT_HEIGHT

        # Texture cache: name -> (numpy_array_RGBA, width, height)
        self._textures = {}

        # Pre-compute UV coordinate grids at EFFECT resolution
        self._init_uv_grids()

    def _init_uv_grids(self):
        """Pre-compute UV coordinate arrays at effect resolution."""
        u = np.linspace(0, 1, self.fx_w, dtype=np.float32)
        v = np.linspace(0, 1, self.fx_h, dtype=np.float32)
        self.base_u, self.base_v = np.meshgrid(u, v)

    def upload_texture(self, name, width, height, data, components=4, filter_mode=True):
        """Store image data as a numpy array."""
        if isinstance(data, bytes):
            arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, components))
        elif isinstance(data, np.ndarray):
            arr = data.reshape((height, width, components))
        else:
            arr = np.frombuffer(bytes(data), dtype=np.uint8).reshape((height, width, components))

        self._textures[name] = (arr.copy(), width, height)

    def get_texture(self, name):
        """Get texture numpy array by name, or None."""
        entry = self._textures.get(name)
        return entry[0] if entry else None

    def get_texture_size(self, name):
        """Get (width, height) of a cached texture."""
        entry = self._textures.get(name)
        return (entry[1], entry[2]) if entry else (0, 0)

    def sample_texture(self, name, u_coords, v_coords):
        """
        Sample a texture at given UV coordinates using nearest-neighbor.

        Args:
            name: Texture name
            u_coords: 2D array of U coordinates [0, 1]
            v_coords: 2D array of V coordinates [0, 1]

        Returns:
            RGBA numpy array matching u_coords shape
        """
        entry = self._textures.get(name)
        if entry is None:
            h, w = u_coords.shape
            return np.zeros((h, w, 4), dtype=np.uint8)

        tex_arr, tex_w, tex_h = entry

        # Wrap UVs and convert to pixel coordinates
        px = (np.mod(u_coords, 1.0) * (tex_w - 1)).astype(np.int32)
        py = (np.mod(v_coords, 1.0) * (tex_h - 1)).astype(np.int32)

        # Clamp
        np.clip(px, 0, tex_w - 1, out=px)
        np.clip(py, 0, tex_h - 1, out=py)

        return tex_arr[py, px]

    def render_base_image(self, texture_name):
        """Render the base image at effect resolution."""
        return self.sample_texture(texture_name, self.base_u, self.base_v)

    def apply_uv_distortion(self, base_pixels, texture_name, u_offset, v_offset):
        """
        Apply UV distortion to the base image at effect resolution.

        Returns RGBA array at (fx_h, fx_w, 4).
        """
        new_u = self.base_u + u_offset
        new_v = self.base_v + v_offset
        return self.sample_texture(texture_name, new_u, new_v)

    def to_pygame_surface(self, pixels):
        """Convert an RGBA numpy array to a pygame Surface at output resolution."""
        if not pixels.flags["C_CONTIGUOUS"]:
            pixels = np.ascontiguousarray(pixels)

        h, w = pixels.shape[:2]

        surface = pygame.image.frombuffer(
            pixels.tobytes(), (w, h), "RGBA"
        )

        # Upscale to output resolution if needed
        if w != self.width or h != self.height:
            surface = pygame.transform.smoothscale(surface, (self.width, self.height))

        return surface

    def release(self):
        """Free texture memory."""
        self._textures.clear()
