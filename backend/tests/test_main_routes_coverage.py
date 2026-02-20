from __future__ import annotations
from datetime import datetime
import main

def _seed_user(fake_supabase, user_id, email, role="user", name="User"):
    fake_supabase.table("users").insert(
        {
            "id": user_id,
            "email": email,
            "name": name,
            "role": role,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
    ).execute()

def _seed_post(fake_supabase, post_id, author_id, author_email, caption="cap"):
    fake_supabase.table("posts").insert(
        {
            "id": post_id,
            "caption": caption,
            "media_public_id": f"pub-{post_id}",
            "media_url": f"https://cdn/{post_id}.jpg",
            "media_type": "image",
            "author_id": author_id,
            "author_email": author_email,
            "author_name": author_email,
            "liked_by": [],
            "viewed_by": [],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
    ).execute()

def test_require_auth_auto_heals_missing_user_row(client, fake_supabase, auth_as):
    auth_as("missing@school.edu", user_id=99)

    response = client.get("/users/me")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["email"] == "missing@school.edu"

def test_require_auth_fallback_when_supabase_lookup_fails(client, auth_as, monkeypatch):
    auth_as("fallback@school.edu", role="admin", user_id=42)

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "ensure_supabase", boom)

    response = client.get("/users/me")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["email"] == "fallback@school.edu"
    assert payload["role"] == "admin"

def test_require_admin_blocks_non_admin(client, fake_supabase, auth_as):
    _seed_user(fake_supabase, 1, "user@school.edu", role="user")
    auth_as("user@school.edu", role="user", user_id=1)

    response = client.post("/users", json={"name": "N", "email": "n@school.edu"})

    assert response.status_code == 403
    assert response.get_json()["error"] == "Forbidden"

def test_create_post_returns_500_when_insert_returns_empty(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "owner@school.edu")
    auth_as("owner@school.edu", user_id=1)

    original_table = fake_supabase.table

    class EmptyInsertTable:
        def __init__(self, delegate):
            self.delegate = delegate
            self._is_insert = False

        def select(self, *a, **k):
            self.delegate.select(*a, **k)
            return self

        def eq(self, *a, **k):
            self.delegate.eq(*a, **k)
            return self

        def limit(self, *a, **k):
            self.delegate.limit(*a, **k)
            return self

        def order(self, *a, **k):
            self.delegate.order(*a, **k)
            return self

        def insert(self, payload):
            self._is_insert = True
            self.delegate.insert(payload)
            return self

        def update(self, payload):
            self.delegate.update(payload)
            return self

        def delete(self):
            self.delegate.delete()
            return self

        def execute(self):
            if self._is_insert:
                return type("R", (), {"data": []})()
            return self.delegate.execute()

    class Wrapper:
        def table(self, name):
            return EmptyInsertTable(original_table(name))

    monkeypatch.setattr(main, "ensure_supabase", lambda: Wrapper())

    response = client.post(
        "/api/posts",
        json={"caption": "c", "media_public_id": "p", "media_url": "https://cdn/x.jpg"},
    )

    assert response.status_code == 500
    assert response.get_json()["error"] == "Failed to create post"


def test_create_post_exception_path(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "owner@school.edu")
    auth_as("owner@school.edu", user_id=1)

    def boom():
        raise RuntimeError("supabase unavailable")

    monkeypatch.setattr(main, "ensure_supabase", boom)

    response = client.post(
        "/api/posts",
        json={"caption": "c", "media_public_id": "p", "media_url": "https://cdn/x.jpg"},
    )

    assert response.status_code == 500
    assert response.get_json()["error"] == "Failed to create post"

def test_list_posts_exception_path(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "owner@school.edu")
    auth_as("owner@school.edu", user_id=1)

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))

    response = client.get("/api/posts")

    assert response.status_code == 500
    assert response.get_json()["error"] == "Failed to list posts"

