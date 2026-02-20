import "./component.css";
import { FaGithub, FaLinkedin } from "react-icons/fa";

const Footer = () => {
    return (
        <footer className="footer">
            <div className="footer-container">
                <div className="footer-section">
                    <h2>About Me</h2>
                    <p>
                        CollegeLife is a platform designed to help students
                        manage their daily life, explore music, weather,
                        restaurants, and stay connected.
                    </p>
                </div>

                <div className="footer-section">
                    <h2>Quick Links</h2>
                    <ul>
                        <li><a href="/">Home</a></li>
                        <li><a href="/posts">Posts</a></li>
                        <li><a href="/music">Music</a></li>
                        <li><a href="/restaurants">Restaurants</a></li>
                        <li><a href="/weather">Weather</a></li>
                        <li><a href="/account">Account</a></li>
                    </ul>
                </div>

                <div className="footer-section">
                    <h2>Check These Out!</h2>
                    <ul className="social-links">
                        <li>
                            <FaGithub /> <a href="https://github.com/wilsonquilli" target = "_blank">GitHub</a></li>
                        <li>
                            <FaLinkedin /> <a href="https://www.linkedin.com/in/wilson-quilli-8469b4291/" target = "_blank">LinkedIn</a></li>
                    </ul>
                </div>
            </div>

            <div className="footer-bottom">
                <p>
                    © 2026 Wilson Quilli. All Rights Reserved.
                </p>
            </div>
        </footer>
    );
};

export default Footer;