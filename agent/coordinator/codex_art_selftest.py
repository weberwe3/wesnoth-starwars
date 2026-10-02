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
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 4096


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
        for path in (ROOT / "addons/Star_Wars_Thrawn_Trilogy/units").glob("hte_*.cfg"):
            units.update(re.findall(r"(?m)^\[unit_type\]\n    id=(\S+)", path.read_text(encoding="utf-8")))
        self.assertTrue(units)
        self.assertEqual(sorted(units - set(direction["units"])), [])

    def test_generated_images_are_derived_into_the_state_set(self) -> None:
        calls = []

        def runner(command, **kwargs):
            self.assertEqual(command[-1], "-")
            kind = "sprite" if "sprite.png" in kwargs["input"] else "portrait"
            calls.append(kind)
            (self.workspace / f"{kind}.png").write_bytes(PNG + kind.encode())
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
        made = iter([PNG + b"sprite", PNG + b"portrait"])

        def runner(command, **kwargs):
            (session / f"exec-{len(list(session.iterdir()))}.png").write_bytes(next(made))
            return subprocess.CompletedProcess(command, 0, "done", "")

        with mock.patch.object(codex_art.ticket_runner, "require_codex_chatgpt_quota",
                               return_value={"CODEX_HOME": str(home)}), \
                mock.patch.object(codex_art, "_run_tool", return_value=json.dumps({"written": ["a"] * 13})):
            result = codex_art.generate_unit_art(ROOT, self.job, runner=runner)
        self.assertEqual(result["state"], "generated")
        self.assertEqual((self.workspace / "sprite.png").read_bytes(), PNG + b"sprite")
        self.assertEqual((self.workspace / "portrait.png").read_bytes(), PNG + b"portrait")

    def test_film_characters_get_sprite_framed_portraits(self) -> None:
        job = {"id": "art-sw-hero-han", "unit_id": "sw_hero_han", "unit_name": "Smuggler General"}
        calls = []

        def runner(command, **kwargs):
            calls.append(kwargs["input"])
            (self.workspace / "sprite.png").write_bytes(PNG)
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(codex_art, "_run_tool", return_value=json.dumps({"written": []})):
            codex_art.generate_unit_art(ROOT, job, runner=runner)
        # No close-up portrait is ever requested for a film-portrayed character.
        self.assertEqual(len(calls), 1)
        self.assertEqual((self.workspace / "portrait.png").read_bytes(), PNG)

    def test_old_sessions_are_never_harvested(self) -> None:
        home = Path(self.temp.name) / "codex-home"
        old = home / "generated_images" / "old"
        old.mkdir(parents=True)
        (old / "x.png").write_bytes(PNG)
        import os
        os.utime(old / "x.png", (1000, 1000))
        os.utime(old, (1000, 1000))
        self.assertEqual(codex_art.harvest_generated(home, 5000.0, 6000.0), [])

    def test_refused_design_keeps_code_drawn_art(self) -> None:
        refusal = 'error=image generation failed: "code": "moderation_blocked"'
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, refusal, ""))
        with mock.patch.object(codex_art, "_run_tool", return_value="{}") as tool:
            result = codex_art.generate_unit_art(ROOT, self.job, runner=runner)
        self.assertEqual(result["state"], "coded_fallback")
        self.assertEqual(tool.call_args.args[1], codex_art.CODED_TOOL)

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
