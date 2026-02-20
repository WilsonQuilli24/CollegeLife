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

def test_unauthenticated_access_to_protected_route_returns_401(client, fake_supabase):
    response = client.get("/users/me")
    assert response.status_code == 401
    payload = response.get_json()
    assert payload["error"] == "Unauthorized"

def test_happy_path_create_and_fetch_post(client, fake_supabase, auth_as):
    _seed_user(fake_supabase, 1, "a@school.edu")
    auth_as("a@school.edu", user_id=1)
    create = client.post(
        "/api/posts",
        json={
            "caption": "First",
            "media_public_id": "pub1",
            "media_url": "https://cdn/x.jpg",
            "media_type": "image",
        },
    )
    assert create.status_code == 201
    created = create.get_json()
    assert created["caption"] == "First"
    assert created["author"]["email"] == "a@school.edu"

    listing = client.get("/api/posts")
    assert listing.status_code == 200
    posts = listing.get_json()["posts"]
    assert len(posts) == 1
    assert posts[0]["id"] == created["id"]

def test_validation_error_on_invalid_create_payload(client, fake_supabase, auth_as):
    _seed_user(fake_supabase, 1, "a@school.edu")
    auth_as("a@school.edu", user_id=1)
    response = client.post(
        "/api/posts",
        json={
            "caption": "Missing media",
            "media_public_id": "",
            "media_url": None,
        },
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert "media_public_id" in payload["error"]

def test_authenticated_user_can_update_own_data(client, fake_supabase, auth_as):
    _seed_user(fake_supabase, 1, "owner@school.edu")
    auth_as("owner@school.edu", user_id=1)

    create = client.post(
        "/api/posts",
        json={
            "caption": "Original",
            "media_public_id": "pub1",
            "media_url": "https://cdn/x.jpg",
            "media_type": "image",
        },
    )
    post_id = create.get_json()["id"]
    update = client.put(f"/api/posts/{post_id}", json={"caption": "Updated"})
    assert update.status_code == 200
    payload = update.get_json()
    assert payload["caption"] == "Updated"

def test_user_b_cannot_update_user_a_post(client, fake_supabase, auth_as):
    _seed_user(fake_supabase, 1, "a@school.edu")
    _seed_user(fake_supabase, 2, "b@school.edu")
    auth_as("a@school.edu", user_id=1)
    create = client.post(
        "/api/posts",
        json={
            "caption": "A owns this",
            "media_public_id": "pub1",
            "media_url": "https://cdn/x.jpg",
            "media_type": "image",
        },
    )
    post_id = create.get_json()["id"]

    auth_as("b@school.edu", user_id=2)
    response = client.put(f"/api/posts/{post_id}", json={"caption": "B takeover"})
    assert response.status_code == 403
    assert response.get_json()["error"] == "Forbidden"

def test_user_b_cannot_delete_user_a_post(client, fake_supabase, auth_as, monkeypatch):
    _seed_user(fake_supabase, 1, "a@school.edu")
    _seed_user(fake_supabase, 2, "b@school.edu")

    monkeypatch.setattr(main.cloudinary.uploader, "destroy", lambda *args, **kwargs: None)

    auth_as("a@school.edu", user_id=1)
    create = client.post(
        "/api/posts",
        json={
            "caption": "A owns this",
            "media_public_id": "pub1",
            "media_url": "https://cdn/x.jpg",
            "media_type": "image",
        },
    )
    post_id = create.get_json()["id"]

    auth_as("b@school.edu", user_id=2)
    response = client.delete(f"/api/posts/{post_id}")
    assert response.status_code == 403
    assert response.get_json()["error"] == "Forbidden"