def test_toggle_like_not_found(client, fake_supabase, auth_as):
    _seed_user(fake_supabase, 1, "user@school.edu")
    auth_as("user@school.edu", user_id=1)

    response = client.post("/api/posts/999/like")

    assert response.status_code == 404

def test_toggle_like_update_failure(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "user@school.edu")
    _seed_post(fake_supabase, 1, 1, "user@school.edu")
    auth_as("user@school.edu", user_id=1)

    original_table = fake_supabase.table

    class BrokenUpdateWrapper:
        def table(self, name):
            delegate = original_table(name)

            class Q:
                def __init__(self):
                    self._is_update = False

                def select(self, *a, **k):
                    delegate.select(*a, **k)
                    return self

                def eq(self, *a, **k):
                    delegate.eq(*a, **k)
                    return self

                def limit(self, *a, **k):
                    delegate.limit(*a, **k)
                    return self

                def insert(self, payload):
                    delegate.insert(payload)
                    return self

                def update(self, payload):
                    self._is_update = True
                    delegate.update(payload)
                    return self

                def delete(self):
                    delegate.delete()
                    return self

                def execute(self):
                    if self._is_update and name == "posts":
                        return type("R", (), {"data": []})()
                    return delegate.execute()

            return Q()

    monkeypatch.setattr(main, "ensure_supabase", lambda: BrokenUpdateWrapper())

    response = client.post("/api/posts/1/like")

    assert response.status_code == 500
    assert response.get_json()["error"] == "Failed to update like"

def test_toggle_like_exception_path(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "user@school.edu")
    auth_as("user@school.edu", user_id=1)

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))

    response = client.post("/api/posts/1/like")

    assert response.status_code == 500
    assert response.get_json()["error"] == "Failed to toggle like"

def test_view_not_found_and_update_failure(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "user@school.edu")
    _seed_post(fake_supabase, 1, 1, "user@school.edu")
    auth_as("user@school.edu", user_id=1)

    not_found = client.post("/api/posts/999/view")
    assert not_found.status_code == 404

    original_table = fake_supabase.table

    class BrokenViewUpdateWrapper:
        def table(self, name):
            delegate = original_table(name)

            class Q:
                def __init__(self):
                    self._is_update = False

                def select(self, *a, **k):
                    delegate.select(*a, **k)
                    return self

                def eq(self, *a, **k):
                    delegate.eq(*a, **k)
                    return self

                def limit(self, *a, **k):
                    delegate.limit(*a, **k)
                    return self

                def update(self, payload):
                    self._is_update = True
                    delegate.update(payload)
                    return self

                def execute(self):
                    if self._is_update and name == "posts":
                        return type("R", (), {"data": []})()
                    return delegate.execute()

            return Q()

    monkeypatch.setattr(main, "ensure_supabase", lambda: BrokenViewUpdateWrapper())

    failed_update = client.post("/api/posts/1/view")
    assert failed_update.status_code == 500
    assert failed_update.get_json()["error"] == "Failed to update view"

def test_view_exception_path(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "user@school.edu")
    auth_as("user@school.edu", user_id=1)

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))

    response = client.post("/api/posts/1/view")

    assert response.status_code == 500
    assert response.get_json()["error"] == "Failed to register view"

def test_update_post_not_found_and_no_payload_paths(client, fake_supabase, auth_as):
    _seed_user(fake_supabase, 1, "owner@school.edu")
    _seed_post(fake_supabase, 1, 1, "owner@school.edu", caption="old")
    auth_as("owner@school.edu", user_id=1)

    missing = client.put("/api/posts/999", json={"caption": "x"})
    assert missing.status_code == 404

    no_payload = client.put("/api/posts/1", json={})
    assert no_payload.status_code == 200
    assert no_payload.get_json()["caption"] == "old"

