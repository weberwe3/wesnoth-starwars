#!/usr/bin/env python3

"""Create minimal original project-owned PNG placeholders for WML references.

This deliberately does not download, copy, or transform external artwork.  It
only creates a small, deterministic abstract trooper silhouette when a ticket
introduces a missing ``images/*.png`` reference.  Audio and non-PNG art remain
fail-closed: they need an explicit original asset from the implementing worker.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import zlib

from gameplay_contracts import ADDON_ROOT, _config_files, _project_resource_references


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload)) + kind + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _rgba_png(width: int, height: int, pixels: list[tuple[int, int, int, int]]) -> bytes:
    raw = b"".join(
        b"\x00" + bytes(channel for pixel in pixels[row * width:(row + 1) * width] for channel in pixel)
        for row in range(height)
    )
    return (
        _PNG_SIGNATURE
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, level=9))
        + _chunk(b"IEND", b"")
    )


def _placeholder_png(relative: str) -> bytes:
    """Draw an original, generic teal-and-slate tactical unit placeholder."""

    portrait = "/portraits/" in f"/{relative}"
    width = height = 256 if portrait else 72
    digest = hashlib.sha256(relative.encode("utf-8")).digest()
    accent = (50 + digest[0] // 3, 150 + digest[1] // 4, 170 + digest[2] // 5)
    pixels = [(0, 0, 0, 0) for _ in range(width * height)]

    def paint(x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            pixels[y * width + x] = color

    scale = max(1, width // 72)
    # An original abstract armored figure: helmet, visor, torso, and a compact
    # blaster-like diagonal. It intentionally contains no franchise emblem.
    for y in range(12 * scale, 34 * scale):
        for x in range(23 * scale, 49 * scale):
            if ((x - 36 * scale) ** 2) / (15 * scale) ** 2 + ((y - 24 * scale) ** 2) / (14 * scale) ** 2 <= 1:
                paint(x, y, (36, 51, 67, 255))
    for y in range(25 * scale, 29 * scale):
        for x in range(26 * scale, 46 * scale):
            paint(x, y, (*accent, 255))
    for y in range(34 * scale, 64 * scale):
        half = max(5 * scale, (64 * scale - y) // 2)
        for x in range(36 * scale - half, 36 * scale + half):
            paint(x, y, (31, 47, 64, 255))
    for step in range(28 * scale):
        paint(44 * scale + step // 2, 43 * scale + step, (*accent, 255))
        paint(45 * scale + step // 2, 43 * scale + step, (15, 28, 40, 255))
    return _rgba_png(width, height, pixels)


def materialize_missing_project_images(root: Path) -> dict[str, object]:
    """Create safe PNG placeholders; reject missing project resources otherwise."""

    generated: list[str] = []
    unsupported: list[str] = []
    try:
        sources = _config_files(root)
    except OSError as exc:
        return {"pass": False, "generated": [], "unsupported": [exc.__class__.__name__]}
    for _source, relative in _project_resource_references(sources):
        destination = root / ADDON_ROOT / relative
        if destination.exists() and destination.is_file() and not destination.is_symlink():
            continue
        if destination.is_symlink() or not relative.startswith("images/") or not relative.endswith(".png"):
            unsupported.append(relative)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_placeholder_png(relative))
        generated.append((Path(ADDON_ROOT) / relative).as_posix())
    return {"pass": not unsupported, "generated": sorted(set(generated)), "unsupported": sorted(set(unsupported))}
