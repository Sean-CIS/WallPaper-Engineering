"""
Software renderer for Wallpaper Engine scenes using numpy + pygame.

Renders the base image and applies effect animations (water flow,
foliage sway, etc.) on the CPU using numpy UV remapping.
No OpenGL required — works with the existing pygame desktop embed.
"""

import numpy as np
import pygame
from PIL import Image


class SoftwareRenderer:
    """CPU-based renderer using numpy for UV distortion effects."""

    def __init__(self, width, height):
        self.width = width
        self.height = height

        # Texture cache: name -> (numpy_array_RGBA, width, height)
        self._textures = {}

        # Pre-compute UV coordinate grids
        self._init_uv_grids()

    def _init_uv_grids(self):
        """Pre-compute UV coordinate arrays for the output resolution."""
        # u, v in [0, 1] range
        u = np.linspace(0, 1, self.width, dtype=np.float32)
        v = np.linspace(0, 1, self.height, dtype=np.float32)
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
        Sample a texture at given UV coordinates using bilinear filtering.

        Args:
            name: Texture name
            u_coords: 2D array of U coordinates [0, 1]
            v_coords: 2D array of V coordinates [0, 1]

        Returns:
            RGBA numpy array of shape (height, width, 4)
        """
        entry = self._textures.get(name)
        if entry is None:
            return np.zeros((self.height, self.width, 4), dtype=np.uint8)

        tex_arr, tex_w, tex_h = entry

        # Wrap UVs
        u = np.mod(u_coords, 1.0)
        v = np.mod(v_coords, 1.0)

        # Convert to pixel coordinates
        px = (u * (tex_w - 1)).astype(np.int32)
        py = (v * (tex_h - 1)).astype(np.int32)

        # Clamp
        px = np.clip(px, 0, tex_w - 1)
        py = np.clip(py, 0, tex_h - 1)

        return tex_arr[py, px]

    def render_base_image(self, texture_name):
        """
        Render the base image to a numpy RGBA array at output resolution.

        Returns (height, width, 4) uint8 array.
        """
        return self.sample_texture(texture_name, self.base_u, self.base_v)

    def apply_uv_distortion(self, base_pixels, texture_name, u_offset, v_offset):
        """
        Apply UV distortion to the base image.

        Args:
            base_pixels: Original RGBA array (unused — re-samples from texture)
            texture_name: Texture to re-sample
            u_offset: 2D float array of U offsets
            v_offset: 2D float array of V offsets

        Returns:
            New RGBA array with distorted UVs.
        """
        new_u = self.base_u + u_offset
        new_v = self.base_v + v_offset
        return self.sample_texture(texture_name, new_u, new_v)

    def to_pygame_surface(self, pixels):
        """Convert an RGBA numpy array to a pygame Surface."""
        # Ensure contiguous C-order array
        if not pixels.flags["C_CONTIGUOUS"]:
            pixels = np.ascontiguousarray(pixels)

        surface = pygame.image.frombuffer(
            pixels.tobytes(), (self.width, self.height), "RGBA"
        )
        return surface.convert_alpha()

    def release(self):
        """Free texture memory."""
        self._textures.clear()
