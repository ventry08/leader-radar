#!/usr/bin/env python3
"""leader-radar - which validator client is holding the ledger right now.

Solana's leader schedule is public for the whole epoch. Each leader runs one of
several validator clients, and those clients order transactions by rules that have
nothing in common with each other: some sort by a computed rank, some run batch
auctions where arrival picks your batch, some re-sort a 50ms buffer purely by fee.

So "how much should I pay for speed" has no single answer. It depends on who holds
the ledger in that exact second - and that is knowable in advance.

This prints it.

    python3 leader_radar.py                 # now + next 2 minutes
    python3 leader_radar.py --minutes 10    # next 10 minutes
    python3 leader_radar.py --stats         # how the epoch splits by client
    python3 leader_radar.py --rpc <url>     # your own endpoint

No dependencies, no API key. The public endpoint is heavily rate limited; for
anything repeated, pass your own with --rpc.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

DEFAULT_RPC = "https://api.mainnet-beta.solana.com"
SLOT_MS = 400  # nominal; real slots drift a little

# What each client does with your transaction once it has the ledger.
# Timings are medians measured Sep-Oct 2026 from nodes in Frankfurt and Amsterdam,
# for the fastest wallets on honest pump.fun launches. Your mileage will differ.
CLIENTS = {
    "AgaveBam": ("BAM", "batch auction, 10-50ms: arrival picks the batch, fee orders it", "17-22 ms"),
    "FireBAM": ("BAM", "batch auction, 10-50ms: arrival picks the batch, fee orders it", "17-22 ms"),
    "Firedancer": ("FD", "packs by compute price, tips ignored entirely", "16-24 ms"),
    "Frankendancer": ("FD", "packs by compute price, tips ignored entirely", "187-800 ms"),
    "JitoLabs": ("Jito", "rank formula + block engine auction every 50ms", "25-28 ms"),
    "HarmonicAgave": ("Harmonic", "two 50ms buffers: arrival order ignored inside, fee decides", "~137 ms"),
    "HarmonicFiredancer": ("Harmonic", "two 50ms buffers: arrival order ignored inside, fee decides", "~137 ms"),
    "Agave": ("Agave", "rank = (priority + 2500) * 1e6 / (1 + cost)", "25-40 ms"),
    "Rakurai": ("Rakurai", "not measured", "?"),
    "Raiku": ("Raiku", "not measured", "?"),
}


def rpc(url: str, method: str, params=None, retries: int = 3):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params or []}).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                payload = json.load(r)
            if "error" in payload:
                raise RuntimeError(payload["error"].get("message", payload["error"]))
            return payload.get("result")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:            # public endpoint throttles hard
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{method} failed after {retries} tries: {last}")


def load(url: str):
    """Current position in the epoch, the schedule, and who runs what."""
    info = rpc(url, "getEpochInfo")
    schedule = rpc(url, "getLeaderSchedule", [None, {"commitment": "finalized"}])
    nodes = rpc(url, "getClusterNodes")
    if not schedule:
        raise RuntimeError("this endpoint returned no leader schedule")

    client_of = {n["pubkey"]: (n.get("clientId") or "Unknown") for n in nodes}

    # schedule: {validator_pubkey: [slot_index, ...]} -> flat lookup
    leader_at = {}
    for pubkey, slots in schedule.items():
        for s in slots:
            leader_at[s] = pubkey
    return info, leader_at, client_of


def describe(client: str):
    fam, how, landing = CLIENTS.get(client, (client, "unknown behaviour", "?"))
    return fam, how, landing


def upcoming(info, leader_at, client_of, minutes: int):
    here = info["slotIndex"]
    span = int(minutes * 60 * 1000 / SLOT_MS)
    out = []
    for s in range(here, min(here + span, info["slotsInEpoch"])):
        pk = leader_at.get(s)
        if pk is None:
            continue
        out.append((s, pk, client_of.get(pk, "Unknown")))
    return out


def fmt_eta(slots_ahead: int) -> str:
    sec = slots_ahead * SLOT_MS / 1000
    if sec < 1:
        return "now"
    if sec < 60:
        return f"+{sec:4.1f}s"
    return f"+{sec/60:4.1f}m"


def show_now(info, rows):
    if not rows:
        print("no schedule data for the current position in the epoch")
        return
    here = info["slotIndex"]
    slot, pk, client = rows[0]
    fam, how, landing = describe(client)
    print()
    print(f"  holding the ledger   {fam}  ({client})")
    print(f"  how it orders you    {how}")
    print(f"  fastest bots land    {landing}")
    print(f"  epoch {info['epoch']}, slot {here:,} of {info['slotsInEpoch']:,}")
    print()

    # group the stretch ahead into runs of the same family
    runs, prev = [], None
    for s, pk, client in rows:
        fam = describe(client)[0]
        if prev and prev[0] == fam:
            prev[2] = s
        else:
            prev = [fam, s, s]
            runs.append(prev)

    print("  next up")
    for fam, start, end in runs[:14]:
        n = end - start + 1
        print(f"    {fmt_eta(start - here)}  {fam:<10} {n:>3} slots  ({n * SLOT_MS / 1000:.1f}s)")
    print()


def show_stats(info, leader_at, client_of):
    fams = Counter()
    for s, pk in leader_at.items():
        fams[describe(client_of.get(pk, "Unknown"))[0]] += 1
    total = sum(fams.values())
    print()
    print(f"  epoch {info['epoch']}: {total:,} scheduled slots")
    print()
    for fam, n in fams.most_common():
        bar = "#" * int(40 * n / total)
        print(f"    {fam:<12} {100*n/total:5.1f}%  {n:>7,}  {bar}")
    print()
    print("  a slot is ~0.4s, so these are also the odds your next trade")
    print("  lands on each kind of machine")
    print()


def main():
    ap = argparse.ArgumentParser(description="which validator client holds the Solana ledger right now")
    ap.add_argument("--rpc", default=DEFAULT_RPC, help="RPC endpoint (default: public mainnet)")
    ap.add_argument("--minutes", type=int, default=2, help="how far ahead to look")
    ap.add_argument("--stats", action="store_true", help="epoch-wide split by client")
    ap.add_argument("--json", action="store_true", help="machine readable output")
    a = ap.parse_args()

    try:
        info, leader_at, client_of = load(a.rpc)
    except Exception as e:
        print(f"could not read the chain: {e}", file=sys.stderr)
        print("the public endpoint rate limits aggressively - try --rpc with your own",
              file=sys.stderr)
        return 1

    if a.stats:
        show_stats(info, leader_at, client_of)
        return 0

    rows = upcoming(info, leader_at, client_of, a.minutes)

    if a.json:
        print(json.dumps({
            "epoch": info["epoch"],
            "slot_index": info["slotIndex"],
            "now": ({"slot": rows[0][0], "validator": rows[0][1],
                     "client": rows[0][2], "family": describe(rows[0][2])[0]}
                    if rows else None),
            "ahead": [{"slot": s, "validator": pk, "client": c,
                       "family": describe(c)[0]} for s, pk, c in rows],
        }, indent=1))
        return 0

    show_now(info, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
