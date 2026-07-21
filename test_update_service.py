import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from update_service import (
    ReleaseInfo,
    UpdateError,
    is_newer_version,
    parse_checksum,
    prepare_update,
    safe_extract_package,
)
from version import APP_NAME, MAIN_EXECUTABLE_NAME, UPDATE_HELPER_NAME


class UpdateServiceTests(unittest.TestCase):
    def test_compares_semantic_versions(self):
        self.assertTrue(is_newer_version("1.10.0", "1.9.9"))
        self.assertTrue(is_newer_version("v2.0.0", "1.99.99"))
        self.assertFalse(is_newer_version("1.0.0-rc.1", "1.0.0"))

    def test_parses_checksum_for_expected_asset(self):
        digest = "a" * 64
        text = f"{'b' * 64}  other.zip\n{digest} *package.zip\n"
        self.assertEqual(digest, parse_checksum(text, "package.zip"))

    def test_rejects_zip_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("../outside.txt", "bad")
            with self.assertRaises(UpdateError):
                safe_extract_package(archive, Path(folder) / "extract")

    def test_prepares_and_verifies_complete_update_from_local_urls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package_name = "QuickVideoEditor-v1.1.0-win-x64.zip"
            archive = root / package_name
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr(f"{APP_NAME}/{MAIN_EXECUTABLE_NAME}", b"main")
                package.writestr(f"{APP_NAME}/{UPDATE_HELPER_NAME}", b"helper")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            checksum = root / f"{package_name}.sha256"
            checksum.write_text(f"{digest}  {package_name}\n", encoding="ascii")
            release = ReleaseInfo(
                version="1.1.0",
                tag="v1.1.0",
                notes="notes",
                page_url="https://example.invalid/release",
                package_url=archive.as_uri(),
                checksum_url=checksum.as_uri(),
                package_name=package_name,
            )
            prepared = prepare_update(release, cache_root=root / "cache")
            self.assertTrue((prepared.package_dir / MAIN_EXECUTABLE_NAME).is_file())
            self.assertTrue((prepared.package_dir / UPDATE_HELPER_NAME).is_file())


if __name__ == "__main__":
    unittest.main()
