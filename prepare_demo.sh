#!/bin/bash

echo ""
echo "🎯 Agentic Support Platform — Demo Preparation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd /home/beatriz/AAMAD
source .venv/bin/activate

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1 — Backup current live tickets
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "📦 Step 1/4 — Backing up current tickets..."

python3 - <<'PYEOF'
import shutil, sqlite3
from pathlib import Path
from datetime import datetime

data_dir = Path("src/aamad/data")
db_path = data_dir / "support.db"

# Try both possible DB names
for db_name in ["support.db", "tickets.db"]:
    db_path = data_dir / db_name
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            count = conn.execute(
                "SELECT COUNT(*) FROM support_tickets"
            ).fetchone()[0]
            conn.close()
            if count > 0:
                backup_name = f"support_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                backup_path = data_dir / backup_name
                shutil.copy2(db_path, backup_path)
                print(f"  ✅ Backed up {count} tickets → {backup_name}")
            else:
                print(f"  ℹ️  Live DB is already empty — no backup needed")
        except Exception as e:
            print(f"  ⚠️  Could not backup: {e}")
        break
else:
    print("  ℹ️  No live DB found — skipping backup")
PYEOF

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2 — Merge new tickets into demo_dataset.db
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "🔀 Step 2/4 — Merging new tickets into demo dataset..."

python3 - <<'PYEOF'
import sqlite3, shutil
from pathlib import Path

data_dir = Path("src/aamad/data")
demo_db = data_dir / "demo_dataset.db"

if not demo_db.exists():
    print("  ⚠️  demo_dataset.db not found — skipping merge")
else:
    # Get existing reference_ids in demo
    demo_conn = sqlite3.connect(str(demo_db))
    demo_conn.row_factory = sqlite3.Row

    try:
        existing_ids = set(
            row[0] for row in demo_conn.execute(
                "SELECT reference_id FROM support_tickets"
            ).fetchall()
        )
        demo_before = len(existing_ids)
    except:
        existing_ids = set()
        demo_before = 0

    # Find all backup files to merge from
    sources = list(data_dir.glob("support_backup_*.db"))

    # Also try live DB
    for db_name in ["support.db", "tickets.db"]:
        live = data_dir / db_name
        if live.exists():
            sources.append(live)

    total_merged = 0
    for source in sources:
        try:
            src = sqlite3.connect(str(source))
            src.row_factory = sqlite3.Row
            rows = src.execute(
                "SELECT * FROM support_tickets"
            ).fetchall()

            merged = 0
            for row in rows:
                d = dict(row)
                ref_id = d.get('reference_id', '')
                if not ref_id or ref_id in existing_ids:
                    continue
                existing_ids.add(ref_id)
                cols = list(d.keys())
                vals = [d[c] for c in cols]
                try:
                    demo_conn.execute(
                        f"INSERT INTO support_tickets "
                        f"({','.join(cols)}) "
                        f"VALUES ({','.join(['?']*len(cols))})",
                        vals
                    )
                    merged += 1
                except:
                    pass

            demo_conn.commit()
            src.close()
            if merged > 0:
                total_merged += merged
                print(f"  ✅ +{merged} tickets from {source.name}")
        except Exception as e:
            pass  # Skip files that don't have support_tickets table

    final = demo_conn.execute(
        "SELECT COUNT(*) FROM support_tickets"
    ).fetchone()[0]
    demo_conn.close()

    print(f"  ✅ Demo dataset: {demo_before} → {final} tickets (+{total_merged} new)")
PYEOF

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — Clear live database
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "🗑️  Step 3/4 — Clearing live database..."

python3 - <<'PYEOF'
import sys
sys.path.insert(0, '.')

try:
    from src.aamad.data_store import data_store
    from sqlalchemy import text

    with data_store.SessionLocal() as session:
        result = session.execute(
            text("DELETE FROM support_tickets")
        )
        session.commit()
        print(f"  ✅ Cleared {result.rowcount} tickets from live DB")

        try:
            refunds = session.execute(
                text("SELECT COUNT(*) FROM refunds")
            ).scalar()
            print(f"  ✅ Refunds intact: {refunds} records")
        except:
            pass
except Exception as e:
    print(f"  ⚠️  Could not clear via SQLAlchemy: {e}")
    print(f"  Trying direct SQLite...")

    import sqlite3
    from pathlib import Path

    data_dir = Path("src/aamad/data")
    for db_name in ["support.db", "tickets.db"]:
        db_path = data_dir / db_name
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                result = conn.execute(
                    "DELETE FROM support_tickets"
                )
                conn.commit()
                print(f"  ✅ Cleared {result.rowcount} tickets")
                conn.close()
                break
            except Exception as e2:
                print(f"  ❌ Failed: {e2}")
PYEOF

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4 — Verify everything
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "✅ Step 4/4 — Verifying state..."

python3 - <<'PYEOF'
import sqlite3
from pathlib import Path

data_dir = Path("src/aamad/data")

# Check live DB
live_tickets = 0
for db_name in ["support.db", "tickets.db"]:
    db_path = data_dir / db_name
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            live_tickets = conn.execute(
                "SELECT COUNT(*) FROM support_tickets"
            ).fetchone()[0]
            try:
                live_refunds = conn.execute(
                    "SELECT COUNT(*) FROM refunds"
                ).fetchone()[0]
            except:
                live_refunds = "n/a"
            conn.close()
            print(f"  Live DB:      {live_tickets} tickets, {live_refunds} refunds")
            break
        except:
            pass

# Check demo dataset
demo_db = data_dir / "demo_dataset.db"
if demo_db.exists():
    try:
        conn = sqlite3.connect(str(demo_db))
        demo_tickets = conn.execute(
            "SELECT COUNT(*) FROM support_tickets"
        ).fetchone()[0]
        conn.close()
        print(f"  Demo Dataset: {demo_tickets} tickets")
    except:
        print(f"  Demo Dataset: could not read")

# List backups
backups = sorted(data_dir.glob("support_backup_*.db"))
print(f"  Backups:      {len(backups)} files available")

print("")
if live_tickets == 0:
    print("  🎯 Ready for demo!")
    print("     Live DB is clean ✅")
    print("     Demo dataset loaded ✅")
else:
    print(f"  ⚠️  Live DB still has {live_tickets} tickets")
PYEOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 Now start the platform:"
echo "   ./start_demo.sh"
echo ""
echo "🔄 Dataset Toggle in Operator Dashboard:"
echo "   [● Live Demo]     → clean, starts from zero"
echo "   [📂 Historical]   → rich data, all tickets"
echo ""
echo "⚡ Quick Demo dropdown in Customer Portal"
echo "   → 25+ pre-filled scenarios ready"
echo ""
