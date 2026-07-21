import hashlib
import json
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
    fetch_latest_release,
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

    def test_reads_latest_release_from_static_manifest_without_api(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / "latest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "version": "1.0.1",
                        "tag": "v1.0.1",
                        "notes": "Fix update checks.",
                        "page_url": "https://github.com/xiaolikabbk-boop/QuickVideoEditor/releases/tag/v1.0.1",
                        "package_name": "QuickVideoEditor-v1.0.1-win-x64.zip",
                        "package_url": "https://github.com/xiaolikabbk-boop/QuickVideoEditor/releases/download/v1.0.1/QuickVideoEditor-v1.0.1-win-x64.zip",
                        "checksum_url": "https://github.com/xiaolikabbk-boop/QuickVideoEditor/releases/download/v1.0.1/QuickVideoEditor-v1.0.1-win-x64.zip.sha256",
                    }
                ),
                encoding="utf-8",
            )
            release = fetch_latest_release(
                "1.0.0",
                manifest_url=manifest.as_uri(),
                api_url="https://api.invalid/should-not-be-used",
            )
            self.assertIsNotNone(release)
            self.assertEqual("1.0.1", release.version)
            self.assertEqual("Fix update checks.", release.notes)

    def test_static_manifest_reports_current_version_without_api(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / "latest.json"
            manifest.write_text(json.dumps({"version": "1.0.1"}), encoding="utf-8")
            self.assertIsNone(
                fetch_latest_release(
                    "1.0.1",
                    manifest_url=manifest.as_uri(),
                    api_url="https://api.invalid/should-not-be-used",
                )
            )


if __name__ == "__main__":
    unittest.main()
