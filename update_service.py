from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from packaging.version import InvalidVersion, Version

from version import (
    APP_NAME,
    GITHUB_RELEASES_API,
    MAIN_EXECUTABLE_NAME,
    RELEASE_ASSET_TEMPLATE,
    UPDATE_HELPER_NAME,
)


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag: str
    notes: str
    page_url: str
    package_url: str
    checksum_url: str
    package_name: str


@dataclass(frozen=True)
class PreparedUpdate:
    release: ReleaseInfo
    package_dir: Path


def _version(value: str) -> Version:
    try:
        return Version(value.strip().removeprefix("v"))
    except InvalidVersion as exc:
        raise UpdateError(f"无效版本号：{value}") from exc


def is_newer_version(latest: str, current: str) -> bool:
    return _version(latest) > _version(current)


def fetch_latest_release(
    current_version: str,
    api_url: str = GITHUB_RELEASES_API,
    timeout: float = 10,
) -> ReleaseInfo | None:
    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"QuickVideoEditor/{current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise UpdateError(f"无法连接更新服务器：{exc}") from exc

    tag = str(payload.get("tag_name", "")).strip()
    latest_version = str(_version(tag))
    if not is_newer_version(latest_version, current_version):
        return None

    package_name = RELEASE_ASSET_TEMPLATE.format(version=latest_version)
    checksum_name = f"{package_name}.sha256"
    assets = {
        str(asset.get("name")): str(asset.get("browser_download_url"))
        for asset in payload.get("assets", [])
        if isinstance(asset, dict)
    }
    if not assets.get(package_name) or not assets.get(checksum_name):
        raise UpdateError(
            f"Release {tag} 缺少更新文件：{package_name} 或 {checksum_name}"
        )
    return ReleaseInfo(
        version=latest_version,
        tag=tag,
        notes=str(payload.get("body") or "本版本未提供更新说明。"),
        page_url=str(payload.get("html_url") or ""),
        package_url=assets[package_name],
        checksum_url=assets[checksum_name],
        package_name=package_name,
    )


def download_file(
    url: str,
    destination: Path,
    progress: Callable[[int, int], None] | None = None,
    timeout: float = 30,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "QuickVideoEditor-Updater"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, destination.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                downloaded += len(chunk)
                if progress:
                    progress(downloaded, total)
    except (OSError, urllib.error.URLError) as exc:
        destination.unlink(missing_ok=True)
        raise UpdateError(f"下载更新失败：{exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksum(text: str, expected_filename: str) -> str:
    for line in text.splitlines():
        parts = line.strip().split()
        if parts and len(parts[0]) == 64:
            filename = parts[-1].lstrip("*") if len(parts) > 1 else expected_filename
            if filename == expected_filename:
                try:
                    int(parts[0], 16)
                except ValueError:
                    continue
                return parts[0].lower()
    raise UpdateError("更新校验文件格式无效")


def safe_extract_package(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                path = PurePosixPath(member.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts:
                    raise UpdateError(f"更新包包含不安全路径：{member.filename}")
                resolved = (destination / Path(*path.parts)).resolve()
                if destination.resolve() not in (resolved, *resolved.parents):
                    raise UpdateError(f"更新包路径越界：{member.filename}")
            package.extractall(destination)
    except (OSError, zipfile.BadZipFile) as exc:
        raise UpdateError(f"无法解压更新包：{exc}") from exc

    package_dir = destination / APP_NAME
    if not (package_dir / MAIN_EXECUTABLE_NAME).is_file():
        raise UpdateError(f"更新包中缺少 {APP_NAME}/{MAIN_EXECUTABLE_NAME}")
    if not (package_dir / UPDATE_HELPER_NAME).is_file():
        raise UpdateError(f"更新包中缺少 {APP_NAME}/{UPDATE_HELPER_NAME}")
    return package_dir


def prepare_update(
    release: ReleaseInfo,
    progress: Callable[[int, int], None] | None = None,
    cache_root: Path | None = None,
) -> PreparedUpdate:
    cache_root = cache_root or Path(tempfile.gettempdir()) / "QuickVideoEditor-updates"
    work_dir = cache_root / release.version
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    archive = work_dir / release.package_name
    checksum_file = work_dir / f"{release.package_name}.sha256"
    download_file(release.package_url, archive, progress)
    download_file(release.checksum_url, checksum_file)
    expected = parse_checksum(checksum_file.read_text(encoding="utf-8-sig"), release.package_name)
    actual = sha256_file(archive)
    if actual != expected:
        raise UpdateError(f"更新包校验失败（期望 {expected}，实际 {actual}）")
    package_dir = safe_extract_package(archive, work_dir / "staging")
    return PreparedUpdate(release, package_dir)


def install_prepared_update(prepared: PreparedUpdate) -> None:
    if not getattr(sys, "frozen", False):
        raise UpdateError("开发运行模式不会替换源码目录，请使用打包后的程序测试更新。")
    install_dir = Path(sys.executable).resolve().parent
    helper = install_dir / UPDATE_HELPER_NAME
    if not helper.is_file():
        raise UpdateError(f"找不到独立更新助手：{helper}")
    helper_copy_dir = Path(tempfile.mkdtemp(prefix="QuickVideoEditor-helper-"))
    helper_copy = helper_copy_dir / UPDATE_HELPER_NAME
    shutil.copy2(helper, helper_copy)
    command = [
        str(helper_copy),
        "--wait-pid", str(os.getpid()),
        "--source", str(prepared.package_dir),
        "--target", str(install_dir),
        "--exe", MAIN_EXECUTABLE_NAME,
    ]
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        subprocess.Popen(command, close_fds=True, creationflags=creationflags)
    except OSError as exc:
        raise UpdateError(f"无法启动更新助手：{exc}") from exc
