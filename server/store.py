"""Encrypted, bounded pairing journals; identity remains in LiteLLM."""
import json
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager

from cryptography.fernet import Fernet


class Store:
    def __init__(self, path, key):
        self.path = Path(path)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.cipher = Fernet(key)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS pairs (code TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, payload BLOB NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload BLOB NOT NULL)')
        os.chmod(self.path, 0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def encode(self, value):
        return self.cipher.encrypt(json.dumps(value, separators=(',', ':')).encode())

    def decode(self, value):
        return json.loads(self.cipher.decrypt(value))

    def pairs(self):
        with self.connection() as db:
            return [self.decode(row[0]) for row in db.execute('SELECT payload FROM pairs')]

    def pair(self, code=None, token_hash=None):
        field, value = ('code', code) if code is not None else ('token_hash', token_hash)
        with self.connection() as db:
            row = db.execute('SELECT payload FROM pairs WHERE ' + field + '=?', (value,)).fetchone()
        return self.decode(row[0]) if row else None

    def put(self, value):
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO pairs VALUES (?,?,?)',
                       (value['code'], value['token_hash'], self.encode(value)))

    def delete(self, code):
        with self.connection() as db:
            db.execute('DELETE FROM pairs WHERE code=?', (code,))

    def device(self, device_id):
        with self.connection() as db:
            row = db.execute('SELECT payload FROM devices WHERE id=?', (device_id,)).fetchone()
        return self.decode(row[0]) if row else None

    def devices(self, owner):
        with self.connection() as db:
            return [self.decode(row[0]) for row in db.execute('SELECT payload FROM devices WHERE owner=?', (owner,))]

    def put_device(self, device):
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO devices VALUES (?,?,?)',
                       (device['device_id'], device['user_id'], self.encode(device)))

    def commit_device(self, pair, device):
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO pairs VALUES (?,?,?)',
                       (pair['code'], pair['token_hash'], self.encode(pair)))
            db.execute('INSERT OR REPLACE INTO devices VALUES (?,?,?)',
                       (device['device_id'], device['user_id'], self.encode(device)))
