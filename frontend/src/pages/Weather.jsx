import { useEffect, useState } from "react";
import "./Pages.css";

const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

function Weather() {
    const [city, setCity] = useState("Philadelphia");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [weather, setWeather] = useState(null);

    const fetchWeather = async (cityName) => {
        try {
            setLoading(true);
            setError("");
            const params = new URLSearchParams({ city: cityName });
            const response = await fetch(`${API_BASE}/api/weather?${params.toString()}`, {
                credentials: "include"
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Failed to fetch weather data");
            }
            setWeather(data);
        } catch (err) {
            setWeather(null);
            setError(err.message || "Failed to fetch weather data");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchWeather("Philadelphia");
    }, []);

    const handleSubmit = (event) => {
        event.preventDefault();
        if (!city.trim()) {
            setError("Please enter a city.");
            return;
        }
        fetchWeather(city.trim());
    };

    return (
        <div className="feature-page">
            <h1 className="page-intro">Weather</h1>
            <p className="feature-subtitle">Check current conditions by city.</p>

            <form className="feature-form" onSubmit={handleSubmit}>
                <input
                    type="text"
                    className="feature-input"
                    value={city}
                    onChange={(event) => setCity(event.target.value)}
                    placeholder="Enter city"
                />
                <button type="submit" className="feature-btn" disabled={loading}>
                    {loading ? "Loading..." : "Get Weather"}
                </button>
            </form>

            {error ? <p className="feature-message">{error}</p> : null}

            {weather ? (
                <article className="feature-card">
                    <div>
                        <h2>{weather.city}, {weather.country}</h2>
                        <p><strong>Condition:</strong> {weather.description}</p>
                        <p><strong>Temperature:</strong> {weather.temperature}°F</p>
                        <p><strong>Feels Like:</strong> {weather.feels_like}°F</p>
                        <p><strong>Humidity:</strong> {weather.humidity}%</p>
                        <p><strong>Wind:</strong> {weather.wind_speed} mph</p>
                    </div>
                    {weather.icon ? <img className="weather-icon" src={weather.icon} alt={weather.description} /> : null}
                </article>
            ) : null}
        </div>
    );

}

export default Weather;
