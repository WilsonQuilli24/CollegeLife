import os
import json
import logging
import time
import uuid
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse
import cloudinary
import cloudinary.api
import cloudinary.uploader
import requests
from authlib.integrations.base_client.errors import MismatchingStateError
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, session, g, Response
from flask_caching import Cache
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest
from supabase import Client, create_client
from werkzeug.exceptions import HTTPException
from services.post_rules import (
    can_user_modify_post,
    normalize_caption,
    normalize_id_list,
    validate_create_payload,
)

load_dotenv()

app = Flask(__name__)
cache = Cache(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.config["SESSION_COOKIE_NAME"] = "college_session"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

API_KEY = os.getenv("UNI_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API")
YELP_API_KEY = os.getenv("YELP_API_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
}
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    cleaned_url = SUPABASE_URL.strip().strip('"').strip("'")
    supabase = create_client(cleaned_url, SUPABASE_SERVICE_ROLE_KEY.strip())
elif os.getenv("DATABASE_URL") and SUPABASE_SERVICE_ROLE_KEY:
    db_url = os.getenv("DATABASE_URL", "").strip().strip('"').strip("'")
    parsed = urlparse(db_url)
    host = parsed.hostname or ""
    if host.startswith("db.") and host.endswith(".supabase.co"):
        project_ref = host[3:].split(".supabase.co")[0]
        candidate = f"https://{project_ref}.supabase.co"
        supabase = create_client(candidate, SUPABASE_SERVICE_ROLE_KEY.strip())

CORS(
    app,
    origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    supports_credentials=True,
)

oauth = OAuth(app)
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

spotify = oauth.register(
    name="spotify",
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    access_token_url="https://accounts.spotify.com/api/token",
    authorize_url="https://accounts.spotify.com/authorize",
    api_base_url="https://api.spotify.com/v1",
    client_kwargs={
        "scope": "user-read-playback-state user-read-currently-playing streaming user-modify-playback-state"
    },
)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

CLOUDINARY_CONFIGURED = all(
    [
        os.getenv("CLOUDINARY_CLOUD_NAME"),
        os.getenv("CLOUDINARY_API_KEY"),
        os.getenv("CLOUDINARY_API_SECRET"),
    ]
)

limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
limiter.init_app(app)

logger = logging.getLogger("college_life")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
logger.propagate = False

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests by method, path, and status code",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency by method and path",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
POSTS_CREATED_TOTAL = Counter("posts_created_total", "Number of posts created")

def _normalize_origin(origin):  # pragma: no cover
    if not origin:
        return None
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def is_allowed_frontend_origin(origin):  # pragma: no cover
    normalized = _normalize_origin(origin)
    if not normalized:
        return False

    parsed = urlparse(normalized)
    hostname = parsed.hostname
    if hostname in {"localhost", "127.0.0.1"}:
        return True

    return normalized == FRONTEND_URL

def resolve_frontend_origin(preferred=None):  # pragma: no cover
    if preferred and is_allowed_frontend_origin(preferred):
        return _normalize_origin(preferred)

    stored = session.get("frontend_origin")
    if stored and is_allowed_frontend_origin(stored):
        return _normalize_origin(stored)

    header_origin = request.headers.get("Origin")
    if header_origin and is_allowed_frontend_origin(header_origin):
        return _normalize_origin(header_origin)

    if request.referrer and is_allowed_frontend_origin(request.referrer):
        return _normalize_origin(request.referrer)

    return FRONTEND_URL

def remember_frontend_origin(candidate):  # pragma: no cover
    if is_allowed_frontend_origin(candidate):
        session["frontend_origin"] = _normalize_origin(candidate)

def _safe_next_path(candidate):  # pragma: no cover
    if not candidate:
        return None
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None
    return candidate

def _backend_origin():  # pragma: no cover
    return BACKEND_URL.rstrip("/")

def _clear_spotify_state():  # pragma: no cover
    stale_keys = [k for k in session.keys() if str(k).startswith("_state_spotify_")]
    for key in stale_keys:
        session.pop(key, None)

def _event(event, level="info", **data):  # pragma: no cover
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level.upper(),
        "event": event,
        **data,
    }
    message = json.dumps(payload, default=str)
    getattr(logger, level if hasattr(logger, level) else "info")(message)

