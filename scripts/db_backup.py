"""
ForgeFlow AI - Database Backup & Restore Script.

Creates compressed PostgreSQL dumps with pgvector extension support.
Designed to run as a daily cron job or via manual invocation.

Usage:
    python scripts/db_backup.py backup          # Create a backup
    python scripts/db_backup.py restore <file>  # Restore from backup
    python scripts/db_backup.py list            # List available backups

Configuration:
    DB_URL=postgresql://user:pass@host:5432/forgeflow
    BACKUP_DIR=./db/backups  (default)
    BACKUP_RETENTION_DAYS=30  (default, auto-clean old backups)
"""

import argparse
import gzip
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _get_db_url() -> str:
    """Resolve database URL from environment or .env file."""
    url = os.getenv("DB_URL", "")
    if url:
        return url

    # Try loading from .env
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DB_URL="):
                    return line.split("=", 1)[1].strip()

    raise RuntimeError(
        "DB_URL not set. Set DB_URL=postgresql://user:pass@host:5432/dbname"
    )


def _get_backup_dir() -> Path:
    """Resolve backup directory from environment or default."""
    backup_dir = os.getenv("BACKUP_DIR", "")
    if backup_dir:
        return Path(backup_dir)
    return Path(__file__).resolve().parent.parent / "db" / "backups"


def _get_retention_days() -> int:
    """Get backup retention period in days."""
    return int(os.getenv("BACKUP_RETENTION_DAYS", "30"))


def backup() -> Path:
    """Create a compressed database backup.

    Uses pg_dump with:
    - Custom format (compressed) for smaller file size
    - --no-owner and --no-acl for portability
    - Includes pgvector extension data

    Returns:
        Path to the created backup file.
    """
    db_url = _get_db_url()
    backup_dir = _get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"forgeflow_backup_{timestamp}.sql.gz"
    filepath = backup_dir / filename

    print(f"[backup] Creating backup: {filepath}")
    print(f"[backup] Database: {db_url.split('@')[1] if '@' in db_url else db_url}")

    # Use pg_dump with custom format
    try:
        result = subprocess.run(
            [
                "pg_dump",
                db_url,
                "--format=custom",  # Compressed custom format
                "--compress=9",  # Maximum compression
                "--no-owner",
                "--no-acl",
                "--file",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"[backup] Success: {filepath} ({filepath.stat().st_size / 1024:.1f} KB)")
        return filepath
    except subprocess.CalledProcessError as e:
        print(f"[backup] FAILED: {e.stderr}", file=sys.stderr)
        raise


def restore(filepath: Path) -> None:
    """Restore database from a backup file.

    WARNING: This will DROP and recreate all database objects.
    Only run against a dedicated restore target, never production.

    Args:
        filepath: Path to the backup file (.sql.gz or .dump).
    """
    db_url = _get_db_url()

    if not filepath.exists():
        raise FileNotFoundError(f"Backup file not found: {filepath}")

    confirm = input(
        f"\nWARNING: This will DROP and recreate the database at\n"
        f"  {db_url.split('@')[1] if '@' in db_url else db_url}\n"
        f"  from {filepath}\n"
        f"Type 'YES' to confirm: "
    )
    if confirm != "YES":
        print("[restore] Aborted.")
        return

    print(f"[restore] Restoring from: {filepath}")

    try:
        result = subprocess.run(
            [
                "pg_restore",
                "--dbname",
                db_url,
                "--clean",  # Drop existing objects
                "--if-exists",  # Don't fail if object doesn't exist
                "--no-owner",
                "--no-acl",
                "--jobs=4",  # Parallel restore
                str(filepath),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        print("[restore] Success!")
    except subprocess.CalledProcessError as e:
        print(f"[restore] FAILED: {e.stderr}", file=sys.stderr)
        raise


def list_backups() -> list[Path]:
    """List available backup files sorted by date (newest first)."""
    backup_dir = _get_backup_dir()
    if not backup_dir.exists():
        print(f"[list] No backup directory found: {backup_dir}")
        return []

    backups = sorted(
        backup_dir.glob("forgeflow_backup_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backups:
        print("[list] No backups found.")
        return []

    print(f"[list] {len(backups)} backup(s) in {backup_dir}:")
    for bp in backups:
        age_days = (datetime.now() - datetime.fromtimestamp(bp.stat().st_mtime)).days
        size_kb = bp.stat().st_size / 1024
        print(f"  {bp.name}  ({size_kb:.0f} KB, {age_days}d ago)")

    return backups


def cleanup_old_backups(retention_days: int | None = None) -> int:
    """Remove backups older than retention_days.

    Returns:
        Number of backups removed.
    """
    if retention_days is None:
        retention_days = _get_retention_days()

    backup_dir = _get_backup_dir()
    if not backup_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0

    for bp in backup_dir.glob("forgeflow_backup_*"):
        mtime = datetime.fromtimestamp(bp.stat().st_mtime)
        if mtime < cutoff:
            bp.unlink()
            print(f"[cleanup] Removed old backup: {bp.name}")
            removed += 1

    if removed == 0:
        print(f"[cleanup] No backups older than {retention_days} days found.")
    return removed


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ForgeFlow AI - Database Backup & Restore"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("backup", help="Create a compressed database backup")
    restore_parser = sub.add_parser("restore", help="Restore from a backup file")
    restore_parser.add_argument("file", type=Path, help="Path to backup file")
    sub.add_parser("list", help="List available backups")
    cleanup_parser = sub.add_parser("cleanup", help="Remove old backups")
    cleanup_parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="Days to retain (default: BACKUP_RETENTION_DAYS or 30)",
    )

    args = parser.parse_args()

    if args.command == "backup":
        path = backup()
        cleanup_old_backups()
        print(f"\nBackup complete: {path}")
    elif args.command == "restore":
        restore(args.file)
    elif args.command == "list":
        list_backups()
    elif args.command == "cleanup":
        cleanup_old_backups(args.retention_days)
