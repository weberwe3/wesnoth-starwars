"""Negative fixtures for the bounded gameplay contract index."""

import json
from pathlib import Path
import tempfile
import unittest

from contract_store import ContractStoreError, INDEX_PATH, SHARD_DIR, load_contracts


class ContractStoreTests(unittest.TestCase):
    def _write(self, root: Path, rel: str, value: dict) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def _store(self, root: Path, first: list[dict], second: list[dict] | None = None) -> None:
        files = ["first.json"] + (["second.json"] if second is not None else [])
        self._write(root, INDEX_PATH, {"schema_version": 2, "files": files})
        self._write(root, SHARD_DIR + "/first.json", {"schema_version": 1, "contracts": first})
        if second is not None:
            self._write(root, SHARD_DIR + "/second.json", {"schema_version": 1, "contracts": second})

    def test_index_supports_more_than_legacy_hundred_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._store(root, [{"id": f"first-{i}"} for i in range(100)], [{"id": "second-0"}])
            contracts, paths = load_contracts(root)
            self.assertEqual(len(contracts), 101)
            self.assertEqual(len(paths), 3)

    def test_duplicate_id_in_different_shards_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._store(root, [{"id": "same"}], [{"id": "same"}])
            with self.assertRaisesRegex(ContractStoreError, "duplicate"):
                load_contracts(root)

    def test_unlisted_shard_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._store(root, [{"id": "listed"}])
            self._write(root, SHARD_DIR + "/lost.json", {"schema_version": 1, "contracts": [{"id": "lost"}]})
            with self.assertRaisesRegex(ContractStoreError, "differs from index"):
                load_contracts(root)

    def test_missing_shard_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._store(root, [{"id": "listed"}])
            (root / SHARD_DIR / "first.json").unlink()
            with self.assertRaisesRegex(ContractStoreError, "differs from index"):
                load_contracts(root)

    def test_unsupported_index_and_unsafe_name_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, INDEX_PATH, {"schema_version": 3, "files": []})
            with self.assertRaisesRegex(ContractStoreError, "unsupported"):
                load_contracts(root)
            self._write(root, INDEX_PATH, {"schema_version": 2, "files": ["../outside.json"]})
            with self.assertRaisesRegex(ContractStoreError, "invalid"):
                load_contracts(root)

    def test_legacy_fixture_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, INDEX_PATH, {"schema_version": 1, "contracts": [{"id": "old"}]})
            contracts, paths = load_contracts(root)
            self.assertEqual(contracts[0][0]["id"], "old")
            self.assertEqual(paths, [INDEX_PATH])


if __name__ == "__main__":
    unittest.main()