def test_update_post_media_replace_validation_and_empty_update(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "owner@school.edu")
    _seed_post(fake_supabase, 1, 1, "owner@school.edu", caption="old")
    auth_as("owner@school.edu", user_id=1)

    bad = client.put("/api/posts/1", json={"media_public_id": "", "media_url": ""})
    assert bad.status_code == 400

    original_table = fake_supabase.table

    class EmptyPostUpdateWrapper:
        def table(self, name):
            delegate = original_table(name)

            class Q:
                def __init__(self):
                    self._is_update = False

                def select(self, *a, **k):
                    delegate.select(*a, **k)
                    return self

                def eq(self, *a, **k):
                    delegate.eq(*a, **k)
                    return self

                def limit(self, *a, **k):
                    delegate.limit(*a, **k)
                    return self

                def update(self, payload):
                    self._is_update = True
                    delegate.update(payload)
                    return self

                def execute(self):
                    if self._is_update and name == "posts":
                        return type("R", (), {"data": []})()
                    return delegate.execute()

            return Q()

    monkeypatch.setattr(main, "ensure_supabase", lambda: EmptyPostUpdateWrapper())

    failed = client.put("/api/posts/1", json={"caption": "new"})
    assert failed.status_code == 500
    assert failed.get_json()["error"] == "Failed to update post"

def test_update_post_exception_and_cloudinary_destroy_exception(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "owner@school.edu")
    _seed_post(fake_supabase, 1, 1, "owner@school.edu", caption="old")
    auth_as("owner@school.edu", user_id=1)

    def destroy_raises(*_a, **_k):
        raise RuntimeError("cloudinary error")

    monkeypatch.setattr(main.cloudinary.uploader, "destroy", destroy_raises)

    ok = client.put(
        "/api/posts/1",
        json={"media_public_id": "new-public", "media_url": "https://cdn/new.jpg", "media_type": "image"},
    )
    assert ok.status_code == 200

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    failed = client.put("/api/posts/1", json={"caption": "x"})
    assert failed.status_code == 500
    assert failed.get_json()["error"] == "Failed to update post"


def test_delete_post_not_found_success_and_exception(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "owner@school.edu")
    _seed_post(fake_supabase, 1, 1, "owner@school.edu", caption="old")
    auth_as("owner@school.edu", user_id=1)

    missing = client.delete("/api/posts/999")
    assert missing.status_code == 404

    def destroy_raises(*_a, **_k):
        raise RuntimeError("cloudinary error")

    monkeypatch.setattr(main.cloudinary.uploader, "destroy", destroy_raises)
    success = client.delete("/api/posts/1")
    assert success.status_code == 200

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    failed = client.delete("/api/posts/1")
    assert failed.status_code == 500
    assert failed.get_json()["error"] == "Failed to delete post"

def test_users_list_admin_user_and_error(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "admin@school.edu", role="admin")
    _seed_user(fake_supabase, 2, "user@school.edu", role="user")

    auth_as("admin@school.edu", role="admin", user_id=1)
    admin_listing = client.get("/users")
    assert admin_listing.status_code == 200
    assert len(admin_listing.get_json()) >= 2

    auth_as("user@school.edu", role="user", user_id=2)
    user_listing = client.get("/users")
    assert user_listing.status_code == 200
    assert len(user_listing.get_json()) == 1

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    error_listing = client.get("/users")
    assert error_listing.status_code == 500

def test_get_user_success_forbidden_not_found_and_error(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "admin@school.edu", role="admin")
    _seed_user(fake_supabase, 2, "user@school.edu", role="user")
    _seed_user(fake_supabase, 3, "other@school.edu", role="user")

    auth_as("user@school.edu", role="user", user_id=2)
    own = client.get("/users/2")
    assert own.status_code == 200

    forbidden = client.get("/users/3")
    assert forbidden.status_code == 403

    missing = client.get("/users/999")
    assert missing.status_code == 404

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    error_case = client.get("/users/2")
    assert error_case.status_code == 500

