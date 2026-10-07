"""Outbound-only PC Bloomberg receiver for the hosted global dashboard.

The browser inserts an authenticated Supabase request. This process polls the
existing global request queue, queries Desktop API on this PC, and publishes
the result to global-only Supabase rows. No inbound port is needed.
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone

from bloomberg_local_server import fetch_reference
from publish_kiwoom_market import (
    DEFAULT_SUPABASE_URL, SupabaseRest, complete_request,
    load_market_snapshot, normalize_security_list, publish_market_snapshot,
    publish_quotes, required_env,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def claim_bloomberg_request(client: SupabaseRest) -> dict | None:
    rows = client.get_all("global_market_refresh_requests", {
        "select": "*", "status": "eq.pending", "priority": "gte.30",
        "order": "priority.desc,requested_at.asc", "limit": "1"})
    if not rows:
        return None
    request = rows[0]
    claimed = client.update_rows("global_market_refresh_requests",
                                 {"id": f"eq.{request['id']}", "status": "eq.pending"},
                                 {"status": "processing", "started_at": utc_now(), "error": None})
    return claimed[0] if claimed else None


def process_one(client: SupabaseRest, host: str, port: int) -> bool:
    request = claim_bloomberg_request(client)
    if not request:
        return False
    request_id = request["id"]
    securities = normalize_security_list(request.get("securities"))
    discovery = request.get("request_type") == "batch" and int(request.get("priority") or 0) >= 40
    try:
        if not securities:
            raise ValueError("조회 종목이 없습니다.")
        if len(securities) > 1000:
            raise ValueError("한 번에 조회 가능한 종목은 1,000개입니다.")
        incoming = fetch_reference(securities, host, port, metadata_only=discovery)
        if discovery:
            # ETF metadata is returned to this request only. Browser-side
            # FundEtfDiscovery validates the security type before DB save.
            result = {"securities": incoming.get("securities", {}),
                      "errors": incoming.get("errors", {}),
                      "updatedAt": incoming.get("updatedAt")}
        else:
            existing, created_by = load_market_snapshot(client)
            merged = {**existing, **incoming}
            merged["securities"] = {**(existing.get("securities") or {}),
                                      **(incoming.get("securities") or {})}
            merged["errors"] = {**(existing.get("errors") or {}),
                                  **(incoming.get("errors") or {})}
            for field in ("fx", "fxPrevClose", "fxChange", "fxAt1530", "fxPreviousAt1530",
                          "fxAt1530Date", "fxPreviousAt1530Date"):
                if incoming.get(field) is None and existing.get(field) is not None:
                    merged[field] = existing[field]
            merged["updatedAt"] = utc_now()
            merged["source"] = "bloomberg-pc-receiver"
            publish_market_snapshot(client, merged, request.get("requested_by") or created_by)
            publish_quotes(client, {**incoming, "source": "bloomberg-pc-receiver"})
            result = {"requestedCount": len(securities),
                      "successCount": len(incoming.get("securities") or {}),
                      "failedCount": len(incoming.get("errors") or {}),
                      "asOf": incoming.get("asOf"), "updatedAt": merged["updatedAt"]}
        complete_request(client, request_id, status="done", result=result)
        print(f"{utc_now()} request {request_id} complete: {result.get('successCount', len(result.get('securities', {})))} securities", flush=True)
    except Exception as exc:
        complete_request(client, request_id, status="failed", error=str(exc))
        print(f"{utc_now()} request {request_id} failed: {exc}", flush=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Global dashboard Bloomberg Supabase receiver")
    parser.add_argument("--blp-host", default="localhost")
    parser.add_argument("--blp-port", type=int, default=8194)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    client = SupabaseRest(os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL),
                          required_env("SUPABASE_SERVICE_ROLE_KEY"))
    print("Bloomberg global receiver ready. Keep Terminal logged in and this window open.", flush=True)
    print("Polling Supabase outbound; no inbound web port.", flush=True)
    while True:
        try:
            processed = process_one(client, args.blp_host, args.blp_port)
            if args.once:
                break
            if not processed:
                time.sleep(max(args.poll_seconds, 0.5))
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"{utc_now()} receiver error: {exc}", flush=True)
            if args.once:
                raise
            time.sleep(max(args.poll_seconds, 2.0))


if __name__ == "__main__":
    main()
