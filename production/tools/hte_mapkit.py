"""Small deterministic hex-map construction kit for Campaign I maps.

Coordinates are Wesnoth 1-based play-area coordinates (x = column, y = row).
Wesnoth staggers even columns half a hex down ("odd-q" in 0-based terms), so
neighbor and distance math converts to cube coordinates.
"""
from __future__ import annotations

import random
import re
from pathlib import Path

TERRAIN_TOKEN = re.compile(r"^(?:[1-9] )?[A-Z][A-Za-z]{0,3}(?:\^[A-Z][A-Za-z|/\\]{0,3})?$")


def to_cube(x: int, y: int) -> tuple[int, int, int]:
    col, row = x - 1, y - 1
    q = col
    r = row - (col - (col & 1)) // 2
    return q, r, -q - r


def from_cube(q: int, r: int) -> tuple[int, int]:
    col = q
    row = r + (q - (q & 1)) // 2
    return col + 1, row + 1


def distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    aq, ar, as_ = to_cube(*a)
    bq, br, bs = to_cube(*b)
    return max(abs(aq - bq), abs(ar - br), abs(as_ - bs))


def _round_cube(q: float, r: float, s: float) -> tuple[int, int]:
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return rq, rr


def line(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    n = distance(a, b)
    aq, ar, as_ = to_cube(*a)
    bq, br, bs = to_cube(*b)
    out = []
    for i in range(n + 1):
        t = i / n if n else 0.0
        q, r = _round_cube(aq + (bq - aq) * t + 1e-6, ar + (br - ar) * t + 1e-6, as_ + (bs - as_) * t - 2e-6)
        out.append(from_cube(q, r))
    return out


def neighbors(x: int, y: int) -> list[tuple[int, int]]:
    q, r, _ = to_cube(x, y)
    return [from_cube(q + dq, r + dr) for dq, dr in ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))]


# Generators place mainline codes for their meaning (keep, castle, wall,
# floor); the written maps use the add-on's lore terrains, which alias the same
# mainline types (utils/hte_terrain.cfg), so movement and defense are unchanged.
LORE_RESKIN = {
    "Isr": "Qid", "Xos": "Qib", "Urc": "Qit",
    "Kh": "Qkb", "Ch": "Qcb", "Ke": "Qkp", "Ce": "Qcp",
    "Rr": "Qrd", "Rrc": "Qrp",
}


def reskin(code: str) -> str:
    base, sep, overlay = code.partition("^")
    return LORE_RESKIN.get(base, base) + sep + overlay


class HexMap:
    def __init__(self, width: int, height: int, fill: str, seed: int = 1):
        self.w, self.h = width, height
        self.cells = {(x, y): fill for x in range(1, width + 1) for y in range(1, height + 1)}
        self.starts: dict[int, tuple[int, int]] = {}
        self.rng = random.Random(seed)

    def inside(self, x: int, y: int) -> bool:
        return 1 <= x <= self.w and 1 <= y <= self.h

    def set(self, x: int, y: int, code: str) -> None:
        if self.inside(x, y):
            self.cells[(x, y)] = code

    def get(self, x: int, y: int) -> str:
        return self.cells[(x, y)]

    def disc(self, center: tuple[int, int], radius: int, code: str, prob: float = 1.0) -> None:
        for pos in list(self.cells):
            if distance(pos, center) <= radius and self.rng.random() < prob:
                self.cells[pos] = code

    def rect(self, x1: int, y1: int, x2: int, y2: int, code: str) -> None:
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                self.set(x, y, code)

    def path(self, points: list[tuple[int, int]], code: str, width: int = 0, keep: tuple[str, ...] = ()) -> None:
        for a, b in zip(points, points[1:]):
            for p in line(a, b):
                targets = [p] if width == 0 else [q for q in self.cells if distance(q, p) <= width]
                for t in targets:
                    if self.inside(*t) and not any(self.cells[t].startswith(k) for k in keep):
                        self.cells[t] = code

    def scatter(self, code: str, prob: float, where: str | None = None, avoid: tuple[str, ...] = ()) -> None:
        for pos, cur in list(self.cells.items()):
            if where is not None and cur != where:
                continue
            if any(cur.startswith(a) for a in avoid):
                continue
            if self.rng.random() < prob:
                self.cells[pos] = code

    def replace(self, old: str, new: str) -> None:
        for pos, cur in self.cells.items():
            if cur == old:
                self.cells[pos] = new

    def start(self, side: int, x: int, y: int) -> None:
        self.starts[side] = (x, y)

    def tokens(self) -> list[list[str]]:
        """Map rows as written: semantic codes reskinned to the add-on's lore terrains."""
        rows = []
        for y in range(0, self.h + 2):
            row = []
            for x in range(0, self.w + 2):
                cx, cy = min(max(x, 1), self.w), min(max(y, 1), self.h)
                code = reskin(self.cells[(cx, cy)])
                if (x, y) == (cx, cy):
                    for side, pos in self.starts.items():
                        if pos == (x, y):
                            code = f"{side} {code}"
                row.append(code)
            rows.append(row)
        return rows

    def validate(self) -> None:
        for row in self.tokens():
            for tok in row:
                if not TERRAIN_TOKEN.match(tok):
                    raise ValueError(f"invalid terrain token {tok!r}")

    def text(self) -> str:
        self.validate()
        return "\n".join(", ".join(row) for row in self.tokens()) + "\n"

    def write(self, path: Path) -> None:
        path.write_text(self.text(), encoding="utf-8")