def test_update_user_paths(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "admin@school.edu", role="admin")
    _seed_user(fake_supabase, 2, "user@school.edu", role="user")
    _seed_user(fake_supabase, 3, "other@school.edu", role="user")

    auth_as("user@school.edu", role="user", user_id=2)
    no_payload = client.put("/users/2", json={})
    assert no_payload.status_code == 200

    forbidden = client.put("/users/3", json={"name": "X"})
    assert forbidden.status_code == 403

    not_found = client.put("/users/999", json={"name": "X"})
    assert not_found.status_code == 404

    auth_as("admin@school.edu", role="admin", user_id=1)
    admin_update = client.put(
        "/users/2",
        json={"name": "Updated", "email": "updated@school.edu", "role": "admin"},
    )
    assert admin_update.status_code == 200
    assert admin_update.get_json()["role"] == "admin"

    original_table = fake_supabase.table

    class EmptyUserUpdateWrapper:
        def table(self, name):
            delegate = original_table(name)

            class Q:
                def __init__(self):
                    self._is_update = False

                def select(self, *a, **k):
                    delegate.select(*a, **k)
                    return self

                def eq(self, *a, **k):
                    delegate.eq(*a, **k)
                    return self

                def limit(self, *a, **k):
                    delegate.limit(*a, **k)
                    return self

                def update(self, payload):
                    self._is_update = True
                    delegate.update(payload)
                    return self

                def execute(self):
                    if self._is_update and name == "users":
                        return type("R", (), {"data": []})()
                    return delegate.execute()

            return Q()

    monkeypatch.setattr(main, "ensure_supabase", lambda: EmptyUserUpdateWrapper())
    empty_update = client.put("/users/2", json={"name": "Nope"})
    assert empty_update.status_code == 500

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    error_case = client.put("/users/2", json={"name": "Err"})
    assert error_case.status_code == 500

def test_delete_user_paths(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "admin@school.edu", role="admin")
    _seed_user(fake_supabase, 2, "user@school.edu", role="user")
    _seed_user(fake_supabase, 3, "other@school.edu", role="user")

    auth_as("user@school.edu", role="user", user_id=2)
    forbidden = client.delete("/users/3")
    assert forbidden.status_code == 403

    not_found = client.delete("/users/999")
    assert not_found.status_code == 404

    auth_as("admin@school.edu", role="admin", user_id=1)
    success = client.delete("/users/3")
    assert success.status_code == 200

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    error_case = client.delete("/users/2")
    assert error_case.status_code == 500

def test_create_user_paths(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "admin@school.edu", role="admin")
    auth_as("admin@school.edu", role="admin", user_id=1)

    bad = client.post("/users", json={"name": "OnlyName"})
    assert bad.status_code == 400

    duplicate_existing = client.post("/users", json={"name": "A", "email": "admin@school.edu"})
    assert duplicate_existing.status_code == 400

    created = client.post("/users", json={"name": "New", "email": "new@school.edu", "role": "user"})
    assert created.status_code == 201

    original_table = fake_supabase.table

    class EmptyCreateWrapper:
        def table(self, name):
            delegate = original_table(name)

            class Q:
                def __init__(self):
                    self._is_insert = False

                def select(self, *a, **k):
                    delegate.select(*a, **k)
                    return self

                def eq(self, *a, **k):
                    delegate.eq(*a, **k)
                    return self

                def limit(self, *a, **k):
                    delegate.limit(*a, **k)
                    return self

                def insert(self, payload):
                    self._is_insert = True
                    delegate.insert(payload)
                    return self

                def execute(self):
                    if self._is_insert and name == "users":
                        return type("R", (), {"data": []})()
                    return delegate.execute()

            return Q()

    monkeypatch.setattr(main, "ensure_supabase", lambda: EmptyCreateWrapper())
    empty_create = client.post("/users", json={"name": "NoRows", "email": "norows@school.edu"})
    assert empty_create.status_code == 500

    monkeypatch.setattr(main, "ensure_supabase", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    error_case = client.post("/users", json={"name": "Err", "email": "err@school.edu"})
    assert error_case.status_code == 500