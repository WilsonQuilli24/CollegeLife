import { useEffect, useState } from "react";

function Weather() {

    const [weather, setWeather] = useState(null);


    useEffect(() => {

        fetch("http://localhost:8000/api/weather?city=Philadelphia", {

            credentials: "include",

        })

        .then(res => res.json())

        .then(data => setWeather(data));

    }, []);


    if (!weather) return <p>Loading...</p>;


    return (

        <div>

            <h1>Weather</h1>

            <p>{weather.city}</p>

            <p>{weather.temperature}°F</p>

            <p>{weather.description}</p>

        </div>

    );

}

export default Weather;