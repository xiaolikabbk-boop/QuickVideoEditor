from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


def wait_for_process(pid: int, timeout_seconds: int = 120) -> None:
    if pid <= 0:
        return
    if sys.platform == "win32":
        synchronize = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
        if handle:
            try:
                ctypes.windll.kernel32.WaitForSingleObject(handle, timeout_seconds * 1000)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
            return
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)


def install_update(
    source: Path,
    target: Path,
    executable_name: str,
    simulate_launch_failure: bool = False,
) -> None:
    source = source.resolve()
    target = target.resolve()
    executable = source / executable_name
    if not source.is_dir() or not executable.is_file():
        raise RuntimeError("更新源目录不完整")
    target.parent.mkdir(parents=True, exist_ok=True)
    incoming = target.parent / f".{target.name}.incoming-{uuid.uuid4().hex}"
    backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
    swapped = False
    try:
        shutil.copytree(source, incoming)
        if target.exists():
            target.rename(backup)
        incoming.rename(target)
        swapped = True
        if simulate_launch_failure:
            raise RuntimeError("simulated launch failure")
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(
            [str(target / executable_name)],
            close_fds=True,
            creationflags=creationflags,
        )
    except Exception:
        if swapped and target.exists():
            shutil.rmtree(target, ignore_errors=True)
        if backup.exists() and not target.exists():
            backup.rename(target)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        if incoming.exists():
            shutil.rmtree(incoming, ignore_errors=True)


def write_error_log(exc: BaseException) -> None:
    log = Path(tempfile.gettempdir()) / "QuickVideoEditor-update-error.log"
    try:
        log.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--simulate-launch-failure", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        wait_for_process(args.wait_pid)
        install_update(args.source, args.target, args.exe, args.simulate_launch_failure)
        return 0
    except Exception as exc:
        write_error_log(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