def _request_path():  # pragma: no cover
    if request.url_rule and request.url_rule.rule:
        return request.url_rule.rule
    return request.path

@app.before_request
def _before_request():  # pragma: no cover
    g.request_start = time.perf_counter()
    g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

@app.after_request
def _after_request(response):  # pragma: no cover
    elapsed = max(time.perf_counter() - getattr(g, "request_start", time.perf_counter()), 0)
    path = _request_path()
    method = request.method
    status = str(response.status_code)

    REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
    REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)
    response.headers["X-Request-ID"] = getattr(g, "request_id", "")

    _event(
        "http_request",
        level="info",
        request_id=getattr(g, "request_id", None),
        method=method,
        path=path,
        status_code=response.status_code,
        duration_ms=round(elapsed * 1000, 2),
    )
    return response

@app.errorhandler(Exception)
def _handle_unexpected_error(error):  # pragma: no cover
    if isinstance(error, HTTPException):
        return error
    request_id = getattr(g, "request_id", None)
    _event(
        "unhandled_exception",
        level="error",
        request_id=request_id,
        method=request.method,
        path=_request_path(),
        error_type=type(error).__name__,
    )
    return jsonify({"error": "Internal server error", "request_id": request_id}), 500

def ensure_supabase():
    if supabase is None:
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    return supabase

def normalize_user(row):
    user_id = row.get("id")
    if user_id is None:
        user_id = row.get("user_id")

    return {
        "id": user_id,
        "email": row.get("email"),
        "name": row.get("name"),
        "role": row.get("role", "user"),
        "created_at": row.get("created_at"),
    }

def _ids_as_ints(values):
    return normalize_id_list(values)

def serialize_post(row, current_user_id=None):
    liked_by = _ids_as_ints(row.get("liked_by") or [])
    viewed_by = _ids_as_ints(row.get("viewed_by") or [])
    current = int(current_user_id) if current_user_id is not None else None

    return {
        "id": row["id"],
        "caption": row.get("caption", ""),
        "created_at": row.get("created_at"),
        "author": {
            "id": row["author_id"],
            "name": row.get("author_name"),
            "email": row.get("author_email"),
        },
        "media": {
            "public_id": row.get("media_public_id"),
            "url": row.get("media_url"),
            "type": row.get("media_type"),
        },
        "likes": len(liked_by),
        "views": len(viewed_by),
        "liked_by_me": current in liked_by if current is not None else False,
        "viewed_by_me": current in viewed_by if current is not None else False,
    }

def get_spotify_headers():  # pragma: no cover
    token = session.get("spotify_token")
    if not token:
        return None

    expires_at = token.get("expires_at")
    if expires_at and datetime.utcnow().timestamp() > expires_at:
        new_token = spotify.refresh_token(
            token_url=spotify.access_token_url,
            refresh_token=token["refresh_token"],
        )
        new_token["expires_at"] = datetime.utcnow().timestamp() + new_token["expires_in"]
        session["spotify_token"] = new_token
        token = new_token

    return {"Authorization": f"Bearer {token['access_token']}"}

