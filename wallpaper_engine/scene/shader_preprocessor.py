"""
Preprocess Wallpaper Engine GLSL shaders into valid GLSL 330.

WE shaders use a custom dialect with HLSL compatibility:
- texSample2D() instead of texture()
- saturate(), frac(), lerp(), mul()
- CAST2/3/4 macros
- attribute/varying instead of in/out
- #include directives
- // [COMBO] preprocessor defines
"""

import os
import re

# Default WE shader include search path
WE_SHADER_DIR = os.path.join(
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    "Steam", "steamapps", "common", "wallpaper_engine", "assets", "shaders"
)

# HLSL compatibility macros injected after #version
COMPAT_HEADER = """
#define frac fract
#define saturate(x) clamp(x, 0.0, 1.0)
#define fmod mod
#define lerp mix
#define CAST2(x) vec2(x)
#define CAST3(x) vec3(x)
#define CAST4(x) vec4(x)
#define CAST3X3(x) mat3(x)
#define mul(a, b) ((a) * (b))
#define atan2 atan
#define ddx dFdx
#define ddy dFdy
#define texSample2D texture
#define texSample2DLod textureLod
#define tex2D texture
#define tex2Dlod textureLod
#define GLSL 1
#define HLSL 0
#define HLSL_SM30 0
#define MAKE_SAMPLER2D_ARGUMENT(name) sampler2D name
"""

# Regex patterns
_INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"', re.MULTILINE)
_COMBO_RE = re.compile(r'//\s*\[COMBO\]\s*(\{.*?\})')
_REQUIRE_RE = re.compile(r'^\s*#require\s+.*$', re.MULTILINE)


def preprocess_vertex(source, combos=None, include_resolver=None, pkg_reader=None):
    """Preprocess a WE vertex shader into GLSL 330."""
    return _preprocess(source, "vertex", combos, include_resolver, pkg_reader)


def preprocess_fragment(source, combos=None, include_resolver=None, pkg_reader=None):
    """Preprocess a WE fragment shader into GLSL 330."""
    return _preprocess(source, "fragment", combos, include_resolver, pkg_reader)


def _preprocess(source, shader_type, combos=None, include_resolver=None, pkg_reader=None):
    """Full preprocessing pipeline."""
    if combos is None:
        combos = {}

    # 1. Resolve #include directives
    source = _resolve_includes(source, include_resolver, pkg_reader, set())

    # 2. Remove #require directives (WE-specific, not standard GLSL)
    source = _REQUIRE_RE.sub("// (removed #require)", source)

    # 3. Build combo defines
    combo_defines = ""
    for key, value in combos.items():
        if isinstance(value, bool):
            combo_defines += f"#define {key} {1 if value else 0}\n"
        else:
            combo_defines += f"#define {key} {value}\n"

    # 4. Default combo values from // [COMBO] comments
    for match in _COMBO_RE.finditer(source):
        try:
            import json
            combo_json = json.loads(match.group(1))
            combo_name = combo_json.get("combo", "")
            if combo_name and combo_name not in combos:
                default = combo_json.get("default", 0)
                combo_defines += f"#define {combo_name} {default}\n"
        except Exception:
            pass

    # 5. Convert attribute/varying to in/out for GLSL 330
    if shader_type == "vertex":
        source = re.sub(r'\battribute\b', 'in', source)
        source = re.sub(r'\bvarying\b', 'out', source)
    else:
        source = re.sub(r'\bvarying\b', 'in', source)
        # gl_FragColor -> out variable
        if "gl_FragColor" in source:
            source = "out vec4 _fragColor;\n" + source
            source = source.replace("gl_FragColor", "_fragColor")

    # 6. Handle uvec4 for non-skinning (remove if SKINNING is 0)
    # This avoids issues with uvec4 attributes in basic scenes

    # 7. Build final source
    header = "#version 330 core\n"
    header += combo_defines
    header += COMPAT_HEADER

    # Remove any existing #version
    source = re.sub(r'^\s*#version\s+.*$', '', source, flags=re.MULTILINE)

    return header + "\n" + source


def _resolve_includes(source, resolver, pkg_reader, visited):
    """Recursively resolve #include directives."""

    def replace_include(match):
        include_path = match.group(1)

        if include_path in visited:
            return f"// (circular include: {include_path})"
        visited.add(include_path)

        content = None

        # Try custom resolver first
        if resolver:
            content = resolver(include_path)

        # Try PKG reader (for scene-local shaders)
        if content is None and pkg_reader:
            pkg_path = f"shaders/{include_path}"
            if pkg_reader.has_file(pkg_path):
                content = pkg_reader.read_file(pkg_path).decode("utf-8")

        # Try WE install shader directory
        if content is None:
            full_path = os.path.join(WE_SHADER_DIR, include_path)
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

        if content is None:
            return f"// (missing include: {include_path})"

        # Recursively resolve includes in the included file
        return _resolve_includes(content, resolver, pkg_reader, visited)

    return _INCLUDE_RE.sub(replace_include, source)


def extract_combos_from_material(material_json):
    """Extract combo defines from a WE material JSON."""
    combos = {}

    # combos field
    for key, value in material_json.get("combos", {}).items():
        combos[key] = value

    # Some combos are in passes
    for pass_entry in material_json.get("passes", []):
        for key, value in pass_entry.get("combos", {}).items():
            combos[key] = value

    return combos
