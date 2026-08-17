#!/usr/bin/env python3
"""Re-clone `graylinx_synex` from a source database, safely.

    python scripts/reclone_plant_db.py --check                     # inspect only, no changes
    python scripts/reclone_plant_db.py --from graylinx_v2 --apply
    python scripts/reclone_plant_db.py --from graylinx_v3 --apply

**This drops a database. Read the pre-flight before passing `--apply`.**

---

**Why this is a script and not three commands.**

`DROP DATABASE graylinx_synex` is irreversible, and the interesting question is not whether
the clone works — it is whether the *source* is the one you meant. The issue recorded in
`docs/DATA-ISSUE-2026-08-14-simulated-rows.md` is that `graylinx_synex` was cloned from
`graylinx_v2`, and **`graylinx_v2` is where the simulated rows came from**: 156,129 marked
`(equipment, slot_time)` pairs spanning 2026-06-23 11:55 to 2026-08-05 23:55.

So re-cloning from `graylinx_v2` reproduces the defect exactly — *unless `v2` has itself
been refreshed since*. That is a question about the source, it is cheap to answer, and it is
the one nobody checks at 11pm. `--check` answers it before anything is dropped.

`graylinx_v3` was loaded from `shiva_014_08_2026.zip` and reportedly holds **real** readings
for 18-Jun to 05-Aug — the same window. If that is confirmed by `--check`, it is the better
source.

**What this script will not do.** It will not decide for you. If the chosen source still
carries simulated rows it stops and says so; `--i-accept-simulated-rows` overrides that, and
the override exists so the decision is recorded in your shell history rather than made by a
script default.

**Credentials.** `synex_plant_ro` cannot do this by design — it holds `SELECT` on
`graylinx_synex` alone (Q42). Pass an admin user with `--user`; the password is read from
`MYSQL_ADMIN_PASSWORD` or prompted, never taken from a flag, so it stays out of history.
"""
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
from datetime import datetime

try:
    import pymysql
except ImportError:  # pragma: no cover
    sys.exit("pymysql is required: pip install pymysql")

# Windows consoles default to cp1252, which cannot encode the box-drawing characters this
# script prints — and a UnicodeEncodeError while reporting is a crash before the useful
# output, not after it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGET = "graylinx_synex"
MARKER = "snapshot_simulated_slots"
PROBE_TABLE = "chiller_1_normalized"


def connect(host: str, port: int, user: str, password: str, db: str | None = None):
    return pymysql.connect(
        host=host, port=port, user=user, password=password, database=db, connect_timeout=8
    )


def inspect(conn, db: str) -> dict:
    """What is actually in a database. Facts only — no verdict."""
    out: dict = {"database": db, "exists": False}
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = %s", (db,))
    if not cur.fetchone()[0]:
        return out
    out["exists"] = True

    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s", (db,)
    )
    out["tables"] = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = %s AND table_name = %s",
        (db, MARKER),
    )
    out["has_marker"] = bool(cur.fetchone()[0])

    if out["has_marker"]:
        cur.execute(f"SELECT COUNT(*), MIN(slot_time), MAX(slot_time) FROM `{db}`.`{MARKER}`")
        n, lo, hi = cur.fetchone()
        out["simulated_rows"] = n
        out["simulated_span"] = (lo, hi)

    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = %s AND table_name = %s",
        (db, PROBE_TABLE),
    )
    if cur.fetchone()[0]:
        cur.execute(
            f"SELECT COUNT(*), MIN(slot_time), MAX(slot_time) FROM `{db}`.`{PROBE_TABLE}`"
        )
        out["probe_rows"], out["first_slot"], out["last_slot"] = cur.fetchone()
        # Condenser flow is the signal that decides most, and the one the simulation
        # invented. Real slots with a non-zero value is the single most useful number here.
        if out["has_marker"]:
            cur.execute(
                f"SELECT SUM(n.cond_flow <> 0) FROM `{db}`.`{PROBE_TABLE}` n "
                f"LEFT JOIN `{db}`.`{MARKER}` s "
                f"  ON s.equipment = %s AND s.slot_time = n.slot_time "
                f"WHERE s.slot_time IS NULL",
                (PROBE_TABLE,),
            )
        else:
            cur.execute(f"SELECT SUM(cond_flow <> 0) FROM `{db}`.`{PROBE_TABLE}`")
        out["cond_flow_nonzero_real"] = cur.fetchone()[0] or 0
    return out


