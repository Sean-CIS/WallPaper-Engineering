"""
Reader for Wallpaper Engine PKGV0023 binary archives.

Format:
    Header (12 bytes):
        uint32  unknown (always 8)
        char[4] magic   "PKGV"
        char[4] version "0023"
    uint32 entry_count
    Entry[entry_count]:
        uint32       name_length
        char[N]      name (UTF-8)
        uint32       data_offset (relative to data section start)
        uint32       data_size
    Data section: all file data packed sequentially
"""

import json
import struct


class PkgEntry:
    __slots__ = ("name", "offset", "size")

    def __init__(self, name, offset, size):
        self.name = name
        self.offset = offset
        self.size = size

    def __repr__(self):
        return f"PkgEntry({self.name!r}, offset={self.offset}, size={self.size})"


class PkgReader:
    """Read files from a Wallpaper Engine .pkg archive."""

    def __init__(self, path):
        self.path = path
        self.entries = {}
        self._data_offset = 0

        with open(path, "rb") as f:
            self._parse_header(f)

    def _parse_header(self, f):
        # Header: uint32 + "PKGV" + "0023"
        unknown = struct.unpack("<I", f.read(4))[0]
        magic = f.read(4)
        version = f.read(4)

        if magic != b"PKGV":
            raise ValueError(f"Not a PKG file: magic={magic!r}")

        entry_count = struct.unpack("<I", f.read(4))[0]

        # Parse file table
        for _ in range(entry_count):
            name_len = struct.unpack("<I", f.read(4))[0]
            name = f.read(name_len).decode("utf-8")
            offset = struct.unpack("<I", f.read(4))[0]
            size = struct.unpack("<I", f.read(4))[0]
            self.entries[name] = PkgEntry(name, offset, size)

        # Data section starts right after the file table
        self._data_offset = f.tell()

    def list_files(self):
        """Return list of all file paths in the archive."""
        return list(self.entries.keys())

    def read_file(self, name):
        """Read raw bytes of a file from the archive."""
        entry = self.entries.get(name)
        if entry is None:
            raise KeyError(f"File not found in PKG: {name}")

        with open(self.path, "rb") as f:
            f.seek(self._data_offset + entry.offset)
            return f.read(entry.size)

    def read_json(self, name):
        """Read and parse a JSON file from the archive."""
        data = self.read_file(name)
        return json.loads(data.decode("utf-8"))

    def has_file(self, name):
        """Check if a file exists in the archive."""
        return name in self.entries

    def file_size(self, name):
        """Get the size of a file in bytes."""
        entry = self.entries.get(name)
        return entry.size if entry else 0
