import os
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, redirect, url_for, session
from flask_cors import CORS
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
from functools import wraps
import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache

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

CORS(app, origins=["http://localhost:3000"], supports_credentials=True)

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
    client_kwargs={"scope": "user-read-playback-state user-read-currently-playing streaming user-modify-playback-state"}
)

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

users = {}
next_user_id = 1

limiter = Limiter(
    app,
    key_func=get_remote_address,  
    default_limits=["200 per day", "50 per hour"]
)

def requireAuth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_email = session.get("user")
        if not user_email:
            return jsonify({"error": "Unauthorized", "message": "Valid access token is required"}), 401
        request.user = None
        for user in users.values():
            if user["email"] == user_email:
                request.user = user
                break
        if not request.user:
            return jsonify({"error": "User not found"}), 401
        return f(*args, **kwargs)
    return decorated

def requireAdmin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.user.get("role") != "admin":
            return jsonify({"error": "Forbidden", "message": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

def get_spotify_headers():
    token = session.get("spotify_token")
    if not token:
        return None
    expires_at = token.get("expires_at")
    if expires_at and datetime.utcnow().timestamp() > expires_at:
        new_token = spotify.refresh_token(
            token_url=spotify.access_token_url,
            refresh_token=token["refresh_token"]
        )
        new_token["expires_at"] = datetime.utcnow().timestamp() + new_token["expires_in"]
        session["spotify_token"] = new_token
        token = new_token
    return {"Authorization": f"Bearer {token['access_token']}"}

@app.get("/health")
def health_check():
    return jsonify({"status": "ok"}), 200

@app.route("/auth/login")
def login():
    redirect_uri = url_for("auth_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.get("/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})

@app.route("/auth/callback")
def auth_callback():
    global next_user_id
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.userinfo()
    email = user_info["email"]
    allowed_domains = os.getenv("ALLOWED_DOMAINS", "").split(",")
    domain = email.split("@")[1]

    if allowed_domains and allowed_domains != [''] and domain not in allowed_domains:
        return jsonify({"error": "Must use school email"}), 403

    session["user"] = email
    existing_user = None
    for user in users.values():
        if user["email"] == email:
            existing_user = user
            break

    if not existing_user:
        users[next_user_id] = {
            "id": next_user_id,
            "email": email,
            "name": user_info.get("name"),
            "role": "user",
            "created_at": datetime.utcnow().isoformat()
        }
        next_user_id += 1

    return jsonify({"message": "Login successful", "email": email, "name": user_info.get("name")})

@app.get("/api/hello")
@requireAuth
def hello():
    return jsonify({"message": f"Hello, {request.user['email']}!"})

@app.get("/api/server-time")
@requireAuth
@cache.cached(timeout=300, query_string=True)
def server_time():
    return jsonify({"serverTime": datetime.utcnow().isoformat() + "Z"})

@app.route("/api/university")
@cache.cached(timeout=600, query_string=True) 
def get_university():
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
def get_weather():
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
            "icon": f"http://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png"
        }
        return jsonify(weather_info)
    except requests.RequestException as e:
        return jsonify({"error": "Weather API request failed", "details": str(e)}), 502
    except (KeyError, IndexError):
        return jsonify({"error": "Unexpected response format from weather API"}), 500

@app.route("/auth/spotify")
@requireAuth
def spotify_login():
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    return spotify.authorize_redirect(redirect_uri)

@app.route("/api/spotify/callback")
@requireAuth
def spotify_callback():
    token = spotify.authorize_access_token()
    token["expires_at"] = datetime.utcnow().timestamp() + token["expires_in"]
    session["spotify_token"] = token
    return redirect("/spotify/current")

@app.get("/spotify/current")
@requireAuth
@limiter.limit("15 per minute")
@cache.cached(timeout=300, query_string=True)  
def spotify_current_track():
    headers = get_spotify_headers()
    if not headers:
        return jsonify({"error": "Spotify not authenticated"}), 401

    url = "https://api.spotify.com/v1/me/player/currently-playing"
    response = requests.get(url, headers=headers)
    if response.status_code == 204:
        return jsonify({"message": "No track currently playing"}), 200
    if response.status_code == 403:
        return jsonify({"message": "Spotify Premium required"}), 403
    if response.status_code != 200:
        return jsonify({"error": "Failed to get current track", "details": response.text}), response.status_code

    data = response.json()
    track_info = {
        "name": data["item"]["name"],
        "artists": [artist["name"] for artist in data["item"]["artists"]],
        "album": data["item"]["album"]["name"],
        "album_image": data["item"]["album"]["images"][0]["url"],
        "progress_ms": data["progress_ms"],
        "duration_ms": data["item"]["duration_ms"],
        "external_url": data["item"]["external_urls"]["spotify"]
    }
    return jsonify(track_info)

