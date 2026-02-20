import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import "./Pages.css";

const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

function Account() {
    const location = useLocation();
    const frontendOrigin = encodeURIComponent(window.location.origin);

    const [user, setUser] = useState(null);
    const [allUsers, setAllUsers] = useState([]);
    const [message, setMessage] = useState("Checking session...");
    const [adminError, setAdminError] = useState("");
    const [deletingUserId, setDeletingUserId] = useState(null);

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        if (params.get("error") === "oauth_state_mismatch") {
            setMessage("Sign-in expired or mismatched. Please try login again from this page.");
            return;
        }

        const fetchSessionUser = async () => {
            try {
                const meResponse = await fetch(`${API_BASE}/users/me`, {
                    credentials: "include"
                });
                const meData = await meResponse.json();

                if (!meResponse.ok || !meData?.email) {
                    setUser(null);
                    setAllUsers([]);
                    setMessage("You are not logged in.");
                    return;
                }

                const currentUser = meData;
                setUser(currentUser);
                setMessage(currentUser ? "Logged in" : "You are not logged in.");

                if (currentUser?.role === "admin") {
                    try {
                        const usersResponse = await fetch(`${API_BASE}/users`, {
                            credentials: "include"
                        });
                        const usersData = await usersResponse.json();
                        if (!usersResponse.ok) {
                            throw new Error(usersData.details || usersData.error || "Failed to load accounts");
                        }
                        setAllUsers(Array.isArray(usersData) ? usersData : []);
                        setAdminError("");
                    } catch (error) {
                        setAllUsers([]);
                        setAdminError(error.message || "Failed to load accounts");
                    }
                } else {
                    setAllUsers([]);
                    setAdminError("");
                }
            } catch (error) {
                setUser(null);
                setAllUsers([]);
                setAdminError("");
                setMessage(error.message || "Could not verify session.");
            }
        };

        fetchSessionUser();
    }, [location.search]);

    const handleDeleteUser = async (userId) => {
        const shouldDelete = window.confirm("Delete this account? This action cannot be undone.");
        if (!shouldDelete) return;

        try {
            setDeletingUserId(userId);
            setAdminError("");
            const response = await fetch(`${API_BASE}/users/${userId}`, {
                method: "DELETE",
                credentials: "include"
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.details || data.error || "Failed to delete account");
            }

            setAllUsers((prev) => prev.filter((u) => u.id !== userId));
            if (user && user.id === userId) {
                window.location.href = `${API_BASE}/auth/logout?frontend_origin=${frontendOrigin}`;
            }
        } catch (error) {
            setAdminError(error.message || "Failed to delete account");
        } finally {
            setDeletingUserId(null);
        }
    };

    return (
        <div className="feature-page">
            <h1 className="feature-title">Account</h1>
            <p className="feature-subtitle">Manage your login session.</p>

            <div className="feature-controls">
                <a className="feature-btn" href={`${API_BASE}/auth/logout?frontend_origin=${frontendOrigin}`}>Log Out</a>
            </div>

            <article className="feature-card vertical">
                <h2>Session Status</h2>
                {user ? (
                    <>
                        <p><strong>Name:</strong> {user.name || "N/A"}</p>
                        <p><strong>Email:</strong> {user.email}</p>
                        <p><strong>Role:</strong> {user.role || "user"}</p>
                    </>
                ) : (
                    <p>{message}</p>
                )}
            </article>

            {user?.role === "admin" ? (
                <article className="feature-card vertical admin-users-card">
                    <h2>Admin: Manage Accounts</h2>
                    {adminError ? <p className="feature-message">{adminError}</p> : null}

                    <div className="admin-users-list">
                        {allUsers.map((account) => (
                            <div key={account.id} className="admin-user-row">
                                <div>
                                    <p><strong>{account.name || "No name"}</strong></p>
                                    <p>{account.email}</p>
                                    <p>Role: {account.role || "user"}</p>
                                </div>
                                <button
                                    type="button"
                                    className="post-delete-btn"
                                    onClick={() => handleDeleteUser(account.id)}
                                    disabled={deletingUserId === account.id}
                                >
                                    {deletingUserId === account.id ? "Deleting..." : "Delete Account"}
                                </button>
                            </div>
                        ))}
                    </div>
                </article>
            ) : null}
        </div>
    );
}

export default Account;