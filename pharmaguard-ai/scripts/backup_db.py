#!/usr/bin/env python3
"""
PharmaGuard AI — Automated Production Database Backup Script
Dumps PostgreSQL or SQLite databases with timestamping and gzip compression.
"""
import os
import sys
import subprocess
import gzip
import shutil
from datetime import datetime, timezone
from pathlib import Path

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_database():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    db_url = os.getenv("DATABASE_URL", "sqlite:///pharmaguard_prod.db")

    print(f"[{timestamp}] Initiating PharmaGuard AI Database Backup...")

    if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        # PostgreSQL pg_dump
        backup_file = BACKUP_DIR / f"pg_backup_{timestamp}.sql.gz"
        cmd = f"pg_dump {db_url} | gzip > {backup_file}"
        try:
            subprocess.run(cmd, shell=True, check=True)
            print(f"Successfully created PostgreSQL backup: {backup_file} ({backup_file.stat().st_size} bytes)")
        except Exception as e:
            print(f"PostgreSQL backup failed: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        # SQLite file copy + gzip
        sqlite_path = db_url.replace("sqlite:///", "")
        source_file = Path(sqlite_path)
        if not source_file.exists():
            # Fallback to local db if path relative
            source_file = Path(__file__).resolve().parent.parent / "backend" / "pharmaguard_prod.db"

        if source_file.exists():
            backup_file = BACKUP_DIR / f"sqlite_backup_{timestamp}.db.gz"
            with open(source_file, "rb") as f_in, gzip.open(backup_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            print(f"Successfully created SQLite backup: {backup_file} ({backup_file.stat().st_size} bytes)")
        else:
            print(f"SQLite source file {source_file} not found; skipping backup.")


if __name__ == "__main__":
    backup_database()
