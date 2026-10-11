#!/usr/bin/env python3
"""Resumable product catalog job for the sbx "local to cloud" workshop.

It cleans up a messy catalog of 500 products, one product at a time:
trims and title-cases names, sets prices to .99, picks a category from
the name, and flags duplicate UPCs (same product shape as
dockersamples/catalog-service-node: name, upc, price).

State lives in the embedded SurrealDB from the sbx-kits-surrealdb kit,
inside the sandbox filesystem. Stop the job, move the sandbox, run it
again, and it carries on from the last finished product.

Usage (inside the sandbox):
    python3 catalog_job.py run       # start or resume the job
    python3 catalog_job.py status    # progress, safe while the job runs
    python3 catalog_job.py report    # summary, after the job stops
    python3 catalog_job.py reset     # start over

Settings (environment variables):
    JOB_DELAY   seconds per product (default 0.6, about 5 minutes total)
    JOB_SITE    label for where a product was processed (default: hostname)
"""
import json
import os
import random
import socket
import sys
import time
from datetime import datetime, timezone

try:
    from surrealdb import Surreal
except ImportError:
    sys.exit("SurrealDB SDK not found. Create the sandbox with the SurrealDB kit.")

HOME = "/home/agent"
WORK = os.environ.get("JOB_DIR", f"{HOME}/catalog-job")
PROGRESS = f"{WORK}/progress.txt"
REPORT = f"{WORK}/report.json"
DB_URL = os.environ.get("JOB_DB_URL", f"surrealkv://{WORK}/db")
TOTAL = 500
DELAY = float(os.environ.get("JOB_DELAY", "0.6"))
SITE = os.environ.get("JOB_SITE", socket.gethostname())

CATEGORIES = {
    "electronics": ["hub", "cable", "charger", "keyboard", "mouse", "monitor", "stand"],
    "kitchen": ["pan", "kettle", "mug", "knife", "pour over", "grinder"],
    "books": ["book", "guide", "handbook", "cookbook"],
    "outdoor": ["tent", "backpack", "bottle", "lantern"],
}
WORDS = [w for ws in CATEGORIES.values() for w in ws]
ADJ = ["compact", "pro", "classic", "travel", "deluxe", "mini", "smart", "eco"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def connect():
    os.makedirs(WORK, exist_ok=True)
    db = Surreal(DB_URL)
    db.connect()
    db.use("sandbox", "catalog_job")
    return db


def seed(db):
    """Create the same messy raw catalog every time (fixed random seed)."""
    rng = random.Random(42)
    upcs = []
    for n in range(1, TOTAL + 1):
        if n % 50 == 0:
            upc = upcs[rng.randrange(len(upcs))]  # a duplicate UPC on purpose
        else:
            upc = f"{100000000000 + n}"
        upcs.append(upc)
        name = f"  {rng.choice(ADJ)} {rng.choice(WORDS)}  ".upper() if n % 3 == 0 \
            else f" {rng.choice(ADJ)} {rng.choice(WORDS)} "
        db.query(
            f"UPSERT raw:{n} SET n = $n, upc = $upc, name = $name, price = $price;",
            {"n": n, "upc": upc, "name": name, "price": round(rng.uniform(5, 150), 2)},
        )
    db.query("UPSERT job:state SET total = $t, done = 0, started_at = $at;",
             {"t": TOTAL, "at": now()})


def category_for(name):
    low = name.lower()
    for cat, words in CATEGORIES.items():
        if any(w in low for w in words):
            return cat
    return "other"


def write_progress(done, last, site):
    tmp = PROGRESS + ".tmp"
    with open(tmp, "w") as f:
        f.write(f"{done}/{TOTAL} products done | last: {last} | on {site} | {now()}\n")
    os.replace(tmp, PROGRESS)


def run():
    db = connect()
    if not db.query("SELECT * FROM job:state;"):
        print("Seeding 500 raw products...")
        seed(db)
    done = db.query("SELECT VALUE done FROM job:state;")[0]
    if done >= TOTAL:
        print("Job already finished. Run: python3 catalog_job.py report")
        return
    print(f"Resuming at product {done + 1} of {TOTAL} on {SITE}" if done
          else f"Starting job on {SITE}")
    # Rebuild the set of UPCs seen so far from the raw rows up to the last
    # counted product, not from the product table. If a move interrupts the job
    # between writing product:n and bumping job:state.done, product:n would
    # otherwise reappear here and be wrongly flagged as a duplicate of itself.
    seen = set(db.query("SELECT VALUE upc FROM raw WHERE n <= $done;", {"done": done}))
    for n in range(done + 1, TOTAL + 1):
        raw = db.query(f"SELECT * FROM raw:{n};")[0]
        name = " ".join(raw["name"].split()).title()
        dup = raw["upc"] in seen
        seen.add(raw["upc"])
        db.query(
            f"UPSERT product:{n} SET upc = $upc, name = $name, price = $price, "
            "category = $cat, duplicate_upc = $dup, processed_on = $site, processed_at = $at;",
            {"n": n, "upc": raw["upc"], "name": name,
             "price": int(raw["price"]) + 0.99, "cat": category_for(name),
             "dup": dup, "site": SITE, "at": now()},
        )
        db.query("UPDATE job:state SET done = $n;", {"n": n})
        write_progress(n, name, SITE)
        time.sleep(DELAY)
    db.query("UPDATE job:state SET finished_at = $at;", {"at": now()})
    db.close()
    write_report()
    print(f"Done. {TOTAL} products processed. Run: python3 catalog_job.py report")


def write_report():
    db = connect()
    by_site = db.query("SELECT processed_on, count() AS products FROM product GROUP BY processed_on;")
    by_cat = db.query("SELECT category, count() AS products FROM product GROUP BY category;")
    dups = db.query("SELECT VALUE upc FROM product WHERE duplicate_upc = true;")
    state = db.query("SELECT * FROM job:state;")[0]
    db.close()
    report = {
        "products_done": state["done"],
        "total": state["total"],
        "processed_on": {r["processed_on"]: r["products"] for r in by_site},
        "by_category": {r["category"]: r["products"] for r in by_cat},
        "duplicate_upcs": sorted(set(dups)),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
    }
    with open(REPORT, "w") as f:
        json.dump(report, f, indent=2)
    return report


def status():
    if os.path.exists(PROGRESS):
        print(open(PROGRESS).read().strip())
    else:
        print("No progress yet. Run: python3 catalog_job.py run")


def report():
    r = write_report()
    print(f"Products done: {r['products_done']} of {r['total']}")
    print("Where each product was processed:")
    for site, count in r["processed_on"].items():
        print(f"  {site:<32} {count}")
    print("By category:")
    for cat, count in sorted(r["by_category"].items()):
        print(f"  {cat:<32} {count}")
    print(f"Duplicate UPCs flagged: {len(r['duplicate_upcs'])}")
    print(f"Saved to {REPORT}")


def reset():
    import shutil
    shutil.rmtree(WORK, ignore_errors=True)
    print("Job reset.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"run": run, "status": status, "report": report, "reset": reset}.get(
        cmd, lambda: sys.exit(__doc__))()
