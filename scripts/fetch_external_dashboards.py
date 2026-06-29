"""Fetch the latest standalone fund and ETF dashboards for Pages deployment."""

from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

ASSETS = {
    "fund/index.html": os.getenv(
        "FUND_DASHBOARD_URL",
        "https://raw.githubusercontent.com/hyunsu6297/fund_returns_daily/main/docs/index.html",
    ),
    "etf/index.html": os.getenv(
        "ETF_DASHBOARD_URL",
        "https://raw.githubusercontent.com/hyunsu6297/active_etf_analysis/main/index.html",
    ),
    "etf/plotly-2.35.2.min.js": os.getenv(
        "ETF_PLOTLY_URL",
        "https://raw.githubusercontent.com/hyunsu6297/active_etf_analysis/main/plotly-2.35.2.min.js",
    ),
}


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "multi-dashboard-build/1.0"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                content = response.read()
            if len(content) < 1_000:
                raise RuntimeError(f"Downloaded asset is unexpectedly small: {url}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            print(f"fetched {url} -> {target.relative_to(DIST)} ({len(content):,} bytes)")
            return
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Unable to fetch {url}") from last_error


def main() -> None:
    if not DIST.is_dir():
        raise FileNotFoundError("dist does not exist; run scripts/assemble_site.py first")
    for relative_path, url in ASSETS.items():
        download(url, DIST / "pages" / relative_path)


if __name__ == "__main__":
    main()

