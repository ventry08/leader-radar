# leader-radar

**Which validator client is holding the Solana ledger right now, and what that does to your transaction.**

```
  holding the ledger   Jito  (JitoLabs)
  how it orders you    rank formula + block engine auction every 50ms
  fastest bots land    25-28 ms
  epoch 1072, slot 336,248 of 432,000

  next up
    now     Jito         4 slots  (1.6s)
    + 1.6s  Harmonic     4 slots  (1.6s)
    + 3.2s  Jito        12 slots  (4.8s)
    + 8.0s  Harmonic     4 slots  (1.6s)
    +14.4s  BAM          4 slots  (1.6s)
    +20.8s  FD           4 slots  (1.6s)
```

---

## Why this exists

Solana's leader schedule is public for the entire epoch - 432,000 slots, one call, no API key.

Each leader runs one of several validator clients. Those clients order incoming transactions by rules that have **nothing in common** with each other:

| client | how it decides who goes first |
|---|---|
| **BAM** | batch auction, 10-50 ms. Arrival picks your batch, fee orders you inside it |
| **Harmonic** | two 50 ms buffers. Arrival order ignored inside - the tick re-sorts purely by fee |
| **Jito** | rank formula, plus a block engine auction every 50 ms |
| **Firedancer** | packs by compute price. Tips are ignored entirely |
| **Agave** | `rank = (priority + 2500) * 1e6 / (1 + cost)` |

So "how much should I pay for speed" has no single answer.

Beating someone by 10 ms is decisive against one of these and completely irrelevant against another. Paying triple buys you nothing if you missed the batch window.

Which one gets your trade is decided by a schedule that was published two days ago. This prints it.

---

## Install

There is nothing to install.

```bash
curl -O https://raw.githubusercontent.com/ventry08/leader-radar/main/leader_radar.py
python3 leader_radar.py
```

Python 3.8+, standard library only. No dependencies, no key, no account.

---

## Use

```bash
python3 leader_radar.py                  # now and the next 2 minutes
python3 leader_radar.py --minutes 10     # look further ahead
python3 leader_radar.py --stats          # how this epoch splits by client
python3 leader_radar.py --json           # machine readable
python3 leader_radar.py --rpc <your-url> # your own endpoint
python3 weigh.py                         # account data one buy loads + what the default costs
```

`--stats` is the one worth running first:

```
  epoch 1072: 432,000 scheduled slots

    BAM           38.1%  164,452  ###############
    Harmonic      30.3%  131,044  ############
    Jito          24.0%  103,472  #########
    FD             5.4%   23,180  ##
    Rakurai        1.2%    5,184
    Agave          0.9%    4,032
```

Those are also the odds that your next trade lands on each kind of machine.

---

## Also in here: `weigh.py`

How much **account data** one pump.fun buy loads, and what the default limit costs you.

```bash
python3 weigh.py
```

```
  10,485,760  pump.fun program            3572 ms
   1,382,061  Token-2022 program          1725 ms
     948,989  pump.fun fee program        1524 ms
     108,645  Token program               1261 ms
     105,032  associated token program     703 ms
       1,856  29 more accounts x 64 B of header

  13,032,343 BYTES  of account data loaded to run ONE buy
                    loadedAccountsDataSize, NOT network traffic
                    the transaction on the wire is ~1.3 KB

      16,384 CU  if you leave the default 64 MiB allowance
       3,184 CU  if you set the limit to what you actually load
      13,200 CU  you are paying for nothing, straight off your priority
```

**To be precise about what this number is.** It is `loadedAccountsDataSize` - the bytes a validator loads to execute the transaction. It is not bandwidth, and the programs are not shipped over the network per buy. Thanks to [@0xeddiekim](https://x.com/0xeddiekim) for pushing me to say that properly.

It still costs you, which is the point of measuring it. The scheduler prices loaded data **before** execution, at 8 CU per 32 KiB started. Leave the default 64 MiB allowance and you carry 16,384 CU you never use - that inflates your cost estimate and drops your scheduling priority for nothing.

The fix is one instruction, five bytes: `SetLoadedAccountsDataSizeLimit`. Anza documents the same effect [here](https://www.anza.xyz/blog/cu-optimization-with-setloadedaccountsdatasizelimit).

The 10,485,760 is not a round coincidence either. It is the maximum size a Solana account can be, and the program the entire memecoin market runs on is flat against that wall.

---

## About the landing times

The `fastest bots land` numbers are **measurements, not specs**.

Taken September through October 2026 from nodes in Frankfurt and Amsterdam, by cross-referencing the leader schedule against real on-chain trades on honest pump.fun launches - the first buy of 0.05 SOL or more, median across the fastest wallets.

They are not what you will get. They are the front of the race on that client, at that time, from those cities.

Two things to keep in mind:

- **This moves.** On October 8th one of the four changed its scheduling mode and went from 36-40 ms to a median of ~137 ms for everyone, regardless of what they paid. Nobody announced it.
- **Geography is most of it.** From a box in Amsterdam to the nearest node is 6.5 ms. From elsewhere, no tip closes that gap.

---

## What this does not do

It does not send transactions, hold keys, or touch a wallet.

It reads three public RPC methods - `getEpochInfo`, `getLeaderSchedule`, `getClusterNodes` - and prints what it finds.

The public endpoint rate limits hard. For anything repeated, pass `--rpc` with your own.

---

## License

MIT. Take it, fork it, correct it.

If your measurements disagree with the table above, open an issue with yours - that is more useful to me than agreement.

[@ventry089](https://x.com/ventry089)
