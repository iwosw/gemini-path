"""Optional, reversible Antigravity x64 client-gate experiment.

Only the language server executable is supported. No network settings or
credentials are changed. A server-side denial remains a server-side denial.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile


# Signature adapted from the independently published research at
# https://github.com/vezlin1/antigravity-bypass-russia/blob/main/src/core/opcodes.rs
STOCK = re.compile(rb"\x80\x78\x08\x00\x74.\x48\x8b.\x24.\x48\x89.\x60", re.S)
PATCHED = re.compile(rb"\xc6\x40\x08\x01\x90\x90\x48\x8b.\x24.\x48\x89.\x60", re.S)
REPLACEMENT = b"\xc6\x40\x08\x01\x90\x90"


def default_target():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise ValueError("LOCALAPPDATA is not set; supply --target")
    return Path(base) / "Programs" / "Antigravity" / "resources" / "bin" / "language_server.exe"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def text_section(data):
    """Return raw .text bounds for a valid x64 PE image, refusing ambiguity."""
    if len(data) < 0x100 or data[:2] != b"MZ":
        raise ValueError("not a PE executable")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe > len(data) - 24 or data[pe:pe + 4] != b"PE\x00\x00":
        raise ValueError("invalid PE header")
    machine, count = struct.unpack_from("<HH", data, pe + 4)
    if machine != 0x8664 or not 1 <= count <= 96:
        raise ValueError("only x64 PE executables are supported")
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    sections = pe + 24 + optional_size
    if sections > len(data) or count * 40 > len(data) - sections:
        raise ValueError("invalid section table")
    matches = []
    for i in range(count):
        off = sections + 40 * i
        name = data[off:off + 8].split(b"\0", 1)[0]
        size, start = struct.unpack_from("<II", data, off + 16)
        if name == b".text":
            if not size or start > len(data) or size > len(data) - start:
                raise ValueError("invalid .text section")
            matches.append((start, start + size))
    if len(matches) != 1:
        raise ValueError("expected exactly one .text section")
    return matches[0]


def inspect(data):
    start, end = text_section(data)
    stock = [start + m.start() for m in STOCK.finditer(data[start:end])]
    patched = [start + m.start() for m in PATCHED.finditer(data[start:end])]
    if len(stock) + len(patched) != 1:
        raise ValueError("unknown or ambiguous binary signature; no changes made")
    return ("stock", stock[0]) if stock else ("patched", patched[0])


def app_running():
    if os.name != "nt":
        return False
    for name in ("Antigravity.exe", "language_server.exe"):
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=True,
        )
        if f'"{name}"' in result.stdout:
            return True
    return False


def replace_bytes(target, data):
    """Write a sibling temp file, then replace the old file in one filesystem step."""
    fd, temp = tempfile.mkstemp(prefix=".geminipath-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        shutil.copymode(target, temp)
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def save_json(path, data):
    fd, temp = tempfile.mkstemp(prefix=".manifest-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def patch_file(target, state_dir):
    if target.name.lower() != "language_server.exe":
        raise ValueError("only language_server.exe may be patched")
    state_dir.mkdir(parents=True, exist_ok=True)
    manifest = state_dir / "antigravity.json"
    if manifest.exists():
        raise ValueError("a patch record already exists; restore before patching again")
    if app_running():
        raise ValueError("close Antigravity and its language server first")
    original = target.read_bytes()
    state, offset = inspect(original)
    if state != "stock":
        raise ValueError("the executable is already modified; refusing to overwrite")
    modified = bytearray(original)
    modified[offset:offset + len(REPLACEMENT)] = REPLACEMENT
    modified = bytes(modified)
    if inspect(modified) != ("patched", offset):
        raise ValueError("patched image failed self-check")
    backup = state_dir / (sha256(original) + ".bin")
    if backup.exists() and sha256(backup.read_bytes()) != sha256(original):
        raise ValueError("backup hash mismatch")
    if not backup.exists():
        with backup.open("xb") as output:
            output.write(original)
            output.flush()
            os.fsync(output.fileno())
    record = {
        "target": str(target.resolve()), "backup": str(backup.resolve()),
        "original_sha256": sha256(original), "patched_sha256": sha256(modified),
        "offset": offset,
    }
    # Record recovery metadata first, so an interruption after replacement
    # cannot leave an untracked modified executable.
    save_json(manifest, record)
    try:
        replace_bytes(target, modified)
    except Exception:
        if sha256(target.read_bytes()) == record["original_sha256"]:
            manifest.unlink()
        raise
    return record


def restore_file(target, state_dir):
    manifest = state_dir / "antigravity.json"
    if not manifest.is_file():
        raise ValueError("no patch record found")
    record = json.loads(manifest.read_text(encoding="utf-8"))
    if str(target.resolve()) != record["target"]:
        raise ValueError("patch record belongs to a different executable")
    if app_running():
        raise ValueError("close Antigravity and its language server first")
    backup = Path(record["backup"])
    if backup.parent.resolve() != state_dir.resolve():
        raise ValueError("backup path is outside the patch directory")
    original = backup.read_bytes()
    if sha256(original) != record["original_sha256"]:
        raise ValueError("backup hash mismatch; original file not changed")
    current = target.read_bytes()
    if sha256(current) == record["original_sha256"]:
        manifest.unlink()
        return "already restored"
    if sha256(current) != record["patched_sha256"]:
        try:
            state, _ = inspect(current)
        except ValueError:
            state = "unknown"
        if state == "stock":
            manifest.unlink()
            return "the app updated itself; current stock executable kept unchanged"
        raise ValueError("app was updated or edited; refusing to overwrite its current version")
    replace_bytes(target, original)
    manifest.unlink()
    return "restored"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("scan", "patch", "restore"))
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    target = args.target or default_target()
    if not target.is_file():
        parser.error(f"executable not found: {target}")
    state_dir = Path(__file__).resolve().parent / "vendor" / "patches"
    try:
        if args.action == "scan":
            data = target.read_bytes()
            state, offset = inspect(data)
            print(f"{state}: unique x64 client gate at offset {offset}; sha256={sha256(data)}")
        elif args.action == "patch":
            record = patch_file(target, state_dir)
            print(f"Patched {target}; original SHA-256 {record['original_sha256']}; backup: {record['backup']}")
            print("Client-side experiment only: Google can still reject requests on its servers.")
        else:
            print(restore_file(target, state_dir))
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