def requireAuth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_email = session.get("user")
        if not user_email:
            return (
                jsonify({"error": "Unauthorized", "message": "Valid access token is required"}),
                401,
            )

        try:
            client = ensure_supabase()
            normalized_email = str(user_email).strip().lower()
            result = client.table("users").select("*").eq("email", normalized_email).limit(1).execute()
            user_rows = result.data or []

            if not user_rows:
                insert_role = "admin" if normalized_email in ADMIN_EMAILS else "user"
                inserted = (
                    client.table("users")
                    .insert(
                        {
                            "email": normalized_email,
                            "name": session.get("user_name"),
                            "role": insert_role,
                        }
                    )
                    .execute()
                )
                user_rows = inserted.data or []

            if not user_rows:
                return jsonify({"error": "User not found"}), 401

            request.user = normalize_user(user_rows[0])
            session["user_id"] = request.user.get("id")
            session["user_role"] = request.user.get("role", "user")
            if not request.user.get("email"):
                return jsonify({"error": "User not found"}), 401
        except Exception as e:
            normalized_email = str(user_email).strip().lower()
            request.user = {
                "id": session.get("user_id"),
                "email": normalized_email,
                "name": session.get("user_name"),
                "role": session.get("user_role") or ("admin" if normalized_email in ADMIN_EMAILS else "user"),
                "created_at": None,
            }
            session["user"] = normalized_email

        return f(*args, **kwargs)

    return decorated

def requireAdmin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.user.get("role") != "admin":
            return jsonify({"error": "Forbidden", "message": "Admin access required"}), 403
        return f(*args, **kwargs)

    return decorated

@app.get("/health")
def health_check():  # pragma: no cover
    if supabase is None:
        return jsonify({"status": "UP", "db": "NOT_CONFIGURED"}), 200

    try:
        ensure_supabase().table("users").select("id", count="exact").limit(1).execute()
        return jsonify({"status": "UP", "db": "UP"}), 200
    except Exception as e:
        return jsonify({"status": "DEGRADED", "db": "DOWN"}), 500

@app.get("/health/live")
def health_live():  # pragma: no cover
    return jsonify({"status": "UP"}), 200

@app.get("/health/ready")
def health_ready():  # pragma: no cover
    if supabase is None:
        return jsonify({"status": "UP", "db": "NOT_CONFIGURED"}), 200
    try:
        ensure_supabase().table("users").select("id", count="exact").limit(1).execute()
        return jsonify({"status": "UP", "db": "UP"}), 200
    except Exception:
        return jsonify({"status": "DOWN", "db": "DOWN"}), 503

@app.get("/metrics")
def metrics():  # pragma: no cover
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route("/auth/login")
def login():  # pragma: no cover
    frontend_origin = request.args.get("frontend_origin")
    next_path = _safe_next_path(request.args.get("next"))
    if frontend_origin:
        remember_frontend_origin(frontend_origin)
    else:
        remember_frontend_origin(request.headers.get("Origin"))
        if request.referrer:
            remember_frontend_origin(request.referrer)

    session.clear()
    if frontend_origin:
        remember_frontend_origin(frontend_origin)
    if next_path:
        session["oauth_next"] = next_path

    redirect_uri = f"{_backend_origin()}/auth/callback"
    return oauth.google.authorize_redirect(
        redirect_uri,
        prompt="select_account",
    )

@app.get("/auth/reset-session")
def reset_session():  # pragma: no cover
    session.clear()
    return jsonify({"message": "Session reset"})

@app.get("/auth/logout")
def logout():  # pragma: no cover
    frontend_origin = request.args.get("frontend_origin")
    target_origin = resolve_frontend_origin(frontend_origin)
    session.clear()
    return redirect(f"{target_origin}/")

