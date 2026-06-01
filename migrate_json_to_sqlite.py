"""One-time migration: import tickets from tickets.json into the SQLite database."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from aamad.data_store import DataStore, SupportTicketData

JSON_PATH = os.path.join("src", "aamad", "data", "tickets.json")


def main():
    # Load JSON source
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not raw:
        print("tickets.json is empty — nothing to migrate.")
        return

    # Open a DataStore that uses SQLite (condition now accepts it)
    store = DataStore()
    if not store.use_database:
        print("ERROR: DataStore is not using a database backend.")
        print("Make sure DATABASE_PROVIDER=sqlite in your .env and SQLAlchemy is installed.")
        sys.exit(1)

    migrated = 0
    skipped = 0
    for ref_id, data in raw.items():
        try:
            ticket = SupportTicketData(**data)
            store.save_ticket(ticket)
            migrated += 1
            print(f"  ✓  {ref_id}  [{ticket.status}]")
        except Exception as exc:
            print(f"  ✗  {ref_id}  SKIPPED — {exc}")
            skipped += 1

    print(f"\nMigration complete: {migrated} tickets inserted, {skipped} skipped.")


if __name__ == "__main__":
    main()
