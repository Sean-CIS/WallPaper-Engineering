"""
Steam Wallpaper Engine workshop content importer.

Parses project.json files from Wallpaper Engine workshop items
and extracts usable assets (preview GIFs, images, etc.).
"""

import os
import json
import shutil


# Default Steam Workshop paths for Wallpaper Engine (app ID 431960)
STEAM_WORKSHOP_PATHS = [
    os.path.expanduser("~/.steam/steam/steamapps/workshop/content/431960"),
    os.path.expanduser("~/.local/share/Steam/steamapps/workshop/content/431960"),
    "C:\\Program Files (x86)\\Steam\\steamapps\\workshop\\content\\431960",
    "D:\\SteamLibrary\\steamapps\\workshop\\content\\431960",
]


def find_workshop_folder():
    """Find the Wallpaper Engine workshop content folder."""
    for path in STEAM_WORKSHOP_PATHS:
        if os.path.exists(path):
            return path
    return None


def list_workshop_items(workshop_path=None):
    """List all installed workshop wallpaper items."""
    if workshop_path is None:
        workshop_path = find_workshop_folder()
    if not workshop_path or not os.path.exists(workshop_path):
        return []

    items = []
    for item_id in os.listdir(workshop_path):
        item_dir = os.path.join(workshop_path, item_id)
        if not os.path.isdir(item_dir):
            continue

        project_file = os.path.join(item_dir, "project.json")
        info = {"id": item_id, "path": item_dir}

        if os.path.exists(project_file):
            try:
                with open(project_file, "r", encoding="utf-8") as f:
                    project = json.load(f)
                info["title"] = project.get("title", "Unknown")
                info["type"] = project.get("type", "unknown")
                info["file"] = project.get("file", "")
                info["preview"] = project.get("preview", "")
            except (json.JSONDecodeError, IOError):
                info["title"] = f"Workshop Item {item_id}"

        # Check for common asset files
        for fname in ("preview.gif", "preview.jpg", "preview.png", "preview"):
            fpath = os.path.join(item_dir, fname)
            if os.path.exists(fpath):
                info["preview_path"] = fpath
                break

        items.append(info)

    return items


def import_workshop_item(item_id, workshop_path=None, dest_folder="assets/wallpapers"):
    """
    Import a workshop item's preview/assets into the local assets folder.

    Args:
        item_id: The Steam Workshop item ID (e.g., "3418185490")
        workshop_path: Path to workshop content folder
        dest_folder: Destination folder for imported assets

    Returns:
        Path to the imported wallpaper file, or None on failure.
    """
    if workshop_path is None:
        workshop_path = find_workshop_folder()
    if not workshop_path:
        print("Could not find Steam Workshop folder")
        return None

    item_dir = os.path.join(workshop_path, str(item_id))
    if not os.path.exists(item_dir):
        print(f"Workshop item {item_id} not found")
        return None

    os.makedirs(dest_folder, exist_ok=True)

    # Try to find a usable wallpaper asset
    # Priority: preview GIF > scene preview > any image
    candidates = [
        "preview.gif", "preview", "preview.jpg", "preview.png",
        "scene.gif", "scene.jpg", "scene.png",
    ]

    for candidate in candidates:
        src = os.path.join(item_dir, candidate)
        if os.path.exists(src):
            # Determine extension
            ext = os.path.splitext(candidate)[1]
            if not ext:
                # Try to detect from file magic bytes
                with open(src, "rb") as f:
                    header = f.read(4)
                if header[:3] == b"GIF":
                    ext = ".gif"
                elif header[:2] == b"\xff\xd8":
                    ext = ".jpg"
                elif header[:4] == b"\x89PNG":
                    ext = ".png"
                else:
                    ext = ".bin"

            dest = os.path.join(dest_folder, f"workshop_{item_id}{ext}")
            shutil.copy2(src, dest)
            print(f"Imported: {candidate} -> {dest}")
            return dest

    print(f"No usable wallpaper asset found in workshop item {item_id}")
    return None


def parse_project_json(project_path):
    """Parse a Wallpaper Engine project.json and return metadata."""
    try:
        with open(project_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "title": data.get("title", "Unknown"),
            "type": data.get("type", "unknown"),
            "description": data.get("description", ""),
            "file": data.get("file", ""),
            "preview": data.get("preview", ""),
            "tags": data.get("tags", []),
            "visibility": data.get("visibility", ""),
            "general": data.get("general", {}),
        }
    except (json.JSONDecodeError, IOError, FileNotFoundError) as e:
        print(f"Error parsing project.json: {e}")
        return None
