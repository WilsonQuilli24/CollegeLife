import { useState, useRef } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import "./component.css";
import logo from "../assets/CollegeLifeLogo.png";

const MotionLi = motion.li;

function Navbar() {
    const navigate = useNavigate();

    return (
        <div className="navbar-div">
            <img src={logo} alt="CollegeLife Logo" className="navbar-logo" onClick={() => navigate("/")}/>
            <SlideTabs />
        </div>
    );
}

const SlideTabs = () => {
    const navigate = useNavigate();
    const [position, setPosition] = useState({
        left: 0,
        width: 0,
        opacity: 0,

    });

    return (
        <ul className="nav-links" onMouseLeave={() => {
                setPosition((pv) => ({
                    ...pv,
                    opacity: 0,
                }));
            }}>
           
            <Tab setPosition={setPosition} onClick={() => navigate("/")}>Home</Tab>
            <Tab setPosition={setPosition} onClick={() => navigate("/posts")}>Posts</Tab>
            <Tab setPosition={setPosition} onClick={() => navigate("/music")}>Music</Tab>
            <Tab setPosition={setPosition} onClick={() => navigate("/restaurants")}>Restaurants</Tab>
            <Tab setPosition={setPosition} onClick={() => navigate("/weather")}>Weather</Tab>
            <Tab setPosition={setPosition} onClick={() => navigate("/account")}>Account</Tab>

            <Cursor position={position} />
        </ul>
    );
};

const Tab = ({ children, setPosition, onClick }) => {
    const ref = useRef(null);

    return (
        <li
            ref={ref}
            className="nav-children"
            onClick={onClick}
            onMouseEnter={() => {
                if (!ref.current) return;
                const { width } = ref.current.getBoundingClientRect();

                setPosition({
                    width,
                    opacity: 1,
                    left: ref.current.offsetLeft,
                });
            }}
        >
            {children}
        </li>
    );
};

const Cursor = ({ position }) => {
    return (
        <MotionLi
            className="cursor"
            animate={{
                left: position.left,
                width: position.width,
                opacity: position.opacity,
            }}

            transition={{
                type: "spring",
                stiffness: 400,
                damping: 30,
            }}
        />
    );
};


export default Navbar;