@app.route("/auth/callback")
def auth_callback():  # pragma: no cover
    try:
        oauth.google.authorize_access_token()
    except MismatchingStateError:
        target_origin = resolve_frontend_origin()
        session.clear()
        return redirect(f"{target_origin}/?error=oauth_state_mismatch")

    user_info = oauth.google.userinfo()
    normalized_email = user_info["email"].strip().lower()
    is_admin_email = normalized_email in ADMIN_EMAILS

    if not is_admin_email and not normalized_email.endswith(".edu"):
        return jsonify({"error": "Must use school email"}), 403

    session["user"] = normalized_email
    session["user_name"] = user_info.get("name")
    email_domain = normalized_email.split("@")[-1] if "@" in normalized_email else ""

    try:
        client = ensure_supabase()
        result = client.table("users").select("*").eq("email", normalized_email).limit(1).execute()
        existing = result.data or []
        if not existing:
            inserted = client.table("users").insert(
                {
                    "email": normalized_email,
                    "name": user_info.get("name"),
                    "role": "admin" if is_admin_email else "user",
                }
            ).execute()
            inserted_rows = inserted.data or []
            if inserted_rows:
                session["user_id"] = inserted_rows[0].get("id")
                session["user_role"] = inserted_rows[0].get("role", "user")
            else:
                session["user_role"] = "admin" if is_admin_email else "user"
        elif is_admin_email and existing[0].get("role") != "admin":
            client.table("users").update({"role": "admin"}).eq("id", existing[0]["id"]).execute()
            session["user_id"] = existing[0].get("id")
            session["user_role"] = "admin"
        else:
            session["user_id"] = existing[0].get("id")
            session["user_role"] = existing[0].get("role", "user")
        _event(
            "user_login",
            request_id=getattr(g, "request_id", None),
            user_role=session.get("user_role", "user"),
            email_domain=email_domain,
        )
    except Exception as e:
        return jsonify({"error": "Failed to persist user in Supabase", "details": str(e)}), 500

    next_path = _safe_next_path(session.pop("oauth_next", None))
    if next_path:
        return redirect(f"{_backend_origin()}{next_path}")
    return redirect(f"{resolve_frontend_origin()}/?just_logged_in=1")

@app.get("/api/hello")
@requireAuth
def hello():  # pragma: no cover
    return jsonify({"message": f"Hello, {request.user['email']}!"})

@app.get("/api/server-time")
@requireAuth
@cache.cached(timeout=300, query_string=True)
def server_time():  # pragma: no cover
    return jsonify({"serverTime": datetime.utcnow().isoformat() + "Z"})


@app.route("/api/university")
@cache.cached(timeout=600, query_string=True)
def get_university():  # pragma: no cover
    name = request.args.get("name")
    url = "https://api.api-ninjas.com/v1/university"
    headers = {"X-API-Key": API_KEY}
    params = {"name": name}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return jsonify({"error": "Unexpected API format"}), 500
        return jsonify(data)
    except requests.RequestException as e:
        return jsonify({"error": "API request failed", "details": str(e)}), 502

@app.route("/api/weather")
@requireAuth
@limiter.limit("10 per minute")
@cache.cached(timeout=300, query_string=True)
def get_weather():  # pragma: no cover
    city = request.args.get("city")
    if not city:
        return jsonify({"error": "City is required"}), 400

    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": WEATHER_API_KEY, "units": "imperial"}

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        weather_info = {
            "city": data.get("name"),
            "country": data.get("sys", {}).get("country"),
            "description": data["weather"][0]["description"].title(),
            "temperature": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "icon": f"http://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png",
        }
        return jsonify(weather_info)
    except requests.RequestException as e:
        return jsonify({"error": "Weather API request failed", "details": str(e)}), 502
    except (KeyError, IndexError):
        return jsonify({"error": "Unexpected response format from weather API"}), 500

@app.route("/auth/spotify")
def spotify_login():  # pragma: no cover
    frontend_origin = request.args.get("frontend_origin")
    if frontend_origin:
        remember_frontend_origin(frontend_origin)
    else:
        remember_frontend_origin(request.headers.get("Origin"))
        if request.referrer:
            remember_frontend_origin(request.referrer)

    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI") or f"{_backend_origin()}/api/spotify/callback"
    _clear_spotify_state()
    try:
        return spotify.authorize_redirect(redirect_uri)
    except Exception as e:
        _event(
            "spotify_authorize_redirect_failed",
            level="error",
            request_id=getattr(g, "request_id", None),
            error_type=type(e).__name__,
        )
        return redirect(f"{resolve_frontend_origin()}/music?error=spotify_authorize_failed")

