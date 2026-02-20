import { useEffect, useState } from "react";
import "./Pages.css";

const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

function Music() {
    const [track, setTrack] = useState(null);
    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);
    const frontendOrigin = encodeURIComponent(window.location.origin);

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const error = params.get("error");
        const connected = params.get("spotify_connected");
        if (connected === "1") {
            setMessage("Spotify connected. You can now fetch your current track.");
        } else if (error === "spotify_state_mismatch") {
            setMessage("Spotify sign-in expired. Please click Connect Spotify again.");
        } else if (error === "spotify_callback_failed" || error === "spotify_authorize_failed") {
            setMessage("Spotify authentication failed. Verify Spotify app redirect URI and try again.");
        }
    }, []);

    const fetchCurrentTrack = async () => {
        try {
            setLoading(true);
            setMessage("");

            const response = await fetch(`${API_BASE}/spotify/current`, {
                credentials: "include"
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || data.message || "Failed to fetch current Spotify track");
            }

            if (data.message) {
                setTrack(null);
                setMessage(data.message);
                return;
            }

            setTrack(data);
        } catch (error) {
            setTrack(null);
            setMessage(error.message || "Failed to fetch current Spotify track");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="feature-page">
            <h1 className="page-intro">Music</h1>
            <p className="feature-subtitle">See what is currently playing on your Spotify account.</p>
            <p className="feature-subtitle">Spotify Premium is required for full playback/current-track access.</p>

            <div className="feature-controls">
                <a className="feature-btn" href={`${API_BASE}/auth/spotify?frontend_origin=${frontendOrigin}`}>
                    Connect Spotify
                </a>
                <button type="button" className="feature-btn" onClick={fetchCurrentTrack} disabled={loading}>
                    {loading ? "Loading..." : "Get Current Track"}
                </button>
            </div>

            {message ? <p className="feature-message">{message}</p> : null}

            {track ? (
                <article className="feature-card">
                    <img className="music-album-image" src={track.album_image} alt={`${track.album} cover`} />
                    <div>
                        <h2>{track.name}</h2>
                        <p><strong>Artist(s):</strong> {track.artists?.join(", ")}</p>
                        <p><strong>Album:</strong> {track.album}</p>
                        <a className="feature-link" href={track.external_url} target="_blank" rel="noreferrer">
                            Open in Spotify
                        </a>
                    </div>
                </article>
            ) : null}
        </div>
    );
}

export default Music;