from __future__ import annotations

import argparse
import json
from pathlib import Path

from local_dashboard_server import FUND_RETURN_CODE_BY_NAME, load_fund_return_series


def main() -> None:
    parser = argparse.ArgumentParser(description="Export fund and benchmark return series for the hosted dashboard.")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("fund_return_series.json"))
    args = parser.parse_args()

    payload = {}
    errors = {}
    for fund_name in FUND_RETURN_CODE_BY_NAME:
        try:
            payload[fund_name] = load_fund_return_series(fund_name)
        except Exception as exc:  # Keep one unavailable fund from blocking the full dashboard deploy.
            errors[fund_name] = str(exc)

    if not payload:
        raise RuntimeError(f"No fund return series could be exported: {errors}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"funds": payload, "errors": errors}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"exported {len(payload)} fund return series -> {args.output}")
    if errors:
        print(f"unavailable funds: {json.dumps(errors, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
