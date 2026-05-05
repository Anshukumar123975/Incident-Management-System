"""
IMS Failure Simulation Script
==============================
Simulates a realistic incident cascade:

Act 1: RDBMS outage  — 150 signals -> 1 P0 Work Item
Act 2: MCP failure   —  80 signals -> 1 P1 Work Item
Act 3: Summary report

Usage:
    python scripts/simulate_failure.py
    python scripts/simulate_failure.py --host http://localhost:8000
"""

import asyncio
import aiohttp
import argparse
import time
from datetime import datetime

DEFAULT_HOST    = "http://localhost:8000"
DEFAULT_API_KEY = "dev-api-key-change-in-production"

RDBMS_SIGNALS = [
    {"component_id": "RDBMS_PRIMARY", "component_type": "RDBMS",
     "error_code": "CONNECTION_POOL_EXHAUSTED",
     "message": "All 100 connections in pool are in use"},
    {"component_id": "RDBMS_PRIMARY", "component_type": "RDBMS",
     "error_code": "QUERY_TIMEOUT",
     "message": "Query exceeded 30s timeout threshold"},
    {"component_id": "RDBMS_PRIMARY", "component_type": "RDBMS",
     "error_code": "REPLICATION_LAG",
     "message": "Replication lag exceeded 60 seconds"},
    {"component_id": "RDBMS_PRIMARY", "component_type": "RDBMS",
     "error_code": "DISK_IO_SATURATION",
     "message": "Disk I/O wait exceeded 95 percent"},
]

MCP_SIGNALS = [
    {"component_id": "MCP_HOST_01", "component_type": "MCP_HOST",
     "error_code": "HEALTH_CHECK_FAILED",
     "message": "MCP host health check returned 503"},
    {"component_id": "MCP_HOST_01", "component_type": "MCP_HOST",
     "error_code": "PROCESSING_QUEUE_FULL",
     "message": "MCP processing queue depth exceeded threshold"},
    {"component_id": "MCP_HOST_01", "component_type": "MCP_HOST",
     "error_code": "MEMORY_PRESSURE",
     "message": "MCP host memory usage at 94 percent"},
]


