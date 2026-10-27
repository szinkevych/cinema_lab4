"""Create a timestamped custom-format PostgreSQL backup using pg_dump."""
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPOSITORY_ROOT / "backups",
        help="directory for the backup file (default: repository/backups)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = output_dir / f"cinema_{timestamp}.dump"

    env = os.environ.copy()
    env.setdefault("PGHOST", "localhost")
    env.setdefault("PGPORT", "5434")
    env.setdefault("PGDATABASE", "cinema")
    env.setdefault("PGUSER", "postgres")
    env.setdefault("PGPASSWORD", "password")

    host = env["PGHOST"]
    port = env["PGPORT"]
    database = env["PGDATABASE"]
    user = env["PGUSER"]
    pg_dump = shutil.which("pg_dump")
    if pg_dump:
        command = [
            pg_dump, "--no-password", "--format=custom", "--no-owner",
            "--host", host, "--port", port, "--username", user, "--dbname", database,
            "--file", str(backup_path),
        ]
        output_stream = None
    else:
        docker = shutil.which("docker")
        if not docker:
            parser.exit(1, "Помилка: не знайдено ні pg_dump, ні Docker CLI.\n")
        command = [
            docker, "compose", "exec", "-T", "postgres", "pg_dump",
            "--no-password", "--format=custom", "--no-owner",
            "--username", user, "--dbname", database,
        ]
        output_stream = backup_path.open("wb")

    try:
        if output_stream:
            with output_stream:
                subprocess.run(command, cwd=REPOSITORY_ROOT, check=True, stdout=output_stream)
        else:
            subprocess.run(command, env=env, cwd=REPOSITORY_ROOT, check=True)
    except subprocess.CalledProcessError as error:
        backup_path.unlink(missing_ok=True)
        parser.exit(error.returncode, "Помилка: не вдалося створити резервну копію PostgreSQL.\n")

    print(f"Резервну копію створено: {backup_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