@app.get("/api/spotify/token")
@requireAuth
def get_spotify_token():
    headers = get_spotify_headers()
    if not headers:
        return jsonify({"error": "Spotify not authenticated"}), 401
    token = session.get("spotify_token")
    return jsonify({"access_token": token["access_token"]})

@app.route("/api/yelp")
@requireAuth
@limiter.limit("5 per minute")  
@cache.cached(timeout=300, query_string=True)
def get_yelp_restaurants():
    location = request.args.get("location")
    term = request.args.get("term", "restaurant")
    limit = request.args.get("limit", 5)

    if not location:
        return jsonify({"error": "location parameter is required"}), 400

    url = "https://api.yelp.com/v3/businesses/search"
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    params = {
        "term": term,
        "location": location,
        "limit": limit
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        businesses = []
        for biz in data.get("businesses", []):
            businesses.append({
                "name": biz["name"],
                "rating": biz.get("rating"),
                "review_count": biz.get("review_count"),
                "address": " ".join(biz.get("location", {}).get("display_address", [])),
                "phone": biz.get("display_phone"),
                "url": biz.get("url"),
                "image_url": biz.get("image_url")
            })

        return jsonify({"businesses": businesses})

    except requests.RequestException as e:
        return jsonify({"error": "Yelp API request failed", "details": str(e)}), 502

@app.post("/api/media/upload")
@requireAuth
def upload_media():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    resource_type = request.form.get("resource_type", "image") 
    try:
        result = cloudinary.uploader.upload(
            file,
            resource_type=resource_type,
            folder=f"college_life/{request.user['id']}/"
        )
        return jsonify({
            "public_id": result["public_id"],
            "url": result["secure_url"],
            "type": result["resource_type"]
        })
    except Exception as e:
        return jsonify({"error": "Upload failed", "details": str(e)}), 500

@app.get("/api/media")
@requireAuth
@cache.cached(timeout=300, query_string=True)
def list_media():
    try:
        result = cloudinary.api.resources(
            type="upload",
            prefix=f"college_life/{request.user['id']}/"
        )
        files = [{
            "public_id": f["public_id"],
            "url": f["secure_url"],
            "type": f["resource_type"]
        } for f in result.get("resources", [])]
        return jsonify({"media": files})
    except Exception as e:
        return jsonify({"error": "Failed to list media", "details": str(e)}), 500

@app.put("/api/media/<public_id>")
@requireAuth
def edit_media(public_id):
    data = request.get_json()
    try:
        result = cloudinary.api.update(
            public_id,
            folder=data.get("folder")
        )
        return jsonify({"updated": result})
    except Exception as e:
        return jsonify({"error": "Update failed", "details": str(e)}), 500

@app.delete("/api/media/<public_id>")
@requireAuth
def delete_media(public_id):
    try:
        cloudinary.uploader.destroy(public_id, invalidate=True)
        return jsonify({"deleted": public_id})
    except Exception as e:
        return jsonify({"error": "Delete failed", "details": str(e)}), 500


@app.get("/users")
@requireAuth
@cache.cached(timeout=300, query_string=True)
def list_users():
    if request.user["role"] == "admin":
        return jsonify(list(users.values()))
    return jsonify([request.user])

@app.get("/users/<int:user_id>")
@requireAuth
def get_user(user_id):
    user = users.get(user_id)
    if not user:
        return jsonify({"error": "not found"}), 404
    if request.user["role"] != "admin" and user["email"] != request.user["email"]:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(user)

@app.put("/users/<int:user_id>")
@requireAuth
def update_user(user_id):
    user = users.get(user_id)
    if not user:
        return jsonify({"error": "not found"}), 404
    if request.user["role"] != "admin" and user["email"] != request.user["email"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    if "role" in data and request.user["role"] != "admin":
        data.pop("role")
    user.update(data)
    return jsonify(user)

@app.delete("/users/<int:user_id>")
@requireAuth
def delete_user(user_id):
    user = users.get(user_id)
    if not user:
        return jsonify({"error": "not found"}), 404
    if request.user["role"] != "admin" and user["email"] != request.user["email"]:
        return jsonify({"error": "Forbidden"}), 403
    del users[user_id]
    return jsonify({"deleted": user_id})

@app.post("/users")
@requireAuth
@requireAdmin
def create_user():
    global next_user_id
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = data.get("email")
    role = data.get("role", "user")
    if not name or not email:
        return jsonify({"error": "name and email required"}), 400
    for u in users.values():
        if u["email"] == email:
            return jsonify({"error": "Email already exists"}), 400
    user = {"id": next_user_id, "name": name, "email": email, "role": role, "created_at": datetime.utcnow().isoformat()}
    users[next_user_id] = user
    next_user_id += 1
    return jsonify(user), 201

if __name__ == "__main__":
    app.run(port=8000, debug=True)