@app.route("/api/spotify/callback")
def spotify_callback():  # pragma: no cover
    try:
        token = spotify.authorize_access_token()
    except MismatchingStateError:
        _clear_spotify_state()
        return redirect(f"{resolve_frontend_origin()}/music?error=spotify_state_mismatch")
    except Exception as e:
        _event(
            "spotify_callback_failed",
            level="error",
            request_id=getattr(g, "request_id", None),
            error_type=type(e).__name__,
        )
        return redirect(f"{resolve_frontend_origin()}/music?error=spotify_callback_failed")

    expires_in = token.get("expires_in") or 3600
    token["expires_at"] = datetime.utcnow().timestamp() + int(expires_in)
    session["spotify_token"] = token
    session.modified = True
    return redirect(f"{resolve_frontend_origin()}/music?spotify_connected=1")


@app.get("/spotify/current")
@limiter.limit("15 per minute")
@cache.cached(timeout=300, query_string=True)
def spotify_current_track():  # pragma: no cover
    headers = get_spotify_headers()
    if not headers:
        return jsonify({"error": "Spotify not authenticated"}), 401

    response = requests.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers)
    if response.status_code == 204:
        return jsonify({"message": "No track currently playing"}), 200
    if response.status_code == 403:
        return jsonify({"message": "Spotify Premium required"}), 403
    if response.status_code != 200:
        return jsonify({"error": "Failed to get current track", "details": response.text}), response.status_code

    data = response.json()
    return jsonify(
        {
            "name": data["item"]["name"],
            "artists": [artist["name"] for artist in data["item"]["artists"]],
            "album": data["item"]["album"]["name"],
            "album_image": data["item"]["album"]["images"][0]["url"],
            "progress_ms": data["progress_ms"],
            "duration_ms": data["item"]["duration_ms"],
            "external_url": data["item"]["external_urls"]["spotify"],
        }
    )

@app.get("/api/spotify/token")
def get_spotify_token():  # pragma: no cover
    headers = get_spotify_headers()
    if not headers:
        return jsonify({"error": "Spotify not authenticated"}), 401
    token = session.get("spotify_token")
    return jsonify({"access_token": token["access_token"]})

@app.route("/api/yelp")
@requireAuth
@limiter.limit("5 per minute")
@cache.cached(timeout=300, query_string=True)
def get_yelp_restaurants():  # pragma: no cover
    location = request.args.get("location")
    term = request.args.get("term", "restaurant")
    limit = request.args.get("limit", 5)

    if not location:
        return jsonify({"error": "location parameter is required"}), 400

    url = "https://api.yelp.com/v3/businesses/search"
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    params = {"term": term, "location": location, "limit": limit}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        businesses = []
        for biz in data.get("businesses", []):
            businesses.append(
                {
                    "name": biz["name"],
                    "rating": biz.get("rating"),
                    "review_count": biz.get("review_count"),
                    "address": " ".join(biz.get("location", {}).get("display_address", [])),
                    "phone": biz.get("display_phone"),
                    "url": biz.get("url"),
                    "image_url": biz.get("image_url"),
                }
            )

        return jsonify({"businesses": businesses})
    except requests.RequestException as e:
        return jsonify({"error": "Yelp API request failed", "details": str(e)}), 502

@app.post("/api/media/upload")
@requireAuth
def upload_media():  # pragma: no cover
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    resource_type = request.form.get("resource_type", "auto")
    if resource_type not in {"image", "video", "raw", "auto"}:
        resource_type = "auto"

    if not CLOUDINARY_CONFIGURED:
        return jsonify({"error": "Upload failed", "details": "Cloudinary environment variables are missing."}), 500

    owner = request.user.get("id") or request.user.get("email") or "anonymous"
    owner = str(owner).replace("/", "_")

    try:
        result = cloudinary.uploader.upload(
            file,
            resource_type=resource_type,
            folder=f"college_life/{owner}/",
        )
        return jsonify(
            {
                "public_id": result["public_id"],
                "url": result["secure_url"],
                "type": result["resource_type"],
            }
        )
    except Exception as e:
        return jsonify({"error": "Upload failed", "details": f"{type(e).__name__}: {str(e)}"}), 500

