"""
CPU-based effect pipeline for Wallpaper Engine scenes.

Applies effects (water flow, water ripple, foliage sway, light shafts)
as UV distortion passes on numpy arrays.

Optimized: masks are cached, grids use effect resolution, and
expensive trig is kept to minimum operations.
"""

import math
import time

import numpy as np


class EffectPipeline:
    """Applies scene effects to the base image using CPU numpy ops."""

    def __init__(self, renderer, pkg_reader):
        self.renderer = renderer
        self.pkg = pkg_reader
        self._start_time = time.time()

        # Pre-compute coordinate grids at effect resolution
        w, h = renderer.fx_w, renderer.fx_h
        u = np.linspace(0, 1, w, dtype=np.float32)
        v = np.linspace(0, 1, h, dtype=np.float32)
        self.u_grid, self.v_grid = np.meshgrid(u, v)
        self._fx_w = w
        self._fx_h = h

        # Mask cache: effect_id -> float32 mask array at effect resolution
        self._mask_cache = {}

        # Pre-compute static grids used by effects
        self._precomputed = {}

    def apply_effects(self, base_texture_name, effects):
        """Apply all effects and return (u_offset, v_offset) arrays."""
        t = time.time() - self._start_time
        u_total = np.zeros_like(self.u_grid)
        v_total = np.zeros_like(self.v_grid)

        for effect in effects:
            if not effect.visible:
                continue

            effect_type = self._classify_effect(effect)

            if effect_type == "waterflow":
                du, dv = self._waterflow(effect, t)
                u_total += du
                v_total += dv
            elif effect_type == "waterripple":
                du, dv = self._waterripple(effect, t)
                u_total += du
                v_total += dv
            elif effect_type == "foliagesway":
                du, dv = self._foliagesway(effect, t)
                u_total += du
                v_total += dv

        return u_total, v_total

    def apply_lightshafts(self, pixels, effects, t=None):
        """Apply light shaft effects as additive blending on pixel data."""
        if t is None:
            t = time.time() - self._start_time

        for effect in effects:
            if not effect.visible:
                continue
            if self._classify_effect(effect) == "lightshafts":
                pixels = self._lightshafts(pixels, effect, t)

        return pixels

    def _classify_effect(self, effect):
        """Determine effect type from its file path."""
        path = effect.effect_file.lower()
        if "waterflow" in path:
            return "waterflow"
        elif "waterripple" in path:
            return "waterripple"
        elif "foliagesway" in path:
            return "foliagesway"
        elif "lightshafts" in path:
            return "lightshafts"
        return "unknown"

    def _get_mask_cached(self, effect, mask_slot=1):
        """Get mask for an effect, caching the result."""
        cache_key = id(effect)
        if cache_key in self._mask_cache:
            return self._mask_cache[cache_key]

        mask = self._load_mask(effect, mask_slot)
        self._mask_cache[cache_key] = mask
        return mask

    def _load_mask(self, effect, mask_slot=1):
        """Load and resize a mask texture."""
        for epass in effect.passes:
            textures = epass.textures
            if mask_slot < len(textures) and textures[mask_slot]:
                mask_name = textures[mask_slot]
                mask = self.renderer.get_texture(mask_name)
                if mask is not None:
                    h, w = mask.shape[:2]
                    if (w, h) != (self._fx_w, self._fx_h):
                        from PIL import Image
                        img = Image.fromarray(mask)
                        img = img.resize((self._fx_w, self._fx_h), Image.BILINEAR)
                        mask = np.array(img)
                    return mask[:, :, 0].astype(np.float32) / 255.0
        return None

    def _get_constants(self, effect):
        """Get constant shader values from the first pass."""
        for epass in effect.passes:
            return epass.constant_values
        return {}

    def _waterflow(self, effect, t):
        """Water flow — shifts UVs based on a flow map."""
        constants = self._get_constants(effect)
        speed = float(constants.get("speed", 0.16))
        strength = float(constants.get("strength", 1.0))

        mask = self._get_mask_cached(effect, 1)

        if mask is not None:
            flow_amount = mask * (strength * 0.01)
        else:
            flow_amount = strength * 0.005

        cycle = math.fmod(t * speed, 1.0)
        cycle2 = math.fmod(t * speed + 0.5, 1.0)
        blend = 2.0 * abs(cycle - 0.5)

        offset1 = (cycle - 0.5) * flow_amount
        offset2 = (cycle2 - 0.5) * flow_amount

        du = offset1 * blend + offset2 * (1.0 - blend)
        dv = du * 0.3

        return du, dv

    def _waterripple(self, effect, t):
        """Water ripple — sinusoidal UV distortion."""
        constants = self._get_constants(effect)
        anim_speed = float(constants.get("animationspeed", 0.06))
        ripple_strength = float(constants.get("ripplestrength", 0.1))
        scale = float(constants.get("scale", 1.82))
        ratio = float(constants.get("ratio", 4.06))

        mask = self._get_mask_cached(effect, 1)

        u_scaled = self.u_grid * (scale * 6.2832)
        v_scaled = self.v_grid * (scale * ratio * 6.2832)

        phase1 = t * anim_speed * anim_speed
        phase2 = phase1 * 1.333

        s = ripple_strength * 0.02
        s2 = ripple_strength * 0.015

        du = np.sin(u_scaled + phase1 * 6.2832) * s + np.sin(self.u_grid * scale * 4.5 + phase2 * 5.0) * s2
        dv = np.cos(v_scaled + phase1 * 4.0) * s + np.cos(self.v_grid * scale * ratio * 3.8 + phase2 * 6.2) * s2

        if mask is not None:
            du *= mask
            dv *= mask

        return du, dv

    def _foliagesway(self, effect, t):
        """Foliage sway — sinusoidal displacement masked to foliage areas."""
        constants = self._get_constants(effect)
        speed = float(constants.get("speeduv", 2.09))
        strength = float(constants.get("strength", 0.14))
        phase = float(constants.get("phase", 0.2))
        power = float(constants.get("power", 1.17))
        scale = float(constants.get("scale", 0.05))
        ratio = float(constants.get("ratio", 1.99))

        mask = self._get_mask_cached(effect, 1)

        # Pre-compute static phase grid (cache it)
        cache_key = f"foliage_phase_{id(effect)}"
        if cache_key not in self._precomputed:
            noise_u = self.u_grid * scale * ratio
            noise_v = self.v_grid * scale
            self._precomputed[cache_key] = (noise_u * 10.0 + noise_v * 5.0) * phase
        phase_val = self._precomputed[cache_key]

        amp = strength * 0.01

        # Simplified: use 2 sine waves instead of 5
        s1 = np.sin(phase_val + speed * t) * amp
        c1 = np.sin(0.4 + phase_val - speed * t * 0.5) * amp

        du = s1
        dv = c1

        if mask is not None:
            du *= mask
            dv *= mask

        return du, dv

    def _lightshafts(self, pixels, effect, t):
        """Light shafts — additive color overlay that pulses with time."""
        constants = self._get_constants(effect)
        speed = float(constants.get("rayspeed", 0.13))
        smoothness = float(constants.get("raysmoothness", 0.73))
        intensity = float(constants.get("colorwintensity", 0.43))

        color_str = constants.get("colorend", "0.5 0.8 1")
        try:
            parts = str(color_str).split()
            color = [float(x) for x in parts[:3]]
        except (ValueError, IndexError):
            color = [0.5, 0.8, 1.0]

        scale_str = constants.get("rayscale", "0.5 0.1")
        try:
            parts = str(scale_str).split()
            ray_scale = (float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            ray_scale = (0.5, 0.1)

        phase = t * speed * 6.2832
        ray_x = self.u_grid * ray_scale[0] * 20.0 + phase

        rays = np.sin(ray_x) * 0.5 + 0.5
        rays *= np.sin(ray_x * 0.7 + 1.3) * 0.5 + 0.5
        rays *= np.exp(-self.v_grid * 2.0)
        factor = intensity * smoothness * 2.0 * 255.0

        result = pixels.astype(np.float32)
        for c in range(3):
            result[:, :, c] = np.clip(
                result[:, :, c] + rays * color[c] * factor,
                0, 255
            )

        return result.astype(np.uint8)
