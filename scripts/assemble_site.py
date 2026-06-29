"""Assemble generated dashboards and the authenticated web shell."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "web", DIST)
    targets = {
        ROOT / "apps" / "stock" / "fund_dashboard.html": DIST / "pages" / "stock" / "index.html",
        ROOT / "apps" / "bond" / "채권형수익증권_대시보드.html": DIST / "pages" / "bond" / "index.html",
    }
    for source, target in targets.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        print(f"copied {source.name} -> {target.relative_to(DIST)}")


if __name__ == "__main__":
    main()