@app.get("/api/media")
@requireAuth
@cache.cached(timeout=300, query_string=True)
def list_media():  # pragma: no cover
    owner = request.user.get("id") or request.user.get("email") or "anonymous"
    owner = str(owner).replace("/", "_")
    try:
        result = cloudinary.api.resources(type="upload", prefix=f"college_life/{owner}/")
        files = [
            {"public_id": f["public_id"], "url": f["secure_url"], "type": f["resource_type"]}
            for f in result.get("resources", [])
        ]
        return jsonify({"media": files})
    except Exception as e:
        return jsonify({"error": "Failed to list media", "details": str(e)}), 500

@app.put("/api/media/<public_id>")
@requireAuth
def edit_media(public_id):  # pragma: no cover
    data = request.get_json()
    try:
        result = cloudinary.api.update(public_id, folder=data.get("folder"))
        return jsonify({"updated": result})
    except Exception as e:
        return jsonify({"error": "Update failed", "details": str(e)}), 500

@app.delete("/api/media/<public_id>")
@requireAuth
def delete_media(public_id):  # pragma: no cover
    try:
        cloudinary.uploader.destroy(public_id, invalidate=True)
        return jsonify({"deleted": public_id})
    except Exception as e:
        return jsonify({"error": "Delete failed", "details": str(e)}), 500

@app.post("/api/posts")
@requireAuth
def create_post():
    data = request.get_json(silent=True) or {}
    caption = normalize_caption(data.get("caption"))
    media_public_id = data.get("media_public_id")
    media_url = data.get("media_url")
    media_type = data.get("media_type", "image")

    validation = validate_create_payload(media_public_id, media_url)
    if not validation.ok:
        return jsonify({"error": validation.error}), 400

    try:
        client = ensure_supabase()
        insert = {
            "caption": caption,
            "media_public_id": media_public_id,
            "media_url": media_url,
            "media_type": media_type,
            "author_id": request.user["id"],
            "author_email": request.user["email"],
            "author_name": request.user.get("name") or request.user["email"],
            "liked_by": [],
            "viewed_by": [],
        }
        result = client.table("posts").insert(insert).execute()
        rows = result.data or []
        if not rows:
            return jsonify({"error": "Failed to create post"}), 500
        POSTS_CREATED_TOTAL.inc()
        _event(
            "post_created",
            request_id=getattr(g, "request_id", None),
            post_id=rows[0].get("id"),
            author_id=request.user.get("id"),
        )
        return jsonify(serialize_post(rows[0], request.user["id"])), 201
    except Exception as e:
        return jsonify({"error": "Failed to create post", "details": str(e)}), 500

@app.get("/api/posts")
@requireAuth
def list_posts():
    try:
        client = ensure_supabase()
        result = client.table("posts").select("*").order("created_at", desc=True).execute()
        rows = result.data or []
        post_list = [serialize_post(row, request.user["id"]) for row in rows]
        return jsonify({"posts": post_list})
    except Exception as e:
        return jsonify({"error": "Failed to list posts", "details": str(e)}), 500

@app.post("/api/posts/<int:post_id>/like")
@requireAuth
def toggle_post_like(post_id):
    try:
        client = ensure_supabase()
        result = client.table("posts").select("*").eq("id", post_id).limit(1).execute()
        rows = result.data or []
        if not rows:
            return jsonify({"error": "Post not found"}), 404

        row = rows[0]
        user_id = int(request.user["id"])
        liked_by = _ids_as_ints(row.get("liked_by") or [])

        if user_id in liked_by:
            liked_by = [uid for uid in liked_by if uid != user_id]
        else:
            liked_by.append(user_id)

        updated = client.table("posts").update({"liked_by": liked_by}).eq("id", post_id).execute()
        updated_rows = updated.data or []
        if not updated_rows:
            return jsonify({"error": "Failed to update like"}), 500

        cache.clear()
        return jsonify(serialize_post(updated_rows[0], user_id))
    except Exception as e:
        return jsonify({"error": "Failed to toggle like", "details": str(e)}), 500

