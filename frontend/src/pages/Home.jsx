import "./Pages.css";
import temple_post from "../assets/Temple_Post.png";
import psu_post from "../assets/PSU_Post.png";
import drexel_post from "../assets/Drexel_Post.png";
import album_cover_1 from "../assets/album_cover_1.png";
import album_cover_2 from "../assets/album_cover_2.jpg";
import album_cover_3 from "../assets/album_cover_3.webp";
import { FaSpotify, FaYelp, FaSun, FaGoogle } from "react-icons/fa";
import restaurant_1 from "../assets/restaurants_1.jpg";
import restaurant_2 from "../assets/restaurants_2.jpeg";
import restaurant_3 from "../assets/restaurants_3.jpg";
import weather_1 from "../assets/weather_1.webp";
import weather_2 from "../assets/weather_2.jpg";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

function Home() {
    const navigate = useNavigate();
    const [currentUser, setCurrentUser] = useState(null);

    const goToGoogleLogin = () => {
        const frontendOrigin = encodeURIComponent(window.location.origin);
        window.location.href = `${API_BASE}/auth/login?frontend_origin=${frontendOrigin}`;
    };

    useEffect(() => {
        const bootstrapSession = async () => {
            const params = new URLSearchParams(window.location.search);
            const justLoggedIn = params.get("just_logged_in") === "1";

            if (justLoggedIn) {
                const cleanPath = window.location.pathname;
                window.history.replaceState({}, "", cleanPath);
            }

            const alreadyReset = sessionStorage.getItem("initial_session_reset_done") === "1";
            if (!justLoggedIn && !alreadyReset) {
                try {
                    await fetch(`${API_BASE}/auth/reset-session`, {
                        credentials: "include"
                    });
                } catch (_error) {
                    // Ignore bootstrap reset failures and continue.
                }
                sessionStorage.setItem("initial_session_reset_done", "1");
            }
        };

        const fetchCurrentUser = async () => {
            try {
                const response = await fetch(`${API_BASE}/users/me`, {
                    credentials: "include"
                });
                const data = await response.json();
                if (!response.ok || !data?.email) {
                    setCurrentUser(null);
                    return;
                }
                setCurrentUser(data);
            } catch (_error) {
                setCurrentUser(null);
            }
        };

        const initialize = async () => {
            await bootstrapSession();
            await fetchCurrentUser();
        };

        initialize();
    }, []);

    return (
        <>
        <div>

            <h1 className="page-intro"> CollegeLife </h1>

            <div className="Sign-in">
                <button className="Sign-in-Buttons" onClick={currentUser ? undefined : goToGoogleLogin}>
                    {currentUser ? `Welcome ${currentUser.name || currentUser.email}` : <>Log in with Google <FaGoogle /></>}
                </button>
            </div>

            <div className="Posts-section">
                <h2 className="page-intro-sub"> View Other Posts </h2>
                <p> View posts from people from other universities! </p>
                <button onClick={() => navigate("/posts")}> Go to Posts </button>
                <div className="posts-images">
                    <img src={temple_post} alt="Temple U" />
                    <img src={drexel_post} alt="Drexel U" />
                    <img src={psu_post} alt="PSU Post" />
                </div>
            </div>

            <div className="Music-section">
                <h2 className="page-intro-sub">
                    See What Music Others are Listening to via Spotify <FaSpotify />
                </h2>
                <p> Share what music you're listening to </p>
                <button onClick={() => navigate("/music")}> Go to Music </button>
                <div className="music-images">
                    <img src={album_cover_1} alt="DTMF Cover" />
                    <img src={album_cover_2} alt="Gabriela Cover" />
                    <img src={album_cover_3} alt="Chromakopia Cover" />
                </div>
            </div>

            <div className="Restaurants-section">
                <h2 className="page-intro-sub"> Restaurants <FaYelp /> </h2>
                <button onClick={() => navigate("/restaurants")}> Go to Restaurants </button>
                <div className="restaurant-images">
                    <img src={restaurant_1} alt="Panera Bread" />
                    <img src={restaurant_2} alt="Crumbl Cookies" />
                    <img src={restaurant_3} alt="Senor Salsa" />
                </div>
            </div>

            <div className="Weather-section">
                <h2 className="page-intro-sub"> Weather <FaSun /> </h2>
                <button onClick={() => navigate("/weather")}> Go to Weather </button>
                <div className="weather-images">
                    <img src={weather_1} alt="Sunny Day" />
                    <img src={weather_2} alt="Rainy Day" />
                </div>
            </div>
        </div>
        </>
    );
}

export default Home;