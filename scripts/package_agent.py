#!/usr/bin/env python3
"""
Build the AgentCore Runtime deployment package: dist/agent.zip.

AgentCore Runtime direct-code deployment runs a zip on managed arm64 Linux
compute with a specific Python version. That is almost certainly not the
machine you build on (x86 Windows, a CI runner), so this script asks pip
for the *arm64 manylinux wheels* of every dependency instead of the wheels
for the local machine.

Zip layout (the entry point is `app.py` at the zip root):

    app.py agent.py refund_logic.py emit_metric.py gateway_names.py
    identity/verify_customer_token.py
    <every dependency, installed flat>

Usage:

    python3 scripts/package_agent.py                 # -> dist/agent.zip
    python3 scripts/package_agent.py --python-version 3.13

The result is deterministic enough to diff, and well under the Runtime's
250 MB zipped / 750 MB unzipped limits for this dependency set.
"""

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "agent"
OUT = ROOT / "dist" / "agent.zip"

# Source files that go in the zip. Setup scripts (create_guardrail.py,
# model_call_test.py, setup_refund_approvals_table.py) are deliberately left
# out: they are one-time tools, not part of the running agent.
AGENT_FILES = ["app.py", "agent.py", "refund_logic.py", "emit_metric.py", "gateway_names.py"]
IDENTITY_FILES = ["verify_customer_token.py"]

# manylinux2014 covers most wheels; manylinux_2_28 covers newer ones that no
# longer publish a 2014 build. Both run on AgentCore's Linux image.
PLATFORMS = ["manylinux2014_aarch64", "manylinux_2_28_aarch64"]


def install_dependencies(python_version: str) -> None:
    command = [
        sys.executable, "-m", "pip", "install",
        "--quiet", "--no-compile", "--upgrade",
        "--target", str(BUILD),
        "--implementation", "cp",
        "--python-version", python_version,
        "--only-binary=:all:",
        "-r", str(ROOT / "requirements-runtime.txt"),
    ]
    for platform in PLATFORMS:
        command += ["--platform", platform]
    print("Installing arm64 dependencies:", " ".join(command[3:8]), "...")
    subprocess.run(command, check=True)


def copy_sources() -> None:
    for name in AGENT_FILES:
        shutil.copy2(ROOT / "agent" / name, BUILD / name)
    (BUILD / "identity").mkdir(exist_ok=True)
    (BUILD / "identity" / "__init__.py").write_text("")
    for name in IDENTITY_FILES:
        shutil.copy2(ROOT / "identity" / name, BUILD / "identity" / name)


def make_zip() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(BUILD.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(BUILD).as_posix())
    size_mb = OUT.stat().st_size / (1024 * 1024)
    print(f"Wrote {OUT.relative_to(ROOT)} ({size_mb:.1f} MB)")
    if size_mb > 250:
        raise SystemExit("Zip exceeds the 250 MB Runtime limit.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--python-version", default="3.13", help="must match the Runtime's PYTHON_3_x setting")
    args = parser.parse_args()

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)

    install_dependencies(args.python_version)
    copy_sources()
    make_zip()


if __name__ == "__main__":
    main()