def report(info: dict) -> None:
    db = info["database"]
    if not info["exists"]:
        print(f"  {db}: DOES NOT EXIST")
        return
    print(f"  {db}: {info['tables']} tables")
    if "probe_rows" in info:
        print(
            f"    {PROBE_TABLE}: {info['probe_rows']:,} rows, "
            f"{info['first_slot']} -> {info['last_slot']}"
        )
        print(f"    cond_flow non-zero in real slots: {info['cond_flow_nonzero_real']:,}")
    if info["has_marker"]:
        lo, hi = info["simulated_span"]
        print(f"    ** {MARKER}: {info['simulated_rows']:,} rows, {lo} -> {hi}")
    else:
        print(f"    no {MARKER} table — nothing is marked simulated")


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-clone the plant database, safely")
    ap.add_argument("--from", dest="source", default="graylinx_v2", help="source database")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3307)
    ap.add_argument("--user", default="root", help="an admin user; synex_plant_ro cannot do this")
    ap.add_argument("--check", action="store_true", help="inspect and stop")
    ap.add_argument("--apply", action="store_true", help="actually drop and re-clone")
    ap.add_argument(
        "--i-accept-simulated-rows",
        action="store_true",
        help="proceed even when the source still carries simulated rows",
    )
    args = ap.parse_args()

    if not args.check and not args.apply:
        ap.error("pass --check to inspect, or --apply to re-clone")

    password = os.environ.get("MYSQL_ADMIN_PASSWORD") or getpass.getpass(
        f"password for {args.user}@{args.host}:{args.port}: "
    )
    conn = connect(args.host, args.port, args.user, password)

    print("\n── before ──────────────────────────────────────────────────────────")
    src = inspect(conn, args.source)
    tgt = inspect(conn, TARGET)
    report(src)
    report(tgt)

    if not src["exists"]:
        print(f"\nFAILED — source {args.source} does not exist.")
        return 1

    print("\n── the question that matters ───────────────────────────────────────")
    dirty = src.get("has_marker") and src.get("simulated_rows", 0) > 0
    if dirty:
        lo, hi = src["simulated_span"]
        print(
            f"  {args.source} still carries {src['simulated_rows']:,} simulated rows "
            f"({lo} -> {hi})."
        )
        print("  Cloning from it reproduces the defect exactly — the new copy will have")
        print("  the same synthetic six weeks, and cond_flow will again look measured.")
        print("  graylinx_v3 was loaded from the 14-Aug Shiva dump with real rows for that")
        print("  window; --check it before choosing.")
    else:
        print(f"  {args.source} carries no simulated-row marker. Clean source.")

    if args.check:
        print("\n--check only. Nothing was changed.")
        return 0

    if dirty and not args.i_accept_simulated_rows:
        print("\nSTOPPED. Re-run with --i-accept-simulated-rows if that is what you want,")
        print("or use --from graylinx_v3.")
        return 2

    print("\n── applying ────────────────────────────────────────────────────────")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"  DROP DATABASE {TARGET}  (irreversible)")
    print(f"  CREATE DATABASE {TARGET}")
    print(f"  copy {args.source} -> {TARGET} via mysqldump")
    if input("\n  type the database name to confirm: ").strip() != TARGET:
        print("  not confirmed. Nothing was changed.")
        return 3

    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS `{TARGET}`")
    cur.execute(f"CREATE DATABASE `{TARGET}` CHARACTER SET utf8mb4")
    conn.commit()

    dump = subprocess.run(
        [
            "mysqldump", f"--host={args.host}", f"--port={args.port}",
            f"--user={args.user}", f"--password={password}",
            "--single-transaction", "--quick", "--routines", "--events",
            args.source,
        ],
        capture_output=True,
    )
    if dump.returncode != 0:
        print("  mysqldump failed:", dump.stderr.decode(errors="replace")[:400])
        return 4

    load = subprocess.run(
        [
            "mysql", f"--host={args.host}", f"--port={args.port}",
            f"--user={args.user}", f"--password={password}", TARGET,
        ],
        input=dump.stdout,
        capture_output=True,
    )
    if load.returncode != 0:
        print("  load failed:", load.stderr.decode(errors="replace")[:400])
        return 5

    # The read-only grant is on the database, and dropping the database drops it with the
    # schema. Without this the back end cannot connect after a re-clone — which is the
    # failure that turns a five-minute job into an evening. Q42.
    cur.execute(f"GRANT SELECT ON `{TARGET}`.* TO 'synex_plant_ro'@'localhost'")
    cur.execute(f"GRANT SELECT ON `{TARGET}`.* TO 'synex_plant_ro'@'%'")
    cur.execute("FLUSH PRIVILEGES")
    conn.commit()

    print("\n── after ───────────────────────────────────────────────────────────")
    report(inspect(conn, TARGET))
    print(f"\nDone ({stamp}). Re-run the gate:")
    print("  cd backend && pytest -m requires_box")
    print("  in particular tests/integration/test_provenance.py, which asserts the")
    print("  measured-window clip still abuts the marker boundary.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
