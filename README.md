# Python-Cleaner

A Windows cleaner with no external dependencies.

## Usage

```powershell
py cleanup.py            # same as --Safe
py cleanup.py --Safe
py cleanup.py --Full
```

The script automatically requests administrator privileges (via a UAC prompt)
if it isn't already running as administrator.

> ⚠️ **No confirmation prompt is shown before deletion.** Files matching the
> targets below (including the Recycle Bin, which is always emptied in both
> modes) are removed immediately once the script runs. Review the "What gets
> cleaned" section before running it.

Arguments are case-sensitive: only `--Safe` and `--Full` (or no argument) are
accepted. Anything else, including different casing like `--full`, prints a
usage message and exits without cleaning.

## Requirements

- Windows (uses `ctypes.windll`, PowerShell, and `sc`/`net` commands - won't
  run on other platforms)
- Python 3.10+ (uses `from __future__ import annotations` and `X | None`
  union syntax)

## What gets cleaned

### `--Safe` mode (default)
- User and system temp files (`%TEMP%`, `%LOCALAPPDATA%\Temp`, `C:\Windows\Temp`, `ProgramData\Temp`)
- Windows Error Reporting (WER) files and Windows Update Medic logs
- For each user profile: temp files, crash dumps, Internet cache, Chrome caches
  (Cache, Code Cache, GPUCache), Edge cache, Discord and Slack caches (Cache, Code Cache,
  GPUCache, logs), Epic Games Launcher logs, Battle.net cache, Ubisoft Game Launcher cache,
  and Firefox caches (cache2, startupCache) for every detected profile
- Recycle Bin (always emptied)

### `--Full` mode
Includes everything above, plus:
- Windows Update download files and Delivery Optimization cache
  (the BITS/wuauserv services are stopped and then restarted for the duration)
- CBS and DISM logs
- LiveKernel reports and Windows minidumps
- The `MEMORY.DMP` file (full memory dump), if present

  > ⚠️ This is a **full system memory dump**, typically generated after a
  > crash (BSOD) for post-mortem debugging. If you or your IT/support team
  > might need to diagnose a recent crash, back this file up before running
  > `--Full`, since deleting it removes that diagnostic data permanently.

## Notes

- Closing browsers and applications before running the script allows more files to be
  removed (files currently in use are skipped, not forced).
- A summary (files removed, space freed, items skipped, elapsed time) is printed at the end.