@app.post("/api/posts/<int:post_id>/view")
@requireAuth
def register_post_view(post_id):
    try:
        client = ensure_supabase()
        result = client.table("posts").select("*").eq("id", post_id).limit(1).execute()
        rows = result.data or []
        if not rows:
            return jsonify({"error": "Post not found"}), 404

        row = rows[0]
        user_id = int(request.user["id"])
        viewed_by = _ids_as_ints(row.get("viewed_by") or [])

        if user_id not in viewed_by:
            viewed_by.append(user_id)

        updated = client.table("posts").update({"viewed_by": viewed_by}).eq("id", post_id).execute()
        updated_rows = updated.data or []
        if not updated_rows:
            return jsonify({"error": "Failed to update view"}), 500

        cache.clear()
        return jsonify(serialize_post(updated_rows[0], user_id))
    except Exception as e:
        return jsonify({"error": "Failed to register view", "details": str(e)}), 500

@app.put("/api/posts/<int:post_id>")
@requireAuth
def update_post(post_id):
    data = request.get_json(silent=True) or {}

    try:
        client = ensure_supabase()
        result = client.table("posts").select("*").eq("id", post_id).limit(1).execute()
        rows = result.data or []
        if not rows:
            return jsonify({"error": "Post not found"}), 404

        row = rows[0]
        row_author_id = str(row.get("author_id"))
        current_user_id = str(request.user.get("id"))
        is_admin = request.user.get("role") == "admin"

        if not can_user_modify_post(current_user_id, row_author_id, request.user.get("role")):
            return jsonify({"error": "Forbidden"}), 403

        payload = {}
        if "caption" in data:
            payload["caption"] = normalize_caption(data.get("caption"))

        if "media_public_id" in data and "media_url" in data:
            new_public_id = data.get("media_public_id")
            new_media_url = data.get("media_url")
            new_media_type = data.get("media_type", row.get("media_type") or "image")
            if not new_public_id or not new_media_url:
                return jsonify({"error": "media_public_id and media_url are required when replacing media"}), 400

            old_public_id = row.get("media_public_id")
            old_media_type = row.get("media_type") or "image"
            if old_public_id and old_public_id != new_public_id:
                try:
                    cloudinary.uploader.destroy(old_public_id, invalidate=True, resource_type=old_media_type)
                except Exception:
                    pass

            payload["media_public_id"] = new_public_id
            payload["media_url"] = new_media_url
            payload["media_type"] = new_media_type

        if not payload:
            return jsonify(serialize_post(row, request.user["id"]))

        updated = client.table("posts").update(payload).eq("id", post_id).execute()
        updated_rows = updated.data or []
        if not updated_rows:
            return jsonify({"error": "Failed to update post"}), 500

        cache.clear()
        return jsonify(serialize_post(updated_rows[0], request.user["id"]))
    except Exception as e:
        return jsonify({"error": "Failed to update post", "details": str(e)}), 500

@app.delete("/api/posts/<int:post_id>")
@requireAuth
def delete_post(post_id):
    try:
        client = ensure_supabase()
        result = client.table("posts").select("*").eq("id", post_id).limit(1).execute()
        rows = result.data or []
        if not rows:
            return jsonify({"error": "Post not found"}), 404

        row = rows[0]
        row_author_id = str(row.get("author_id"))
        current_user_id = str(request.user.get("id"))
        is_admin = request.user.get("role") == "admin"

        if not can_user_modify_post(current_user_id, row_author_id, request.user.get("role")):
            return jsonify({"error": "Forbidden"}), 403

        public_id = row.get("media_public_id")
        media_type = row.get("media_type") or "image"
        if public_id:
            try:
                cloudinary.uploader.destroy(public_id, invalidate=True, resource_type=media_type)
            except Exception:
                pass

        client.table("posts").delete().eq("id", post_id).execute()
        cache.clear()
        return jsonify({"deleted": post_id})
    except Exception as e:
        return jsonify({"error": "Failed to delete post", "details": str(e)}), 500

