#!/usr/bin/env python3
"""Install Feiyue Hermes bridge assets from this repo into the local Hermes home.

This is intentionally small and dependency-free so it works on Windows, macOS,
and Linux. It lets multiple Hermes instances share the same Feiyue bridge script
and skill through the Feiyue GitHub repo while keeping secrets and local session
state out of Git.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
from pathlib import Path


def default_hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser()
    if platform.system().lower().startswith("win"):
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "hermes"
        return Path.home() / "AppData" / "Local" / "hermes"
    return Path.home() / ".hermes"


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Feiyue bridge assets into local Hermes home")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]), help="Feiyue repo root")
    parser.add_argument("--hermes-home", default=str(default_hermes_home()), help="Hermes home to install into")
    parser.add_argument("--install-skill", action="store_true", help="Install hermes-assets/skills/devops/feiyue-bridge")
    parser.add_argument("--install-bridge", action="store_true", help="Install tools/hermes-bridge/feiyue-bridge.py")
    parser.add_argument("--all", action="store_true", help="Install skill and bridge")
    args = parser.parse_args()

    repo = Path(args.repo_root).expanduser().resolve()
    home = Path(args.hermes_home).expanduser().resolve()
    install_skill = args.install_skill or args.all
    install_bridge = args.install_bridge or args.all
    if not install_skill and not install_bridge:
        install_skill = install_bridge = True

    installed: list[str] = []

    if install_bridge:
        src = repo / "tools" / "hermes-bridge" / "feiyue-bridge.py"
        dst = home / "scripts" / "feiyue-bridge.py"
        copy_file(src, dst)
        installed.append(str(dst))

    if install_skill:
        src = repo / "hermes-assets" / "skills" / "devops" / "feiyue-bridge"
        dst = home / "skills" / "devops" / "feiyue-bridge"
        copy_tree(src, dst)
        installed.append(str(dst))

    print("Installed Feiyue Hermes assets:")
    for path in installed:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
