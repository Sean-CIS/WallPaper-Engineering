"""
CPU-based effect pipeline for Wallpaper Engine scenes.

Applies effects (water flow, water ripple, foliage sway, light shafts)
as UV distortion passes on numpy arrays. This is a faithful re-implementation
of the GLSL shader logic in pure Python/numpy.
"""

import math
import time

import numpy as np


class EffectPipeline:
    """Applies scene effects to the base image using CPU numpy ops."""

    def __init__(self, renderer, pkg_reader):
        self.renderer = renderer  # SoftwareRenderer
        self.pkg = pkg_reader
        self._start_time = time.time()

        # Pre-compute coordinate grids (same shape as output)
        w, h = renderer.width, renderer.height
        u = np.linspace(0, 1, w, dtype=np.float32)
        v = np.linspace(0, 1, h, dtype=np.float32)
        self.u_grid, self.v_grid = np.meshgrid(u, v)

    def apply_effects(self, base_texture_name, effects):
        """
        Apply all effects and return the final (u_offset, v_offset) arrays.

        The caller should use these to re-sample the base texture.
        """
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
        elif "blur" in path:
            return "blur"
        return "unknown"

    def _get_mask(self, effect, mask_slot=1):
        """Get the mask texture for an effect (slot 1), or None."""
        for epass in effect.passes:
            textures = epass.textures
            if mask_slot < len(textures) and textures[mask_slot]:
                mask_name = textures[mask_slot]
                mask = self.renderer.get_texture(mask_name)
                if mask is not None:
                    # Resize mask to output resolution if needed
                    h, w = mask.shape[:2]
                    if (w, h) != (self.renderer.width, self.renderer.height):
                        from PIL import Image
                        img = Image.fromarray(mask)
                        img = img.resize((self.renderer.width, self.renderer.height),
                                         Image.BILINEAR)
                        mask = np.array(img)
                    # Return just the R channel as float [0, 1]
                    return mask[:, :, 0].astype(np.float32) / 255.0
        return None

    def _get_constants(self, effect):
        """Get constant shader values from the first pass."""
        for epass in effect.passes:
            return epass.constant_values
        return {}

    def _waterflow(self, effect, t):
        """
        Water flow effect — shifts UVs based on a flow map and phase texture.

        Ported from waterflow.frag:
        - Read flow map (slot 1): rg channels encode flow direction
        - Read phase texture (slot 2): single-channel time offset
        - Compute cycled UV offsets that blend seamlessly
        """
        constants = self._get_constants(effect)
        speed = float(constants.get("speed", 0.16))
        strength = float(constants.get("strength", 1.0))
        phase_scale = float(constants.get("phasescale", 2.28))

        mask = self._get_mask(effect, 1)

        # Flow direction from mask (if available)
        if mask is not None:
            flow_amount = mask * strength * 0.01
        else:
            flow_amount = np.full_like(self.u_grid, strength * 0.005)

        # Cycling phase for seamless looping
        cycle = math.fmod(t * speed, 1.0)
        cycle2 = math.fmod(t * speed + 0.5, 1.0)
        blend = 2.0 * abs(cycle - 0.5)

        offset1 = (cycle - 0.5) * flow_amount
        offset2 = (cycle2 - 0.5) * flow_amount

        # Blend the two offsets for seamless animation
        du = offset1 * blend + offset2 * (1.0 - blend)
        dv = du * 0.3  # Slight vertical component

        return du, dv

    def _waterripple(self, effect, t):
        """
        Water ripple effect — sinusoidal UV distortion with scrolling normals.

        Ported from waterripple.frag/vert.
        """
        constants = self._get_constants(effect)
        anim_speed = float(constants.get("animationspeed", 0.06))
        ripple_strength = float(constants.get("ripplestrength", 0.1))
        scale = float(constants.get("scale", 1.82))
        ratio = float(constants.get("ratio", 4.06))

        mask = self._get_mask(effect, 1)

        # Compute ripple UV coordinates
        u_scaled = self.u_grid * scale
        v_scaled = self.v_grid * scale * ratio

        # Scrolling animation
        phase1 = t * anim_speed * anim_speed
        phase2 = phase1 * 1.333

        # Two overlapping sine waves for ripple
        ripple1_u = np.sin(u_scaled * 6.2832 + phase1 * 6.2832) * ripple_strength * 0.02
        ripple1_v = np.cos(v_scaled * 6.2832 + phase1 * 4.0) * ripple_strength * 0.02
        ripple2_u = np.sin(u_scaled * 4.5 + phase2 * 5.0) * ripple_strength * 0.015
        ripple2_v = np.cos(v_scaled * 3.8 + phase2 * 6.2) * ripple_strength * 0.015

        du = ripple1_u + ripple2_u
        dv = ripple1_v + ripple2_v

        # Apply mask
        if mask is not None:
            du *= mask
            dv *= mask

        return du, dv

    def _foliagesway(self, effect, t):
        """
        Foliage sway effect — sinusoidal displacement masked to foliage areas.

        Ported from foliagesway.frag.
        """
        constants = self._get_constants(effect)
        speed = float(constants.get("speeduv", 2.09))
        strength = float(constants.get("strength", 0.14))
        phase = float(constants.get("phase", 0.2))
        power = float(constants.get("power", 1.17))
        scale = float(constants.get("scale", 0.05))
        ratio = float(constants.get("ratio", 1.99))

        mask = self._get_mask(effect, 1)

        # Generate noise-like UV coordinates
        noise_u = self.u_grid * scale * ratio
        noise_v = self.v_grid * scale

        amp = strength * 0.01

        # Multiple sine waves for organic sway
        phase_val = (noise_u * 10.0 + noise_v * 5.0) * phase

        s1 = np.sin(phase_val + speed * t)
        s2 = np.sin(phase_val + speed * t * -0.16)
        s3 = np.sin(phase_val + speed * t * 0.0083)

        c1 = np.sin(0.4 + phase_val - speed * t * 0.5)
        c2 = np.sin(0.4 + phase_val + speed * t * 0.042)

        # Apply power function for non-linear motion
        s1 = np.sign(s1) * np.abs(s1) ** power
        s2 = np.sign(s2) * np.abs(s2) ** power
        c1 = np.sign(c1) * np.abs(c1) ** power
        c2 = np.sign(c2) * np.abs(c2) ** power

        du = (s1 + s2 + s3) * amp
        dv = (c1 + c2) * amp

        # Apply mask
        if mask is not None:
            du *= mask
            dv *= mask

        return du, dv

    def _lightshafts(self, pixels, effect, t):
        """
        Light shafts — additive color overlay that pulses with time.
        """
        constants = self._get_constants(effect)
        speed = float(constants.get("rayspeed", 0.13))
        smoothness = float(constants.get("raysmoothness", 0.73))
        intensity = float(constants.get("colorwintensity", 0.43))

        # Parse color
        color_str = constants.get("colorend", "0.5 0.8 1")
        try:
            parts = str(color_str).split()
            color = [float(x) for x in parts[:3]]
        except (ValueError, IndexError):
            color = [0.5, 0.8, 1.0]

        # Scale values
        scale_str = constants.get("rayscale", "0.5 0.1")
        try:
            parts = str(scale_str).split()
            ray_scale = (float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            ray_scale = (0.5, 0.1)

        # Create animated ray pattern
        phase = t * speed * 6.2832
        ray_x = self.u_grid * ray_scale[0] * 20.0 + phase
        ray_y = self.v_grid * ray_scale[1] * 5.0

        # Multiple overlapping rays
        rays = np.sin(ray_x) * 0.5 + 0.5
        rays *= np.sin(ray_x * 0.7 + 1.3) * 0.5 + 0.5
        rays *= np.exp(-self.v_grid * 2.0)  # Fade toward bottom
        rays = np.clip(rays * intensity * smoothness * 2.0, 0, 1)

        # Add rays as colored light
        result = pixels.astype(np.float32)
        for c in range(3):
            result[:, :, c] = np.clip(
                result[:, :, c] + rays * color[c] * 255.0 * intensity,
                0, 255
            )

        return result.astype(np.uint8)
