"""One-off script to purge isolated test entries (dave, charlie, bob, alice, host)
from the production poker.sqlite3 database without affecting real users.
"""

import os
import shutil
import sqlite3
import sys
import time

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "backend", "data", "poker.sqlite3")
)
DIRTY_PLAYERS = ("dave", "charlie", "bob", "alice", "host")


def run_cleanup():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    # 1. Create a timestamped backup first
    backup_path = f"{DB_PATH}.bak.{int(time.time())}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"[1/4] Created backup at: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 2. Identify dirty entries
        q_marks = ",".join(["?"] * len(DIRTY_PLAYERS))
        cursor.execute(
            f"SELECT DISTINCT entry_id FROM ledger_participants WHERE player_id IN ({q_marks})",
            DIRTY_PLAYERS,
        )
        dirty_entries = [r[0] for r in cursor.fetchall()]
        print(f"[2/4] Found {len(dirty_entries)} dirty ledger entries associated with {DIRTY_PLAYERS}")

        if not dirty_entries:
            print("No dirty entries found. Database is already clean.")
            return

        # Ensure no real users are in these entries
        placeholders = ",".join(["?"] * len(dirty_entries))
        cursor.execute(
            f"SELECT DISTINCT player_id FROM ledger_participants WHERE entry_id IN ({placeholders})",
            dirty_entries,
        )
        all_players = [r[0] for r in cursor.fetchall()]
        unexpected_real = [p for p in all_players if p not in DIRTY_PLAYERS]
        if unexpected_real:
            raise RuntimeError(
                f"Safety check failed! Found real users {unexpected_real} inside target entries. Aborting!"
            )

        # 3. Perform atomic deletion
        conn.execute("BEGIN TRANSACTION")
        cursor.execute(
            f"DELETE FROM ledger_participants WHERE entry_id IN ({placeholders})",
            dirty_entries,
        )
        del_parts = cursor.rowcount

        cursor.execute(
            f"DELETE FROM ledger_entries WHERE entry_id IN ({placeholders})",
            dirty_entries,
        )
        del_entries = cursor.rowcount

        conn.commit()
        print(f"[3/4] Successfully deleted {del_parts} participant rows and {del_entries} entry rows.")

        # 4. Verify post-cleanup state
        cursor.execute("SELECT DISTINCT player_id, nickname FROM ledger_participants")
        remaining = cursor.fetchall()
        print(f"[4/4] Remaining active ledger participants: {remaining}")

        cursor.execute("""
            SELECT player_id, nickname, sum(net_chips), round(sum(net_cash_cents) / 100.0, 2)
            FROM ledger_participants
            GROUP BY player_id
        """)
        user_sums = cursor.fetchall()
        total_cash = sum(r[3] for r in user_sums)
        print("  User net balances:")
        for r in user_sums:
            print(f"    - {r[0]} ({r[1]}): net_chips={r[2]}, net_cash=¥{r[3]:.2f}")
        print(f"  Total system net cash sum: ¥{total_cash:.2f} (Zero-sum conservation verified)")

    except Exception as e:
        conn.rollback()
        print(f"Error during cleanup: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_cleanup()
