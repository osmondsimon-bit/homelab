#!/usr/bin/env python3
"""Package the reviewed static bubblewrap security backport; requires dpkg-deb and verified artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

BINARY_SHA256 = "711ac2c00998eede367c2b3827efa36ba4436dfce19ab9d3b6d56ff5a5996fa1"
SOURCE_SHA256 = "0e85c8702248b8dd64144f594147553650cdd0e4c951690345faace79c217c4d"
VENDOR_SYSCTL_SHA256 = "7f34e797bf48d7273c1145ef2d0031f481dfe242c34d48b5f99d49fe3dd359b9"
MUSL_NOTICE_SHA256 = "f9bc4423732350eb0b3f7ed7e91d530298476f8fec0c6c427a1c04ade22655af"
LIBCAP_NOTICE_SHA256 = "68467e731f4744bd6e0bb69e8df9c3a994e09cd6b203d0c41327ac6d079c581d"
VERSION = "0.13.1-0homelab1"


def verified(path, expected):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Artifact must be a regular non-symlink file")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Artifact does not match the reviewed SHA-256")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--musl-notice", type=Path, required=True)
    parser.add_argument("--libcap-notice", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = verified(args.binary, BINARY_SHA256)
    source = verified(args.source, SOURCE_SHA256)
    musl_notice = verified(args.musl_notice, MUSL_NOTICE_SHA256)
    libcap_notice = verified(args.libcap_notice, LIBCAP_NOTICE_SHA256)
    # Keep the existing Noble package's namespace policy across package replacement.
    vendor_sysctl = verified(Path("/usr/lib/sysctl.d/50-bubblewrap.conf"), VENDOR_SYSCTL_SHA256)
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refuse to overwrite an existing output")
    if not shutil.which("dpkg-deb"):
        raise ValueError("dpkg-deb is required")
    with tarfile.open(args.source, "r:xz") as archive:
        member = archive.getmember("bubblewrap-0.13.1/COPYING")
        if not member.isfile():
            raise ValueError("Upstream license must be a regular file")
        license_text = archive.extractfile(member).read()
    print("Build the reviewed bubblewrap 0.13.1 security backport; no installation or service action")
    with tempfile.TemporaryDirectory(prefix="bubblewrap-backport-") as directory:
        root = Path(directory) / "package"
        control = root / "DEBIAN"
        doc = root / "usr/share/doc/bubblewrap"
        executable = root / "usr/bin/bwrap"
        for path in [control, doc, executable.parent]:
            path.mkdir(parents=True, exist_ok=True)
        executable.write_bytes(binary)
        executable.chmod(0o755)
        policy = root / "usr/lib/sysctl.d/50-bubblewrap.conf"
        policy.parent.mkdir(parents=True)
        policy.write_bytes(vendor_sysctl)
        for relative in ["usr/share/man/man1/bwrap.1.gz",
                         "usr/share/bash-completion/completions/bwrap",
                         "usr/share/zsh/vendor-completions/_bwrap"]:
            installed = Path("/") / relative
            if installed.is_file() and not installed.is_symlink():
                retained = root / relative
                retained.parent.mkdir(parents=True, exist_ok=True)
                retained.write_bytes(installed.read_bytes())
        (doc / "bubblewrap-0.13.1.tar.xz").write_bytes(source)
        (doc / "COPYING").write_bytes(license_text)
        (doc / "musl-COPYRIGHT").write_bytes(musl_notice)
        (doc / "libcap-LICENSE").write_bytes(libcap_notice)
        (doc / "copyright").write_text(
            "Source: https://github.com/containers/bubblewrap/releases/tag/v0.13.1\n"
            "License: LGPL-2.1-or-later; see COPYING and the included corresponding source.\n"
            "Static dependencies: musl (MIT), libcap (BSD-3-Clause OR GPL-2.0-only).\n"
            "Full dependency notices: musl-COPYRIGHT and libcap-LICENSE in this directory.\n"
            "Build provenance and dependency licenses: homelab/apps/codex-messaging/runtime-revision-research.md\n"
            "This package reuses the reviewed unmodified static artifact; it is not an Ubuntu vendor release.\n"
        )
        (doc / "homelab-provenance.json").write_text(json.dumps({
            "version": VERSION, "upstream_version": "0.13.1",
            "binary_sha256": BINARY_SHA256, "source_sha256": SOURCE_SHA256,
            "preserved_vendor_sysctl_sha256": VENDOR_SYSCTL_SHA256,
            "target": "x86_64-linux-musl", "setuid": False,
            "build": "Zig 0.17.1; Meson 1.12.1; Ninja 1.13.2; libcap-static 2.78-r0",
        }, indent=2) + "\n")
        (control / "control").write_text(
            "Package: bubblewrap\nVersion: " + VERSION + "\nArchitecture: amd64\n"
            "Section: admin\nPriority: optional\nMaintainer: Homelab operator <root@localhost>\n"
            "Homepage: https://github.com/containers/bubblewrap\n"
            "Description: Reviewed static bubblewrap security backport for the homelab\n"
            " Fix CVE-2026-87766 using upstream 0.13.1; retain normal system bwrap usage.\n"
        )
        for path in root.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
            elif path != executable:
                path.chmod(0o644)
        # Normalize ownership inside the archive without requiring root to build it.
        env = os.environ.copy()
        env["SOURCE_DATE_EPOCH"] = "1791979200"
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(root), str(args.output.resolve())],
                       check=True, env=env, stdout=subprocess.DEVNULL)
    print(json.dumps({"package": str(args.output), "version": VERSION,
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, tarfile.TarError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
