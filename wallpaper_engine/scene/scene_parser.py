"""
Parse Wallpaper Engine scene.json into structured data.

Resolves material references, shader paths, texture paths,
effect chains, audio objects, and text overlay objects.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EffectPass:
    """A single render pass within an effect."""
    material_path: str = ""
    shader_base: str = ""
    combos: dict = field(default_factory=dict)
    constant_values: dict = field(default_factory=dict)
    textures: list = field(default_factory=list)  # [None or "path", ...]
    pass_id: int = 0


@dataclass
class SceneEffect:
    """An effect applied to an image object (waterflow, foliagesway, etc.)."""
    effect_file: str = ""
    effect_id: int = 0
    passes: list = field(default_factory=list)  # list of EffectPass
    visible: bool = True
    name: str = ""


@dataclass
class SceneImage:
    """A renderable image object in the scene."""
    obj_id: int = 0
    name: str = ""
    material_path: str = ""
    shader_base: str = ""
    texture_name: str = ""  # The main texture (from material)
    combos: dict = field(default_factory=dict)
    origin: tuple = (0.0, 0.0, 0.0)
    size: tuple = (0.0, 0.0)
    effects: list = field(default_factory=list)  # list of SceneEffect


@dataclass
class SceneAudio:
    """A sound object in the scene."""
    obj_id: int = 0
    name: str = ""
    sound_paths: list = field(default_factory=list)
    volume: float = 1.0
    playback_mode: str = "loop"
    start_silent: bool = False


@dataclass
class SceneText:
    """A text overlay object (clock, date, etc.)."""
    obj_id: int = 0
    name: str = ""
    font_path: str = ""
    point_size: float = 32.0
    origin: tuple = (0.0, 0.0, 0.0)
    scale: tuple = (1.0, 1.0, 1.0)
    size: tuple = (0.0, 0.0)
    brightness: float = 1.0
    effects: list = field(default_factory=list)


@dataclass
class SceneConfig:
    """Full parsed scene configuration."""
    width: int = 3840
    height: int = 2160
    clear_color: tuple = (0.0, 0.0, 0.0)
    images: list = field(default_factory=list)   # list of SceneImage
    audio: list = field(default_factory=list)     # list of SceneAudio
    texts: list = field(default_factory=list)     # list of SceneText


def parse_scene(scene_json, pkg_reader):
    """
    Parse scene.json and resolve all material/effect references.

    Args:
        scene_json: Parsed scene.json dict
        pkg_reader: PkgReader instance for reading material JSONs

    Returns:
        SceneConfig with all objects parsed
    """
    config = SceneConfig()

    # Parse general settings
    general = scene_json.get("general", {})
    ortho = general.get("orthogonalprojection", {})
    config.width = ortho.get("width", 3840)
    config.height = ortho.get("height", 2160)

    clear = general.get("clearcolor", "0 0 0")
    config.clear_color = _parse_vec3(clear)

    # Parse objects
    for obj in scene_json.get("objects", []):
        if "image" in obj:
            config.images.append(_parse_image_object(obj, pkg_reader))
        elif "sound" in obj:
            config.audio.append(_parse_audio_object(obj))
        elif "text" in obj:
            config.texts.append(_parse_text_object(obj))

    return config


def _parse_image_object(obj, pkg_reader):
    """Parse an image object with its material and effects."""
    img = SceneImage()
    img.obj_id = obj.get("id", 0)
    img.name = obj.get("name", "")
    img.origin = _parse_vec3(obj.get("origin", "0 0 0"))
    img.size = _parse_vec2(obj.get("size", "0 0"))

    # Resolve model -> material -> shader + texture
    model_path = obj.get("image", "")
    if model_path and pkg_reader.has_file(model_path):
        model_json = pkg_reader.read_json(model_path)
        mat_path = model_json.get("material", "")
        if mat_path:
            img.material_path = mat_path
            _resolve_material(img, mat_path, pkg_reader)

    # Parse effects
    for eff_data in obj.get("effects", []):
        effect = _parse_effect(eff_data, pkg_reader)
        if effect:
            img.effects.append(effect)

    return img


def _resolve_material(img, mat_path, pkg_reader):
    """Resolve material JSON to get shader and texture info."""
    if not pkg_reader.has_file(mat_path):
        return

    mat_json = pkg_reader.read_json(mat_path)
    passes = mat_json.get("passes", [])
    if not passes:
        return

    first_pass = passes[0]
    img.shader_base = first_pass.get("shader", "")
    img.combos = first_pass.get("combos", {})

    textures = first_pass.get("textures", [])
    if textures:
        img.texture_name = textures[0] if textures[0] else ""


def _parse_effect(eff_data, pkg_reader):
    """Parse a single effect from an object's effects list."""
    effect = SceneEffect()
    effect.effect_file = eff_data.get("file", "")
    effect.effect_id = eff_data.get("id", 0)
    effect.visible = eff_data.get("visible", True)
    effect.name = eff_data.get("name", "")

    if not effect.visible:
        return None

    # Read effect.json to get material references
    effect_json = None
    if effect.effect_file and pkg_reader and pkg_reader.has_file(effect.effect_file):
        effect_json = pkg_reader.read_json(effect.effect_file)

    # Parse passes from the scene object's effect data
    scene_passes = eff_data.get("passes", [])

    # Effect JSON defines the material for each pass
    effect_passes = []
    if effect_json:
        effect_passes = effect_json.get("passes", [])

    for i, scene_pass in enumerate(scene_passes):
        ep = EffectPass()
        ep.pass_id = scene_pass.get("id", 0)
        ep.constant_values = scene_pass.get("constantshadervalues", {})
        ep.combos = scene_pass.get("combos", {})

        # Textures from the scene pass (override material textures)
        ep.textures = scene_pass.get("textures", [])

        # Get material path from the effect definition
        if i < len(effect_passes):
            mat_path = effect_passes[i].get("material", "")
            if mat_path:
                ep.material_path = mat_path
                # Resolve shader from material
                if pkg_reader and pkg_reader.has_file(mat_path):
                    mat_json = pkg_reader.read_json(mat_path)
                    mat_passes = mat_json.get("passes", [])
                    if mat_passes:
                        ep.shader_base = mat_passes[0].get("shader", "")
                        # Merge combos from material
                        mat_combos = mat_passes[0].get("combos", {})
                        merged = dict(mat_combos)
                        merged.update(ep.combos)
                        ep.combos = merged
                        # Material textures (used if scene pass doesn't override)
                        if not ep.textures:
                            ep.textures = mat_passes[0].get("textures", [])

        effect.passes.append(ep)

    return effect


