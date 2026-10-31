#!/usr/bin/env python3
"""What one memecoin buy on pump.fun actually weighs.

Live read from Solana mainnet. No wallet, no keys, nothing signed:
    python3 weigh.py
Behind a proxy:
    PX=http://host:port python3 weigh.py
"""
import base64, json, os, sys, time, urllib.request

RPC = os.environ.get("RPC", "https://api.mainnet-beta.solana.com")
PX = os.environ.get("PX")
if PX:
    urllib.request.install_opener(urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PX, "https": PX})))

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
C = dict(g="\033[92m", r="\033[91m", y="\033[93m", d="\033[90m", w="\033[97m", b="\033[1m", x="\033[0m")

PROGRAMS = [
    ("pump.fun program",          "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"),
    ("Token-2022 program",        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"),
    ("pump.fun fee program",      "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ"),
    ("Token program",             "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
    ("associated token program",  "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"),
]
ACCOUNT_CEILING = 10 * 1024 * 1024   # max size of a Solana account
OTHER_ACCOUNTS = 29                  # the rest of the accounts in the tx, 64 B of header each


def b58encode(raw):
    n = int.from_bytes(raw, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + s


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, data=body, headers={
        "content-type": "application/json", "user-agent": "Mozilla/5.0"})
    t0 = time.time()
    out = json.load(urllib.request.urlopen(req, timeout=30))
    return out, (time.time() - t0) * 1000


def account_size(addr):
    """Account size. For a program, follow it to its programdata - that is where the code lives."""
    res, ms = rpc("getAccountInfo", [addr, {"encoding": "base64"}])
    val = (res.get("result") or {}).get("value")
    if not val:
        return None, ms, None
    raw = base64.b64decode(val["data"][0])
    if len(raw) == 36 and raw[:4] == b"\x02\x00\x00\x00":      # upgradeable loader: a pointer
        pd = b58encode(raw[4:36])
        res2, ms2 = rpc("getAccountInfo", [pd, {"encoding": "base64"}])
        val2 = (res2.get("result") or {}).get("value")
        size = len(base64.b64decode(val2["data"][0])) if val2 else 0
        return size, ms + ms2, pd
    return len(raw), ms, None


def line(s=""):
    print(s, flush=True)


def main():
    line()
    line(f"{C['b']}{C['w']}  WHAT ONE MEMECOIN BUY ACTUALLY WEIGHS{C['x']}")
    line(f"{C['d']}  live query to solana mainnet · no wallet, no keys, nothing signed{C['x']}")
    line(f"{C['d']}  {RPC}{C['x']}")
    line()
    time.sleep(1.2)

    total = 0
    for name, addr in PROGRAMS:
        print(f"  {C['d']}fetching{C['x']}  {name:<26}", end="", flush=True)
        size, ms, pd = account_size(addr)
        if size is None:
            print(f"\r\033[2K  {C['r']}not found{C['x']}  {name}")
            continue
        total += size
        col = C["g"] if size >= ACCOUNT_CEILING else C["w"]
        print(f"\r\033[2K  {col}{size:>12,}{C['x']}  {name:<26}{C['d']}{ms:>6.0f} ms{C['x']}")
        if size >= ACCOUNT_CEILING:
            time.sleep(0.5)
            line(f"  {C['r']}{'':>12}  ^ that is 10,485,760 - the hard ceiling for a solana account.{C['x']}")
            line(f"  {C['r']}{'':>12}    this program cannot grow by a single byte.{C['x']}")
        time.sleep(0.75)

    headers = OTHER_ACCOUNTS * 64
    total += headers
    line(f"  {C['d']}{headers:>12,}  {OTHER_ACCOUNTS} more accounts × 64 B of header{C['x']}")
    time.sleep(1.0)

    line()
    line(f"  {C['b']}{C['y']}{total:>12,} BYTES{C['x']}  {C['w']}move through the network for ONE tap of \"buy\"{C['x']}")
    line(f"  {C['d']}{'':>12}  {total/1048576:.2f} MB · every buy · every person · every time{C['x']}")
    line()
    share = ACCOUNT_CEILING / total * 100
    line(f"  {C['d']}  {share:.0f}% of that is one program sitting flat against the wall.{C['x']}")
    line()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