@app.get("/users")
@requireAuth
def list_users():
    try:
        client = ensure_supabase()
        if request.user["role"] == "admin":
            result = client.table("users").select("*").order("id", desc=False).execute()
            rows = result.data or []
            return jsonify([normalize_user(row) for row in rows])
        return jsonify([request.user])
    except Exception as e:
        return jsonify({"error": "Failed to list users", "details": str(e)}), 500

@app.get("/users/me")
@requireAuth
def get_current_user():
    return jsonify(request.user)

@app.get("/users/<int:user_id>")
@requireAuth
def get_user(user_id):
    try:
        client = ensure_supabase()
        result = client.table("users").select("*").eq("id", user_id).limit(1).execute()
        rows = result.data or []
        if not rows:
            return jsonify({"error": "not found"}), 404

        user = normalize_user(rows[0])
        if request.user["role"] != "admin" and user["email"] != request.user["email"]:
            return jsonify({"error": "Forbidden"}), 403

        return jsonify(user)
    except Exception as e:
        return jsonify({"error": "Failed to get user", "details": str(e)}), 500

@app.put("/users/<int:user_id>")
@requireAuth
def update_user(user_id):
    try:
        client = ensure_supabase()
        result = client.table("users").select("*").eq("id", user_id).limit(1).execute()
        rows = result.data or []
        if not rows:
            return jsonify({"error": "not found"}), 404

        user = normalize_user(rows[0])
        if request.user["role"] != "admin" and user["email"] != request.user["email"]:
            return jsonify({"error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        payload = {}

        if "name" in data:
            payload["name"] = data["name"]
        if "email" in data and request.user["role"] == "admin":
            payload["email"] = data["email"]
        if "role" in data and request.user["role"] == "admin":
            payload["role"] = data["role"]

        if not payload:
            return jsonify(user)

        updated = client.table("users").update(payload).eq("id", user_id).execute()
        updated_rows = updated.data or []
        if not updated_rows:
            return jsonify({"error": "Update failed"}), 500

        return jsonify(normalize_user(updated_rows[0]))
    except Exception as e:
        return jsonify({"error": "Failed to update user", "details": str(e)}), 500

@app.delete("/users/<int:user_id>")
@requireAuth
def delete_user(user_id):
    try:
        client = ensure_supabase()
        result = client.table("users").select("*").eq("id", user_id).limit(1).execute()
        rows = result.data or []
        if not rows:
            return jsonify({"error": "not found"}), 404

        user = normalize_user(rows[0])
        if request.user["role"] != "admin" and user["email"] != request.user["email"]:
            return jsonify({"error": "Forbidden"}), 403

        client.table("users").delete().eq("id", user_id).execute()
        return jsonify({"deleted": user_id})
    except Exception as e:
        return jsonify({"error": "Failed to delete user", "details": str(e)}), 500

@app.post("/users")
@requireAuth
@requireAdmin
def create_user():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = data.get("email")
    role = data.get("role", "user")

    if not name or not email:
        return jsonify({"error": "name and email required"}), 400

    try:
        client = ensure_supabase()
        existing = client.table("users").select("id").eq("email", email).limit(1).execute()
        if existing.data:
            return jsonify({"error": "Email already exists"}), 400

        inserted = (
            client.table("users")
            .insert({"name": name, "email": email, "role": role})
            .execute()
        )
        rows = inserted.data or []
        if not rows:
            return jsonify({"error": "Failed to create user"}), 500
        return jsonify(normalize_user(rows[0])), 201
    except Exception as e:
        return jsonify({"error": "Failed to create user", "details": str(e)}), 500

if __name__ == "__main__":  # pragma: no cover
    app.run(port=8000, debug=True)
