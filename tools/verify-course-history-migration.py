#!/usr/bin/env python3
"""Back up SQLite read-only, migrate only the fresh copy, compare every old row.
Usage: backend/.venv/bin/python tools/verify-course-history-migration.py --source backend/db.sqlite3 --copy /private/tmp/new-copy.sqlite3
Prints counts only; never writes to source or logs transcript contents.
"""
import argparse
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(db):
    return [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]


def rows(db, table):
    return db.execute('SELECT * FROM "' + table.replace('"', '""') + '"').fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--copy', required=True, type=Path)
    args = parser.parse_args()
    source, target = args.source.resolve(strict=True), args.copy.resolve()
    if source == target or target.exists():
        parser.error('Copy must be a new path distinct from source.')
    before_hash = digest(source)
    # Exclusive create, private permissions from the first byte.
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as original, sqlite3.connect(target) as copy:
        original.backup(copy)
        before = {name: rows(copy,name) for name in tables(copy)}
    backend = Path(__file__).resolve().parents[1] / 'backend'
    env = {**os.environ, 'DJANGO_DB_PATH':str(target)}
    subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], cwd=backend, env=env, check=True)
    framework = {'django_migrations', 'django_content_type', 'auth_permission'}
    with sqlite3.connect(target.as_uri()+'?mode=ro', uri=True) as copy:
        for name, old in before.items():
            new = rows(copy, name)
            if name == 'sqlite_sequence':
                after_sequences = dict(new)
                assert all(after_sequences.get(k) == v for k,v in old if k not in framework), 'Application sequence changed'
            elif name in framework:
                assert set(old).issubset(set(new)), 'Existing framework rows changed: '+name
            else:
                assert sorted(old,key=repr) == sorted(new,key=repr), 'Existing table changed: '+name
        assert copy.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Integrity error'
        assert not copy.execute('PRAGMA foreign_key_check').fetchall(), 'Foreign key error'
    assert digest(source) == before_hash, 'Source changed during validation; inspect concurrent writers'
    print(f'PASS: {len(before)} existing tables preserved; only framework additions allowed; SQLite integrity/FKs OK; source SHA-256 unchanged.')


if __name__ == '__main__':
    main()
