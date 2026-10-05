#!/usr/bin/env python3
"""Deterministic tests for Codex unit-art generation (no Codex call is made)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codex_art  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 4096 + b"\0\0\0\0IEND\xaeB`\x82"


class CodexArtTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "ws"
        self.workspace.mkdir()
        self.job = {"id": "art-sw-unit-nr-trooper", "unit_id": "sw_unit_nr_trooper",
                    "unit_name": "New Republic Trooper"}
        patches = [
            mock.patch.object(codex_art.ticket_runner, "resolve_codex_executable", return_value="/x/codex.exe"),
            mock.patch.object(codex_art.ticket_runner, "require_codex_chatgpt_quota", return_value={}),
            mock.patch.object(codex_art, "_managed_directory", return_value=self.workspace),
            mock.patch.object(codex_art, "_windows_path", return_value="C:\\\\ws"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_prompt_uses_art_direction_and_excludes_artist_names(self) -> None:
        direction = codex_art.load_direction(ROOT)
        prompt = codex_art.build_prompt(direction, "sw_hero_thrawn", "Grand Admiral", "sprite")
        self.assertIn("blue skin", prompt)
        self.assertIn("No text", prompt)
        self.assertIn("exactly ONE", prompt)
        self.assertIn("sprite.png", prompt)
        for name in ("Dorman", "McQuarrie", "Alex Ross", "Granov"):
            self.assertNotIn(name, prompt)

    def test_every_campaign_one_unit_has_art_direction(self) -> None:
        import re
        direction = codex_art.load_direction(ROOT)
        units = set()
        for path in [*(ROOT / "addons/Star_Wars_Thrawn_Trilogy/units").glob("hte_*.cfg"), *(ROOT / "addons/Star_Wars_Thrawn_Trilogy/units").glob("dfr_*.cfg"), *(ROOT / "addons/Star_Wars_Thrawn_Trilogy/units").glob("tlc_*.cfg")]:
            units.update(re.findall(r"(?m)^\[unit_type\]\n    id=(\S+)", path.read_text(encoding="utf-8")))
        self.assertTrue(units)
        self.assertEqual(sorted(units - set(direction["units"])), [])

    def test_generated_images_are_derived_into_the_state_set(self) -> None:
        calls = []

        def runner(command, **kwargs):
            self.assertEqual(command[-1], "-")
            kind = "sprite" if "sprite.png" in kwargs["input"] else "portrait"
            calls.append(kind)
            (self.workspace / f"{kind}.png").write_bytes(PNG)
            return subprocess.CompletedProcess(command, 0, f"{kind}.png\n", "")

        with mock.patch.object(codex_art, "_run_tool", return_value=json.dumps({"written": ["a"] * 13})) as tool:
            result = codex_art.generate_unit_art(ROOT, self.job, runner=runner)
        self.assertEqual(calls, ["sprite", "portrait"])
        self.assertEqual(result["state"], "generated")
        self.assertEqual(result["written"], 13)
        self.assertEqual(tool.call_args.args[1], codex_art.DERIVE_TOOL)

    def test_vehicles_need_only_one_image(self) -> None:
        job = {"id": "art-sw-unit-im-tie-fighter", "unit_id": "sw_unit_im_tie_fighter", "unit_name": "TIE Fighter"}
        calls = []

        def runner(command, **kwargs):
            calls.append(kwargs["input"])
            (self.workspace / "sprite.png").write_bytes(PNG)
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(codex_art, "_run_tool", return_value=json.dumps({"written": []})):
            result = codex_art.generate_unit_art(ROOT, job, runner=runner)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["state"], "generated")

    def test_images_left_in_the_codex_session_are_harvested(self) -> None:
        home = Path(self.temp.name) / "codex-home"
        session = home / "generated_images" / "session-1"
        session.mkdir(parents=True)
        made = iter([PNG.replace(b"\0" * 8, b"sprite..", 1), PNG.replace(b"\0" * 8, b"portrait", 1)])

        def runner(command, **kwargs):
            (session / f"exec-{len(list(session.iterdir()))}.png").write_bytes(next(made))
            return subprocess.CompletedProcess(command, 0, "done", "")

        with mock.patch.object(codex_art.ticket_runner, "require_codex_chatgpt_quota",
                               return_value={"CODEX_HOME": str(home)}), \
                mock.patch.object(codex_art, "_run_tool", return_value=json.dumps({"written": ["a"] * 13})):
            result = codex_art.generate_unit_art(ROOT, self.job, runner=runner)
        self.assertEqual(result["state"], "generated")
        self.assertIn(b"sprite..", (self.workspace / "sprite.png").read_bytes())
        self.assertIn(b"portrait", (self.workspace / "portrait.png").read_bytes())

    def test_every_speaking_character_gets_a_dialogue_portrait(self) -> None:
        job = {"id": "art-sw-hero-han", "unit_id": "sw_hero_han", "unit_name": "Smuggler General"}
        calls = []

        def runner(command, **kwargs):
            kind = "sprite" if "sprite.png" in kwargs["input"] else "portrait"
            calls.append(kwargs["input"])
            (self.workspace / f"{kind}.png").write_bytes(PNG)
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(codex_art, "_run_tool", return_value=json.dumps({"written": []})):
            codex_art.generate_unit_art(ROOT, job, runner=runner)
        # Film-portrayed heroes get a real head-and-shoulders portrait; the
        # art rules keep the face original and unlike any actor.
        self.assertEqual(len(calls), 2)
        self.assertIn("head-and-shoulders portrait", calls[1])
        self.assertIn("must not resemble any real actor", calls[1])

    def test_pilot_heroes_get_a_pilot_portrait_not_the_craft(self) -> None:
        direction = codex_art.load_direction(ROOT)
        prompt = codex_art.build_prompt(direction, "sw_hero_wedge", "Wedge Antilles", "portrait")
        self.assertIn("flight suit", prompt)
        self.assertNotIn("four-winged starfighter", prompt)
        sprite = codex_art.build_prompt(direction, "sw_hero_wedge", "Wedge Antilles", "sprite")
        self.assertIn("four-winged starfighter", sprite)
        # Owner rule: no character or franchise names in any prompt.
        for text in (prompt, sprite):
            self.assertNotIn("Wedge Antilles", text)
            self.assertNotIn("Star Wars", text)

    def test_portrait_only_generation_fits_the_portrait_and_keeps_sprites(self) -> None:
        def runner(command, **kwargs):
            (self.workspace / "portrait.png").write_bytes(PNG)
            return subprocess.CompletedProcess(command, 0, "portrait.png", "")

        with mock.patch.object(codex_art, "_run_tool", return_value="{}") as tool:
            result = codex_art.generate_portrait(ROOT, "sw_hero_pellaeon", "Captain Pellaeon", runner=runner)
        self.assertEqual(result["state"], "generated")
        self.assertEqual(tool.call_args.args[1], codex_art.PORTRAIT_TOOL)
        self.assertIn("sw-hero-pellaeon", tool.call_args.args)

    def test_old_sessions_are_never_harvested(self) -> None:
        home = Path(self.temp.name) / "codex-home"
        old = home / "generated_images" / "old"
        old.mkdir(parents=True)
        (old / "x.png").write_bytes(PNG)
        import os
        os.utime(old / "x.png", (1000, 1000))
        os.utime(old, (1000, 1000))
        self.assertEqual(codex_art.harvest_generated(home, 5000.0, 6000.0), [])

    def test_truncated_png_is_not_complete(self) -> None:
        path = self.workspace / "partial.png"
        path.write_bytes(PNG[:-12])
        self.assertFalse(codex_art._valid_png(path))
        path.write_bytes(PNG)
        self.assertTrue(codex_art._valid_png(path))

    def test_image_from_before_the_call_is_never_harvested(self) -> None:
        import os
        home = Path(self.temp.name) / "codex-home"
        session = home / "generated_images" / "s"
        session.mkdir(parents=True)
        (session / "prev.png").write_bytes(PNG)
        os.utime(session / "prev.png", (4990.0, 4990.0))
        self.assertEqual(codex_art.harvest_generated(home, 5000.0, 6000.0), [])

    def test_an_image_is_never_harvested_twice(self) -> None:
        home = Path(self.temp.name) / "codex-home"
        session = home / "generated_images" / "s2"
        session.mkdir(parents=True)
        image = session / "once.png"
        image.write_bytes(PNG)
        codex_art._HARVESTED.add(str(image))
        try:
            self.assertEqual(codex_art.harvest_generated(home, 0.0, 9e12), [])
        finally:
            codex_art._HARVESTED.discard(str(image))

    def test_refused_design_keeps_code_drawn_art(self) -> None:
        refusal = 'error=image generation failed: "code": "moderation_blocked"'
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, refusal, ""))
        with mock.patch.object(codex_art, "_run_tool", return_value="{}") as tool:
            result = codex_art.generate_unit_art(ROOT, self.job, runner=runner)
        self.assertEqual(result["state"], "coded_fallback")
        self.assertEqual(tool.call_args.args[1], codex_art.CODED_TOOL)

    def test_refused_luke_uses_the_painted_master(self) -> None:
        refusal = 'error=image generation failed: "code": "moderation_blocked"'
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, refusal, ""))
        job = {"id": "art-sw-hero-luke", "unit_id": "sw_hero_luke", "unit_name": "Luke Skywalker"}
        with mock.patch.object(codex_art, "_run_tool", return_value="{}") as tool:
            result = codex_art.generate_unit_art(ROOT, job, runner=runner)
        self.assertEqual(result["state"], "coded_fallback")
        tools = [call.args[1] for call in tool.call_args_list]
        self.assertEqual(tools, [codex_art.PAINT_TOOL, codex_art.DERIVE_TOOL])

    def test_derivation_rejects_a_flat_shape_instead_of_a_unit(self) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow is only installed for the art toolchain")
        sys.path.insert(0, str(ROOT / "production" / "tools"))
        import derive_unit_frames
        disc = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
        ImageDraw.Draw(disc).ellipse((2, 2, 70, 70), fill=(20, 60, 250, 255))
        self.assertIn("distinct colors", derive_unit_frames.degenerate_reason(disc))
        painted = Image.new("RGBA", (72, 72))
        painted.putdata([(x * 3, y * 3, (x + y) * 2 % 256, 255) for y in range(72) for x in range(72)])
        self.assertIsNone(derive_unit_frames.degenerate_reason(painted))

    def test_usage_limit_pauses_without_fallback(self) -> None:
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 1, "You've hit your usage limit.", ""))
        with mock.patch.object(codex_art, "_run_tool") as tool:
            result = codex_art.generate_unit_art(ROOT, self.job, runner=runner)
        self.assertEqual(result["state"], "quota_paused")
        tool.assert_not_called()

    def test_invalid_job_is_rejected(self) -> None:
        with self.assertRaises(codex_art.CodexArtError):
            codex_art.generate_unit_art(ROOT, {"id": "../etc", "unit_id": "x"})


if __name__ == "__main__":
    unittest.main()
