"""Keep franchise and character names out of image-generation prompts.

Owner rule (2026-10-04): Codex prompts never name a character and never
mention the franchise. Art-direction subjects are written in-universe, so
franchise terms are rewritten in plain descriptive words, and a prompt that
still contains a banned word is refused (fail closed).
"""
from __future__ import annotations

import re

# Franchise vocabulary -> plain description (case-insensitive, whole words).
REWRITES = [
    (r"\bnew republic\b", "allied"),
    (r"\brepublic\b", "allied"),
    (r"\bimperial\b", "military"),
    (r"\bempire\b", "regime"),
    (r"\brebels?\b", "resistance"),
    (r"\bwookiees?\b", "tall, shaggy, fur-covered alien"),
    (r"\bblasters?\b", "energy weapon"),
    (r"\blightsabers?\b", "energy blade"),
    (r"\bstormtroopers?\b", "armoured soldier"),
    (r"\bjedi\b", "mystic warrior"),
    (r"\bsith\b", "dark mystic"),
]

# Never allowed in a prompt: the franchise, its characters, species, places
# and named craft. Character names are matched case-sensitively so ordinary
# words (a "wedge" shape, a "han"dle) are not caught.
BANNED_ANY_CASE = [
    "star wars", "starwars", "jedi", "sith", "wookiee", "noghri", "ysalamir", "vornskr", "stormtrooper",
    "lightsaber", "x-wing", "y-wing", "a-wing", "tie fighter", "tie interceptor", "tie bomber",
    "star destroyer", "at-st", "e-web", "kashyyyk", "myrkr", "wayland", "honoghr", "coruscant", "tatooine",
    "endor", "hoth", "bespin", "psadan", "myneyrshi", "dreadnaught", "katana fleet", "mandalorian",
]
BANNED_NAMES = [
    "Luke", "Skywalker", "Leia", "Organa", "Han", "Solo", "Chewbacca", "Chewie", "Lando", "Calrissian",
    "Mara", "Jade", "Thrawn", "Pellaeon", "C'baoth", "Joruus", "Luuke", "Karrde", "Talon", "Wedge",
    "Antilles", "Bel Iblis", "Iblis", "Khabarakh", "Vader", "Palpatine", "Yoda", "Kenobi",
]


def scrub(text: str) -> str:
    for pattern, replacement in REWRITES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def check(prompt: str) -> None:
    """Raise if the prompt names a character or the franchise."""
    low = prompt.lower()
    found = [t for t in BANNED_ANY_CASE if t in low]
    found += [n for n in BANNED_NAMES if re.search(rf"\b{re.escape(n)}\b", prompt)]
    if found:
        raise ValueError("prompt contains banned names or franchise terms: " + ", ".join(sorted(set(found))))