def _parse_audio_object(obj):
    """Parse a sound object."""
    audio = SceneAudio()
    audio.obj_id = obj.get("id", 0)
    audio.name = obj.get("name", "")
    audio.sound_paths = obj.get("sound", [])
    audio.volume = obj.get("volume", 1.0)
    audio.playback_mode = obj.get("playbackmode", "loop")
    audio.start_silent = obj.get("startsilent", False)
    return audio


def _parse_text_object(obj):
    """Parse a text overlay object."""
    text = SceneText()
    text.obj_id = obj.get("id", 0)
    text.name = obj.get("name", "")
    text.font_path = obj.get("font", "")
    text.point_size = obj.get("pointsize", 32.0)
    text.origin = _parse_vec3(obj.get("origin", "0 0 0"))
    text.scale = _parse_vec3(obj.get("scale", "1 1 1"))
    text.size = _parse_vec2(obj.get("size", "0 0"))
    text.brightness = obj.get("brightness", 1.0)

    for eff_data in obj.get("effects", []):
        effect = _parse_effect(eff_data, None)
        if effect:
            text.effects.append(effect)

    return text


def _parse_vec2(s):
    """Parse '1.0 2.0' -> (1.0, 2.0)."""
    if isinstance(s, str):
        parts = s.split()
        if len(parts) >= 2:
            return (float(parts[0]), float(parts[1]))
    return (0.0, 0.0)


def _parse_vec3(s):
    """Parse '1.0 2.0 3.0' -> (1.0, 2.0, 3.0)."""
    if isinstance(s, str):
        parts = s.split()
        if len(parts) >= 3:
            return (float(parts[0]), float(parts[1]), float(parts[2]))
    return (0.0, 0.0, 0.0)
