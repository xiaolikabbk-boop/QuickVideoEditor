import tempfile
import unittest
from pathlib import Path
from unittest import mock

from updater import install_update


class UpdaterTests(unittest.TestCase):
    def test_replaces_entire_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "app.exe").write_bytes(b"new executable")
            (source / "new.txt").write_text("new")
            (target / "old.txt").write_text("old")
            with mock.patch("updater.subprocess.Popen"):
                install_update(source, target, "app.exe")
            self.assertTrue((target / "new.txt").is_file())
            self.assertFalse((target / "old.txt").exists())

    def test_rolls_back_when_new_program_cannot_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "app.exe").write_bytes(b"broken")
            (target / "old.txt").write_text("old")
            with mock.patch("updater.subprocess.Popen", side_effect=OSError("cannot start")):
                with self.assertRaises(OSError):
                    install_update(source, target, "app.exe")
            self.assertTrue((target / "old.txt").is_file())
            self.assertFalse((target / "app.exe").exists())


if __name__ == "__main__":
    unittest.main()
