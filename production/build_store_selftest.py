"""Exact Git candidate packaging and tamper fixtures."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from build_store import BuildStoreError, stage_candidate, verify_candidate


class BuildStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.store = self.root / "player-builds"
        self.git("init", "--initial-branch=main")
        addon = self.repo / "addons/Star_Wars_Thrawn_Trilogy"
        (addon / "tests").mkdir(parents=True)
        (addon / "images").mkdir()
        (addon / "assets/prompts").mkdir(parents=True)
        (addon / "_main.cfg").write_text("[campaign]\nid=sw_fixture\n[/campaign]\n", encoding="utf-8")
        (addon / "images/icon.png").write_bytes(b"test image bytes")
        (addon / "tests/gameplay-contracts.json").write_text("{}", encoding="utf-8")
        (addon / "assets/prompts/brief.md").write_text("development only", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
        self.commit = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.commit)

    def git(self, *args: str) -> str:
        result = subprocess.run(["git", "-C", str(self.repo), *args], text=True,
                                capture_output=True, check=False)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def test_exact_candidate_excludes_development_files_and_is_idempotent(self) -> None:
        manifest = stage_candidate(self.repo, self.store, self.commit)
        build = self.store / self.commit
        self.assertEqual(manifest["eligibility"], "candidate_unverified")
        self.assertEqual([item["path"] for item in manifest["files"]], ["_main.cfg", "images/icon.png"])
        self.assertFalse((build / "addon/tests").exists())
        self.assertFalse((build / "addon/assets").exists())
        self.assertEqual(stage_candidate(self.repo, self.store, self.commit), manifest)

    def test_altered_or_extra_bytes_fail_verification(self) -> None:
        stage_candidate(self.repo, self.store, self.commit)
        build = self.store / self.commit
        (build / "addon/_main.cfg").write_text("altered", encoding="utf-8")
        with self.assertRaisesRegex(BuildStoreError, "changed"):
            verify_candidate(build)
        (build / "addon/_main.cfg").write_text("[campaign]\nid=sw_fixture\n[/campaign]\n", encoding="utf-8")
        (build / "addon/extra.cfg").write_text("extra", encoding="utf-8")
        with self.assertRaisesRegex(BuildStoreError, "extra"):
            verify_candidate(build)

    def test_unsupported_manifest_cannot_become_eligible(self) -> None:
        stage_candidate(self.repo, self.store, self.commit)
        build = self.store / self.commit
        manifest_path = build / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["eligibility"] = "verified"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(BuildStoreError, "identity"):
            verify_candidate(build)

    def test_unpublished_commit_is_rejected(self) -> None:
        (self.repo / "addons/Star_Wars_Thrawn_Trilogy/_main.cfg").write_text("new", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "unpublished")
        unpublished = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(BuildStoreError, "identity"):
            stage_candidate(self.repo, self.store, unpublished)
        self.assertFalse((self.store / unpublished).exists())


if __name__ == "__main__":
    unittest.main()
