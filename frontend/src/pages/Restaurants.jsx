import { useState } from "react";
import "./Pages.css";

const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

function Restaurants() {
    const [location, setLocation] = useState("Philadelphia");
    const [term, setTerm] = useState("restaurant");
    const [businesses, setBusinesses] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleSearch = async (event) => {
        event.preventDefault();
        if (!location.trim()) {
            setError("Please enter a location.");
            return;
        }

        try {
            setLoading(true);
            setError("");

            const params = new URLSearchParams({
                location: location.trim(),
                term: term.trim() || "restaurant",
                limit: "8"
            });

            const response = await fetch(`${API_BASE}/api/yelp?${params.toString()}`, {
                credentials: "include"
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Failed to fetch restaurants");
            }

            setBusinesses(data.businesses || []);
        } catch (err) {
            setBusinesses([]);
            setError(err.message || "Failed to fetch restaurants");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="feature-page">
            <h1 className="page-intro">Restaurants</h1>
            <p className="feature-subtitle">Discover places to eat using Yelp data.</p>

            <form className="feature-form" onSubmit={handleSearch}>
                <input
                    type="text"
                    className="feature-input"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                    placeholder="City or area"
                />
                <input
                    type="text"
                    className="feature-input"
                    value={term}
                    onChange={(event) => setTerm(event.target.value)}
                    placeholder="Search term"
                />
                <button type="submit" className="feature-btn" disabled={loading}>
                    {loading ? "Searching..." : "Search"}
                </button>
            </form>

            {error ? <p className="feature-message">{error}</p> : null}

            <div className="feature-grid">
                {businesses.map((business) => (
                    <article key={`${business.name}-${business.address}`} className="feature-card vertical">
                        {business.image_url ? (
                            <img className="restaurant-image" src={business.image_url} alt={business.name} />
                        ) : null}
                        <div>
                            <h3>{business.name}</h3>
                            <p><strong>Rating:</strong> {business.rating ?? "N/A"}</p>
                            <p><strong>Reviews:</strong> {business.review_count ?? "N/A"}</p>
                            <p><strong>Address:</strong> {business.address || "N/A"}</p>
                            <p><strong>Phone:</strong> {business.phone || "N/A"}</p>
                            {business.url ? (
                                <a className="feature-link" href={business.url} target="_blank" rel="noreferrer">
                                    View on Yelp
                                </a>
                            ) : null}
                        </div>
                    </article>
                ))}
            </div>
        </div>
    );
}

export default Restaurants;
