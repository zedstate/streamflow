import sys
import os
import sqlite3
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.connection import init_db, DB_PATH, CONFIG_DIR

def main():
    print("--- 1. Initializing Main Database Tables ---")
    init_db()  # Ensures runs, channel_health, stream_telemetry tables are created

    src_db = CONFIG_DIR / 'telemetry.db'
    dest_db = DB_PATH

    print(f"Source DB: {src_db}")
    print(f"Dest DB: {dest_db}")

    if not src_db.exists():
        print(f"Source database {src_db} does not exist. No data to migrate.")
        sys.exit(0)

    print("--- 2. Attaching and Migrating Rows ---")
    try:
        conn = sqlite3.connect(str(dest_db))
        cursor = conn.cursor()

        # Attach source database
        cursor.execute(f"ATTACH DATABASE '{src_db}' AS telemetry")

        # Copy runs
        print("Migrating 'runs' table...")
        cursor.execute("INSERT OR IGNORE INTO runs SELECT * FROM telemetry.runs")
        runs_count = cursor.rowcount
        print(f"Migrated {runs_count} runs")

        # Copy channel_health
        print("Migrating 'channel_health' table...")
        cursor.execute("INSERT OR IGNORE INTO channel_health SELECT * FROM telemetry.channel_health")
        ch_count = cursor.rowcount
        print(f"Migrated {ch_count} channel_health items")

        # Copy stream_telemetry
        print("Migrating 'stream_telemetry' table...")
        cursor.execute("INSERT OR IGNORE INTO stream_telemetry SELECT * FROM telemetry.stream_telemetry")
        st_count = cursor.rowcount
        print(f"Migrated {st_count} stream_telemetry items")

        conn.commit()
        print("--- Migration Completed Successfully ---")
        
        # Optional: Rename old db for safety
        backup_path = CONFIG_DIR / 'telemetry.db.bak'
        if backup_path.exists():
             backup_path.unlink()
        src_db.rename(backup_path)
        print(f"Backed up old telemetry.db to {backup_path}")

    except Exception as e:
        print(f"Migration Failed: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
