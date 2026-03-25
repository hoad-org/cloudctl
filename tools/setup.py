#!/usr/bin/env python3
"""
🛠️ Toolchain Vendor
Installs 'awsdac' via Go.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

# Use latest to ensure we get a valid version
AWSDAC_VERSION = "latest"
ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = ROOT / "tools" / "bin"
AWSDAC_BIN = BIN_DIR / "awsdac"


def install_awsdac():
    BIN_DIR.mkdir(parents=True, exist_ok=True)

    if AWSDAC_BIN.exists():
        print(f"✅ awsdac is present at {AWSDAC_BIN}")
        return

    print(f"⬇️  Installing awsdac @{AWSDAC_VERSION} via Go...")

    if not shutil.which("go"):
        print("❌ Error: 'go' is required.")
        sys.exit(1)

    env = os.environ.copy()
    env["GOBIN"] = str(BIN_DIR)

    try:
        # Install latest
        cmd = [
            "go",
            "install",
            f"github.com/awslabs/diagram-as-code/cmd/awsdac@{AWSDAC_VERSION}",
        ]
        subprocess.run(cmd, check=True, env=env)
        print("✅ awsdac installed successfully.")

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install awsdac: {e}")
        sys.exit(1)


if __name__ == "__main__":
    install_awsdac()