async def send_signal(session, host, api_key, signal_data):
    headers = {"Content-Type": "application/json", "X-API-Key": api_key}
    try:
        async with session.post(
            f"{host}/signals", json=signal_data, headers=headers,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            return resp.status == 202
    except Exception:
        return False


async def send_burst(session, host, api_key, signals_pool, count, label, delay_ms=50):
    print(f"\n  Sending {count} signals for {label}...")
    sent = 0
    start = time.time()

    for i in range(count):
        signal = signals_pool[i % len(signals_pool)]
        if await send_signal(session, host, api_key, signal):
            sent += 1
        if (i + 1) % 25 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  -> {i+1}/{count} sent | {rate:.0f} signals/sec")
        await asyncio.sleep(delay_ms / 1000)

    elapsed = time.time() - start
    print(f"  Done: {sent}/{count} sent in {elapsed:.1f}s ({sent/elapsed:.0f}/sec)")
    return sent


async def get_incidents(session, host):
    try:
        async with session.get(f"{host}/incidents") as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception:
        pass
    return {"items": [], "total": 0}


async def get_metrics(session, host):
    try:
        async with session.get(f"{host}/metrics") as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception:
        pass
    return ""


def parse_metric(text, name):
    for line in text.splitlines():
        if line.startswith(name + " "):
            try:
                return float(line.split(" ")[1])
            except Exception:
                pass
    return 0


async def run_simulation(host, api_key):
    print("=" * 60)
    print("  IMS FAILURE SIMULATION")
    print("=" * 60)
    print(f"  Target: {host}")
    print(f"  Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:

        # Verify connectivity
        print("\n[0] Verifying IMS connectivity...")
        try:
            async with session.get(f"{host}/health") as resp:
                if resp.status != 200:
                    print(f"  Health check failed: HTTP {resp.status}")
                    return
                health = await resp.json()
                print(f"  IMS healthy: postgres={health['postgres']} "
                      f"mongo={health['mongo']} redis={health['redis']}")
        except Exception as e:
            print(f"  Cannot reach IMS at {host}: {e}")
            print("  Make sure: docker compose up -d")
            return

        # Act 1: RDBMS Outage
        print("\n" + "-" * 60)
        print("[ACT 1] RDBMS PRIMARY OUTAGE")
        print("-" * 60)
        print("  Scenario: Primary DB connection pool exhausted")
        print("  Expected: 1 x P0 Work Item (debouncer collapses 150 signals)")

        await send_burst(session, host, api_key, RDBMS_SIGNALS, 150, "RDBMS_PRIMARY")

        print("\n  Waiting 3s for workers to process...")
        await asyncio.sleep(3)

        incidents = await get_incidents(session, host)
        rdbms_items = [i for i in incidents["items"] if i["component_id"] == "RDBMS_PRIMARY"]

        if rdbms_items:
            wi = rdbms_items[0]
            print(f"\n  Work Item created:")
            print(f"    ID:           {wi['id']}")
            print(f"    Severity:     {wi['severity']} (expected P0)")
            print(f"    Status:       {wi['status']}")
            print(f"    Signals:      {wi['signal_count']} linked")
        else:
            print("\n  No Work Item found for RDBMS_PRIMARY")

        # Pause between acts
        print(f"\n  Pausing 3s before Act 2...")
        await asyncio.sleep(3)

        # Act 2: MCP Host Failure
        print("\n" + "-" * 60)
        print("[ACT 2] MCP HOST FAILURE")
        print("-" * 60)
        print("  Scenario: MCP_HOST_01 health checks failing")
        print("  Expected: 1 x P1 Work Item (debouncer collapses 80 signals)")

        await send_burst(session, host, api_key, MCP_SIGNALS, 80, "MCP_HOST_01")

        print("\n  Waiting 3s for workers to process...")
        await asyncio.sleep(3)

        incidents = await get_incidents(session, host)
        mcp_items = [i for i in incidents["items"] if i["component_id"] == "MCP_HOST_01"]

        if mcp_items:
            wi = mcp_items[0]
            print(f"\n  Work Item created:")
            print(f"    ID:           {wi['id']}")
            print(f"    Severity:     {wi['severity']} (expected P1)")
            print(f"    Status:       {wi['status']}")
            print(f"    Signals:      {wi['signal_count']} linked")
        else:
            print("\n  No Work Item found for MCP_HOST_01")

        # Summary
        print("\n" + "=" * 60)
        print("[SUMMARY]")
        print("=" * 60)

        metrics_text    = await get_metrics(session, host)
        total_ingested  = int(parse_metric(metrics_text, "ims_signals_ingested_total"))
        total_dropped   = int(parse_metric(metrics_text, "ims_signals_dropped_total"))
        incidents       = await get_incidents(session, host)
        all_items       = incidents["items"]
        p0_count        = sum(1 for i in all_items if i["severity"] == "P0")
        p1_count        = sum(1 for i in all_items if i["severity"] == "P1")

        print(f"\n  Signals sent:       230  (150 RDBMS + 80 MCP)")
        print(f"  Signals ingested:   {total_ingested}")
        print(f"  Signals dropped:    {total_dropped}")
        print(f"  Work Items created: {len(all_items)}")
        print(f"    P0 (Critical):    {p0_count}")
        print(f"    P1 (High):        {p1_count}")
        print(f"\n  Debounce efficiency: {total_ingested - len(all_items)} duplicate pages suppressed")
        print(f"\n  Open http://localhost to see incidents in the dashboard.")
        print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMS Failure Simulation")
    parser.add_argument("--host",    default=DEFAULT_HOST)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    args = parser.parse_args()
    asyncio.run(run_simulation(args.host, args.api_key))