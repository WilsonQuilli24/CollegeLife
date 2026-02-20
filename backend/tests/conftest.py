from __future__ import annotations
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
import main

class FakeResponse:
    def __init__(self, data):
        self.data = data

class FakeQuery:
    def __init__(self, store: dict, table: str):
        self.store = store
        self.table = table
        self._action = "select"
        self._filters = []
        self._limit = None
        self._order = None
        self._update_payload = None
        self._insert_payload = None

    def select(self, *_args, **_kwargs):
        self._action = "select"
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def order(self, field, desc=False):
        self._order = (field, desc)
        return self

    def insert(self, payload):
        self._action = "insert"
        self._insert_payload = payload
        return self

    def update(self, payload):
        self._action = "update"
        self._update_payload = payload
        return self

    def delete(self):
        self._action = "delete"
        return self

    def _rows(self):
        return self.store.setdefault(self.table, [])

    def _match(self, row):
        for field, value in self._filters:
            if row.get(field) != value:
                return False
        return True

    def execute(self):
        rows = self._rows()

        if self._action == "insert":
            payloads = self._insert_payload if isinstance(self._insert_payload, list) else [self._insert_payload]
            inserted = []
            for payload in payloads:
                row = deepcopy(payload)
                if row.get("id") is None:
                    row["id"] = self.store.setdefault("_id_counter", {}).get(self.table, 1)
                    self.store["_id_counter"][self.table] = row["id"] + 1
                if "created_at" not in row:
                    row["created_at"] = datetime.utcnow().isoformat() + "Z"
                rows.append(row)
                inserted.append(deepcopy(row))
            return FakeResponse(inserted)

        matched = [row for row in rows if self._match(row)]

        if self._order:
            field, desc = self._order
            matched = sorted(matched, key=lambda r: r.get(field) or "", reverse=desc)

        if self._limit is not None:
            matched = matched[: self._limit]

        if self._action == "select":
            return FakeResponse(deepcopy(matched))

        if self._action == "update":
            updated = []
            for row in rows:
                if self._match(row):
                    row.update(self._update_payload or {})
                    updated.append(deepcopy(row))
            if self._order:
                field, desc = self._order
                updated = sorted(updated, key=lambda r: r.get(field) or "", reverse=desc)
            if self._limit is not None:
                updated = updated[: self._limit]
            return FakeResponse(updated)

        if self._action == "delete":
            deleted = []
            kept = []
            for row in rows:
                if self._match(row):
                    deleted.append(deepcopy(row))
                else:
                    kept.append(row)
            self.store[self.table] = kept
            return FakeResponse(deleted)

        return FakeResponse([])

class FakeSupabase:
    def __init__(self):
        self.store = {"users": [], "posts": [], "_id_counter": {"users": 1, "posts": 1}}

    def table(self, name):
        return FakeQuery(self.store, name)

@pytest.fixture
def app():
    main.app.config.update(TESTING=True)
    return main.app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def fake_supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(main, "ensure_supabase", lambda: fake)
    return fake

@pytest.fixture
def auth_as(client):
    def _login(email: str, name: str = "Test User", role: str = "user", user_id: int = 1):
        with client.session_transaction() as sess:
            sess["user"] = email
            sess["user_name"] = name
            sess["user_role"] = role
            sess["user_id"] = user_id
    return _login