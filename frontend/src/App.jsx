import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Posts from "./pages/Posts";
import Music from "./pages/Music";
import Restaurants from "./pages/Restaurants";
import Weather from "./pages/Weather";
import Account from "./pages/Account";
import Footer from "./components/Footer";

function App() {
    return (
        <BrowserRouter>
            <Navbar />
            <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/posts" element={<Posts />} />
                <Route path="/music" element={<Music />} />
                <Route path="/restaurants" element={<Restaurants />} />
                <Route path="/weather" element={<Weather />} />
                <Route path="/account" element={<Account />} />
            </Routes>
            <Footer />
        </BrowserRouter>
    );
}

export default App;
