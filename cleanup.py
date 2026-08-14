from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Result:
    files: int = 0
    freed: int = 0
    skipped: int = 0


RESULT = Result()


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except AttributeError:
        return False


def elevate() -> None:
    arguments = subprocess.list2cmdline([str(Path(__file__).resolve()), *sys.argv[1:]])
    code = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, arguments, None, 1)
    if code <= 32:
        raise RuntimeError("Administrator elevation was denied or failed.")
    raise SystemExit(0)


def path_from_env(variable: str, *parts: str) -> Path | None:
    value = os.environ.get(variable)
    return Path(value, *parts) if value else None


def delete_path(path: Path) -> bool:
    try:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True
    except (OSError, PermissionError):
        RESULT.skipped += 1
        return False


def directory_size(directory: Path) -> tuple[int, int]:
    files = size = 0
    for root, _, names in os.walk(directory, topdown=False, followlinks=False):
        for name in names:
            path = Path(root, name)
            try:
                size += path.stat().st_size
                files += 1
            except OSError:
                pass
    return files, size


def clean_directory(directory: Path | None, label: str) -> None:
    if directory is None or not directory.is_dir() or directory.is_symlink():
        return

    before_files = RESULT.files
    before_freed = RESULT.freed
    try:
        entries = list(os.scandir(directory))
    except OSError:
        RESULT.skipped += 1
        return

    for entry in entries:
        try:
            if entry.is_dir(follow_symlinks=False):
                files, size = directory_size(Path(entry.path))
                if delete_path(Path(entry.path)):
                    RESULT.files += files
                    RESULT.freed += size
            else:
                try:
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    size = 0
                if delete_path(Path(entry.path)):
                    RESULT.files += 1
                    RESULT.freed += size
        except OSError:
            RESULT.skipped += 1

    removed = RESULT.files - before_files
    if removed:
        freed = RESULT.freed - before_freed
        print(f"  OK  {label} ({removed} files, {format_size(freed)})")


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def user_profiles() -> list[Path]:
    users = Path(os.environ.get("SystemDrive", "C:")) / "Users"
    excluded = {"default", "default user", "public", "all users"}
    try:
        return [path for path in users.iterdir() if path.is_dir() and path.name.lower() not in excluded]
    except OSError:
        return []


def safe_targets() -> list[tuple[Path | None, str]]:
    windir = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    targets: list[tuple[Path | None, str]] = [
        (path_from_env("TEMP"), "User temp files"),
        (path_from_env("LOCALAPPDATA", "Temp"), "Local temp files"),
        (windir / "Temp", "Windows temp files"),
        (path_from_env("ProgramData", "Temp"), "Temp ProgramData"),
        (path_from_env("ProgramData", "Microsoft", "Windows", "WER"), "Windows error reports"),
        (windir / "Logs" / "WindowsUpdateMedic", "Windows Update Medic logs"),
    ]
    for user in user_profiles():
        local = user / "AppData" / "Local"
        roaming = user / "AppData" / "Roaming"
        targets.extend([
            (local / "Temp", f"Temp files — {user.name}"),
            (local / "CrashDumps", f"Crash dumps — {user.name}"),
            (local / "Microsoft" / "Windows" / "INetCache", f"Internet cache — {user.name}"),
            (local / "Google" / "Chrome" / "User Data" / "Default" / "Cache", f"Chrome cache — {user.name}"),
            (local / "Google" / "Chrome" / "User Data" / "Default" / "Code Cache", f"Chrome code cache — {user.name}"),
            (local / "Google" / "Chrome" / "User Data" / "Default" / "GPUCache", f"Chrome GPU cache — {user.name}"),
            (local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache", f"Edge cache — {user.name}"),
            (roaming / "discord" / "Cache", f"Discord cache — {user.name}"),
            (roaming / "discord" / "Code Cache", f"Discord code cache — {user.name}"),
            (roaming / "discord" / "GPUCache", f"Discord GPU cache — {user.name}"),
            (roaming / "discord" / "logs", f"Discord logs — {user.name}"),
            (roaming / "Slack" / "Cache", f"Slack cache — {user.name}"),
            (roaming / "Slack" / "Code Cache", f"Slack code cache — {user.name}"),
            (roaming / "Slack" / "GPUCache", f"Slack GPU cache — {user.name}"),
            (roaming / "Slack" / "logs", f"Slack logs — {user.name}"),
            (local / "EpicGamesLauncher" / "Saved" / "Logs", f"Epic Games logs — {user.name}"),
            (local / "Battle.net" / "Cache", f"Battle.net cache — {user.name}"),
            (local / "Ubisoft Game Launcher" / "spool", f"Ubisoft cache — {user.name}"),
        ])
        firefox = local / "Mozilla" / "Firefox" / "Profiles"
        if firefox.is_dir():
            for profile in firefox.glob("*"):
                targets.extend([(profile / "cache2", f"Firefox cache — {user.name}"),
                                (profile / "startupCache", f"Firefox startup cache — {user.name}")])
    return targets


def service_running(name: str) -> bool:
    result = subprocess.run(["sc", "query", name], capture_output=True, text=True, check=False)
    return "RUNNING" in result.stdout


def run_full_cleanup() -> None:
    running = [name for name in ("BITS", "wuauserv") if service_running(name)]
    for name in running:
        subprocess.run(["net", "stop", name], capture_output=True, check=False)
    try:
        windir = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        clean_directory(windir / "SoftwareDistribution" / "Download", "Windows Update downloads")
        clean_directory(windir / "SoftwareDistribution" / "DeliveryOptimization", "Delivery Optimization")
        clean_directory(windir / "Logs" / "CBS", "CBS logs")
        clean_directory(windir / "Logs" / "DISM", "DISM logs")
        clean_directory(windir / "LiveKernelReports", "LiveKernel reports")
        clean_directory(windir / "Minidump", "Windows minidumps")
        memory_dump = windir / "MEMORY.DMP"
        if memory_dump.is_file():
            try:
                size = memory_dump.stat().st_size
            except OSError:
                size = 0
            if delete_path(memory_dump):
                RESULT.files += 1
                RESULT.freed += size
                print(f"  OK  Windows memory dump (1 file, {format_size(size)})")
    finally:
        for name in running:
            subprocess.run(["net", "start", name], capture_output=True, check=False)


def clear_recycle_bin() -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
        capture_output=True,
        check=False,
    )


def parse_mode() -> str:
    args = sys.argv[1:]
    if not args or args == ["--Safe"]:
        return "safe"
    if args == ["--Full"]:
        return "full"
    print("Usage: py cleanup.py [--Safe | --Full]")
    raise SystemExit(2)


def main() -> None:
    mode = parse_mode()
    if not is_admin():
        elevate()

    start = time.monotonic()
    print(f"{'Full' if mode == 'full' else 'Safe'} cleanup in progress...\n")
    for target, label in safe_targets():
        clean_directory(target, label)
    clear_recycle_bin()
    if mode == "full":
        run_full_cleanup()

    elapsed = time.monotonic() - start
    print(f"\nCompleted: {RESULT.files} files removed, {format_size(RESULT.freed)} freed, "
          f"{RESULT.skipped} items skipped ({elapsed:.1f} s).")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()