# --- preview -----------------------------------------------------------------

PREVIEW_COLORS = [
    ("Qsp", (8, 10, 22)), ("Qsa", (95, 85, 70)), ("Qsd", (110, 115, 125)), ("Qsk", (170, 140, 50)),
    ("Qsc", (140, 145, 160)), ("Qid", (125, 125, 130)), ("Qib", (60, 60, 60)), ("Qit", (40, 38, 44)),
    ("Qrd", (128, 124, 116)), ("Qrp", (172, 168, 158)), ("Qkb", (200, 190, 150)), ("Qcb", (170, 160, 130)), ("Qkp", (200, 190, 150)), ("Qcp", (170, 160, 130)), ("^Fet", (20, 70, 30)), ("^Ftr", (30, 90, 40)), ("^F", (45, 110, 50)),
    ("^V", (200, 60, 60)), ("^E", None), ("^Dr", (120, 110, 100)), ("K", (220, 200, 80)), ("C", (190, 170, 90)),
    ("Xos", (60, 60, 60)), ("Xu", (40, 35, 30)), ("Mm^Xm", (70, 60, 55)), ("Mm", (130, 115, 100)),
    ("Hh", (150, 140, 90)), ("Hhd", (170, 150, 100)), ("Hd", (210, 190, 120)), ("Ww", (70, 120, 190)),
    ("Wwf", (100, 150, 190)), ("Wo", (30, 60, 140)), ("Ss", (80, 100, 70)), ("Dd", (225, 205, 140)),
    ("Ds", (230, 215, 160)), ("Rr", (150, 150, 150)), ("Rrc", (175, 175, 175)), ("Re", (150, 120, 80)),
    ("Rb", (110, 90, 70)), ("Iwr", (140, 100, 60)), ("Isr", (125, 125, 130)), ("Gll", (100, 130, 60)),
    ("Gs", (150, 170, 90)), ("Gd", (140, 160, 80)), ("Gg", (110, 160, 70)), ("Aa", (235, 240, 245)),
]


def _color(code: str) -> tuple[int, int, int]:
    code = re.sub(r"^[1-9] ", "", code)
    for key, col in PREVIEW_COLORS:
        if key.startswith("^"):
            if key in code and col is not None:
                return col
            continue
        if code.split("^")[0] == key or code == key:
            return col  # type: ignore[return-value]
    for key, col in PREVIEW_COLORS:
        if not key.startswith("^") and code.startswith(key) and col:
            return col
    return (255, 0, 255)


def preview(m: HexMap, path: Path, marks: dict[tuple[int, int], str] | None = None, scale: int = 14) -> None:
    from PIL import Image, ImageDraw

    marks = marks or {}
    w = int((m.w + 1) * scale * 1.5) + scale
    h = int((m.h + 1.5) * scale * 1.732) + scale
    img = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for (x, y), code in m.cells.items():
        cx = scale + (x - 1) * scale * 1.5 + scale
        cy = scale + (y - 1) * scale * 1.732 + (scale * 0.866 if x % 2 == 0 else 0) + scale
        pts = [(cx + scale * c, cy + scale * s) for c, s in
               ((1, 0), (0.5, 0.866), (-0.5, 0.866), (-1, 0), (-0.5, -0.866), (0.5, -0.866))]
        d.polygon(pts, fill=_color(code), outline=(20, 20, 20))
        for side, pos in m.starts.items():
            if pos == (x, y):
                d.text((cx - 3, cy - 6), str(side), fill=(255, 255, 255))
        if (x, y) in marks:
            d.text((cx - 3, cy - 6), marks[(x, y)], fill=(255, 255, 0))
    img.save(path)
