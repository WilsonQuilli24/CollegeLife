import main
from services import post_rules

def test_normalize_origin_accepts_http_and_https():
    assert main._normalize_origin("http://localhost:5173/path") == "http://localhost:5173"
    assert main._normalize_origin("https://example.com/abc") == "https://example.com"

def test_normalize_origin_rejects_invalid_values():
    assert main._normalize_origin("ftp://example.com") is None
    assert main._normalize_origin("not-a-url") is None

def test_is_allowed_frontend_origin_allows_localhost_hosts():
    assert main.is_allowed_frontend_origin("http://localhost:3000") is True
    assert main.is_allowed_frontend_origin("http://127.0.0.1:5173") is True

def test_is_allowed_frontend_origin_rejects_unknown_remote_origin():
    assert main.is_allowed_frontend_origin("https://malicious.example.com") is False

def test_ids_as_ints_filters_invalid_values():
    assert main._ids_as_ints(["1", 2, "bad", None, 3]) == [1, 2, 3]

def test_normalize_user_falls_back_to_user_id_field():
    normalized = main.normalize_user({"user_id": 99, "email": "a@a.edu", "role": "user"})
    assert normalized["id"] == 99
    assert normalized["email"] == "a@a.edu"

def test_serialize_post_counts_and_flags():
    row = {
        "id": 1,
        "caption": "hello",
        "created_at": "2026-01-01T00:00:00Z",
        "author_id": 10,
        "author_name": "A",
        "author_email": "a@example.edu",
        "media_public_id": "x",
        "media_url": "https://cdn",
        "media_type": "image",
        "liked_by": [10, 11],
        "viewed_by": [11],
    }

    serialized = main.serialize_post(row, current_user_id=10)
    assert serialized["likes"] == 2
    assert serialized["views"] == 1
    assert serialized["liked_by_me"] is True
    assert serialized["viewed_by_me"] is False

def test_post_rule_normalize_caption_trims_and_clamps():
    assert post_rules.normalize_caption("  hi  ") == "hi"
    assert post_rules.normalize_caption("x" * 300, max_length=10) == "x" * 10

def test_post_rule_validate_create_payload_happy_and_error():
    ok = post_rules.validate_create_payload("pub", "https://cdn")
    bad = post_rules.validate_create_payload("", None)
    assert ok.ok is True
    assert bad.ok is False
    assert "media_public_id" in bad.error

def test_post_rule_can_user_modify_post_admin_and_owner_rules():
    assert post_rules.can_user_modify_post(current_user_id=1, row_author_id=2, role="admin") is True
    assert post_rules.can_user_modify_post(current_user_id=1, row_author_id=1, role="user") is True
    assert post_rules.can_user_modify_post(current_user_id=1, row_author_id=2, role="user") is False