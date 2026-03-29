"""
Main scene renderer that ties together all components:
PKG reading, texture loading, CPU effect pipeline, and text overlays.
"""

import os
import time

import pygame
import numpy as np

from wallpaper_engine.scene.pkg_reader import PkgReader
from wallpaper_engine.scene.tex_reader import read_tex
from wallpaper_engine.scene.scene_parser import parse_scene
from wallpaper_engine.scene.gl_renderer import SoftwareRenderer
from wallpaper_engine.scene.effect_pipeline import EffectPipeline
from wallpaper_engine.scene.text_overlay import TextOverlay


class SceneRenderer:
    """
    Renders a Wallpaper Engine scene to a pygame Surface.

    Usage:
        renderer = SceneRenderer(pkg_path, width, height)
        renderer.load()
        # In your render loop:
        surface = renderer.render_frame()
        screen.blit(surface, (0, 0))
    """

    def __init__(self, pkg_path, width, height):
        self.pkg_path = pkg_path
        self.width = width
        self.height = height

        self.pkg = None
        self.scene_config = None
        self.renderer = None
        self.effect_pipeline = None
        self.text_overlay = None

        self._base_texture_name = None
        self._loaded = False
        self._start_time = time.time()

        # Cache: store the last rendered surface to reuse at lower FPS
        self._cached_surface = None
        self._last_render_time = 0
        self._render_interval = 1.0 / 30  # Match target FPS

    def load(self):
        """Load and compile everything from the PKG."""
        print(f"[scene] Loading scene from {self.pkg_path}")

        # 1. Open PKG
        self.pkg = PkgReader(self.pkg_path)
        files = self.pkg.list_files()
        print(f"[scene] PKG contains {len(files)} files")

        # 2. Parse scene.json
        scene_json = self.pkg.read_json("scene.json")
        self.scene_config = parse_scene(scene_json, self.pkg)
        print(f"[scene] Scene: {self.scene_config.width}x{self.scene_config.height}")
        print(f"[scene] Images: {len(self.scene_config.images)}, "
              f"Audio: {len(self.scene_config.audio)}, "
              f"Texts: {len(self.scene_config.texts)}")

        # 3. Initialize software renderer
        self.renderer = SoftwareRenderer(self.width, self.height)

        # 4. Load textures
        self._load_textures()

        # 5. Initialize effect pipeline
        self.effect_pipeline = EffectPipeline(self.renderer, self.pkg)

        # 6. Initialize text overlays
        self.text_overlay = TextOverlay(
            self.scene_config, self.pkg,
            self.scene_config.width, self.scene_config.height,
            self.width, self.height
        )

        # 7. Extract audio files
        self._audio_paths = self._extract_audio()

        # 8. Determine base texture name
        if self.scene_config.images:
            img = self.scene_config.images[0]
            self._base_texture_name = img.texture_name or img.name

        self._loaded = True
        print("[scene] Scene loaded successfully")

    def _load_textures(self):
        """Load all .tex textures from the PKG."""
        for name in self.pkg.list_files():
            if not name.endswith(".tex"):
                continue

            tex_data = self.pkg.read_file(name)
            img = read_tex(tex_data)
            if img is None:
                print(f"[scene] WARNING: Failed to decode texture {name}")
                continue

            # Build the key matching scene references
            tex_key = name
            if tex_key.startswith("materials/"):
                tex_key = tex_key[len("materials/"):]
            if tex_key.endswith(".tex"):
                tex_key = tex_key[:-4]

            w, h = img.size
            rgba_data = img.tobytes("raw", "RGBA")
            self.renderer.upload_texture(tex_key, w, h, rgba_data)
            print(f"[scene] Loaded texture: {tex_key} ({w}x{h})")

    def _extract_audio(self):
        """Extract audio files from PKG to temp directory for playback."""
        import tempfile
        audio_paths = []

        for audio_obj in self.scene_config.audio:
            for sound_path in audio_obj.sound_paths:
                if self.pkg.has_file(sound_path):
                    data = self.pkg.read_file(sound_path)
                    ext = os.path.splitext(sound_path)[1]
                    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                    tmp.write(data)
                    tmp.close()
                    audio_paths.append({
                        "path": tmp.name,
                        "volume": audio_obj.volume,
                        "mode": audio_obj.playback_mode,
                        "name": audio_obj.name,
                    })
                    print(f"[scene] Extracted audio: {audio_obj.name}")

        return audio_paths

    def get_audio_paths(self):
        """Return list of extracted audio file info dicts."""
        return self._audio_paths if hasattr(self, "_audio_paths") else []

    def render_frame(self):
        """
        Render one frame and return a pygame Surface.

        Uses frame rate limiting to avoid CPU overload on large images.
        """
        if not self._loaded:
            return None

        now = time.time()

        # Rate-limit expensive numpy operations
        if (self._cached_surface is not None and
                now - self._last_render_time < self._render_interval):
            return self._cached_surface

        self._last_render_time = now

        # Find the base texture
        tex_name = self._base_texture_name
        if tex_name is None or self.renderer.get_texture(tex_name) is None:
            # Try alternative names
            for key in self.renderer._textures:
                if "coastal" in key or "landscape" in key:
                    tex_name = key
                    self._base_texture_name = key
                    break

        if tex_name is None:
            return None

        # Step 1: Compute UV distortions from effects
        effects = []
        if self.scene_config.images:
            effects = self.scene_config.images[0].effects

        u_offset, v_offset = self.effect_pipeline.apply_effects(tex_name, effects)

        # Step 2: Render base image with distorted UVs
        pixels = self.renderer.apply_uv_distortion(None, tex_name, u_offset, v_offset)

        # Step 3: Apply light shafts (additive)
        pixels = self.effect_pipeline.apply_lightshafts(pixels, effects)

        # Step 4: Convert to pygame surface
        surface = self.renderer.to_pygame_surface(pixels)

        # Step 5: Render text overlays
        if self.text_overlay:
            self.text_overlay.render(surface)

        self._cached_surface = surface
        return surface

    def cleanup(self):
        """Release all resources."""
        if self.text_overlay:
            self.text_overlay.cleanup()
        if self.renderer:
            self.renderer.release()
        # Clean up temp audio files
        if hasattr(self, "_audio_paths"):
            for info in self._audio_paths:
                try:
                    os.unlink(info["path"])
                except Exception:
                    pass
