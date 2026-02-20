import { useEffect, useMemo, useState } from "react";
import "./Pages.css";

const API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

function Posts() {
    const [posts, setPosts] = useState([]);
    const [currentUser, setCurrentUser] = useState(null);
    const [caption, setCaption] = useState("");
    const [file, setFile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [editingPostId, setEditingPostId] = useState(null);
    const [editCaption, setEditCaption] = useState("");
    const [editSubmitting, setEditSubmitting] = useState(false);
    const [error, setError] = useState("");

    const selectedFileLabel = useMemo(() => {
        if (!file) return "No file selected";
        return `${file.name} (${Math.round(file.size / 1024)} KB)`;
    }, [file]);

    const fetchPosts = async () => {
        try {
            setError("");
            const response = await fetch(`${API_BASE}/api/posts`, {
                credentials: "include"
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Failed to fetch posts");
            setPosts(data.posts || []);
        } catch (err) {
            setError(err.message || "Failed to fetch posts");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPosts();

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

        fetchCurrentUser();
    }, []);

    const handleCreatePost = async (event) => {
        event.preventDefault();
        if (!file) {
            setError("Please choose a photo or video to upload.");
            return;
        }

        try {
            setSubmitting(true);
            setError("");

            const resourceType = file.type.startsWith("video/") ? "video" : "image";
            const uploadBody = new FormData();
            uploadBody.append("file", file);
            uploadBody.append("resource_type", resourceType);

            const uploadResponse = await fetch(`${API_BASE}/api/media/upload`, {
                method: "POST",
                body: uploadBody,
                credentials: "include"
            });

            const uploadData = await uploadResponse.json();
            if (!uploadResponse.ok) {
                throw new Error(uploadData.details || uploadData.error || "Upload failed");
            }

            const createResponse = await fetch(`${API_BASE}/api/posts`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    caption,
                    media_public_id: uploadData.public_id,
                    media_url: uploadData.url,
                    media_type: uploadData.type
                })
            });

            const createData = await createResponse.json();
            if (!createResponse.ok) {
                throw new Error(createData.details || createData.error || "Failed to create post");
            }

            setPosts((prev) => [createData, ...prev]);
            setCaption("");
            setFile(null);
        } catch (err) {
            setError(err.message || "Failed to publish post");
        } finally {
            setSubmitting(false);
        }
    };

    const handleToggleLike = async (postId) => {
        try {
            const response = await fetch(`${API_BASE}/api/posts/${postId}/like`, {
                method: "POST",
                credentials: "include"
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Failed to like post");
            setPosts((prev) => prev.map((post) => (post.id === postId ? data : post)));
        } catch (err) {
            setError(err.message || "Failed to like post");
        }
    };

    const handleRegisterView = async (postId) => {
        try {
            const response = await fetch(`${API_BASE}/api/posts/${postId}/view`, {
                method: "POST",
                credentials: "include"
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Failed to register view");
            setPosts((prev) => prev.map((post) => (post.id === postId ? data : post)));
        } catch (err) {
            setError(err.message || "Failed to register view");
        }
    };

    const handleDeletePost = async (postId) => {
        const shouldDelete = window.confirm("Delete this post? This cannot be undone.");
        if (!shouldDelete) return;

        try {
            const response = await fetch(`${API_BASE}/api/posts/${postId}`, {
                method: "DELETE",
                credentials: "include"
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.details || data.error || "Failed to delete post");
            }

            setPosts((prev) => prev.filter((post) => post.id !== postId));
        } catch (err) {
            setError(err.message || "Failed to delete post");
        }
    };

    const handleStartEdit = (post) => {
        setEditingPostId(post.id);
        setEditCaption(post.caption || "");
        setError("");
    };

    const handleCancelEdit = () => {
        setEditingPostId(null);
        setEditCaption("");
    };

    const handleSaveEdit = async (postId) => {
        try {
            setEditSubmitting(true);
            const response = await fetch(`${API_BASE}/api/posts/${postId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ caption: editCaption })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.details || data.error || "Failed to update post");
            }

            setPosts((prev) => prev.map((post) => (post.id === postId ? data : post)));
            handleCancelEdit();
        } catch (err) {
            setError(err.message || "Failed to update post");
        } finally {
            setEditSubmitting(false);
        }
    };

    const canDeletePost = (post) => {
        if (!currentUser) return false;
        if (currentUser.role === "admin") return true;
        return String(post.author?.id) === String(currentUser.id);
    };

    return (
        <div className="posts-page">
            <h1 className="page-intro">Campus Posts</h1>

            <form className="post-upload-card" onSubmit={handleCreatePost}>
                <h2>Upload a photo or video</h2>
                <textarea
                    className="post-caption-input"
                    placeholder="Add a caption..."
                    value={caption}
                    onChange={(e) => setCaption(e.target.value)}
                    maxLength={250}
                />

                <label className="post-file-picker" htmlFor="post-file-input">
                    Select file
                </label>
                <input
                    id="post-file-input"
                    type="file"
                    accept="image/*,video/*"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    hidden
                />
                <p className="file-label">{selectedFileLabel}</p>

                <button className="post-submit-btn" type="submit" disabled={submitting}>
                    {submitting ? "Publishing..." : "Publish Post"}
                </button>
            </form>

            {error && <p className="post-error">{error}</p>}

            {loading ? (
                <p className="posts-loading">Loading posts...</p>
            ) : (
                <div className="post-feed">
                    {posts.map((post, index) => (
                        <article
                            key={post.id}
                            className="post-card"
                            style={{ animationDelay: `${index * 0.15}s` }}
                        >
                            <div className="post-card-header">
                                <strong>{post.author?.name || "Anonymous"}</strong>
                                <span>{new Date(post.created_at).toLocaleString()}</span>
                            </div>

                            {post.media?.type === "video" ? (
                                <video
                                    className="post-media"
                                    controls
                                    onPlay={() => handleRegisterView(post.id)}
                                    src={post.media.url}
                                />
                            ) : (
                                <img
                                    className="post-media"
                                    src={post.media?.url}
                                    alt={post.caption || "User post"}
                                    onClick={() => handleRegisterView(post.id)}
                                />
                            )}

                            {post.caption && <p className="post-caption">{post.caption}</p>}

                            {editingPostId === post.id ? (
                                <div className="post-edit-box">
                                    <textarea
                                        className="post-caption-input"
                                        value={editCaption}
                                        onChange={(e) => setEditCaption(e.target.value)}
                                        maxLength={250}
                                    />
                                    <div className="post-edit-actions">
                                        <button type="button" onClick={() => handleSaveEdit(post.id)} disabled={editSubmitting}>
                                            {editSubmitting ? "Saving..." : "Save"}
                                        </button>
                                        <button type="button" onClick={handleCancelEdit} disabled={editSubmitting}>
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                            ) : null}

                            <div className="post-actions">
                                <button type="button" onClick={() => handleToggleLike(post.id)}>
                                    {post.liked_by_me ? "Unlike" : "Like"} ({post.likes})
                                </button>
                                <span>{post.views} views</span>
                                {canDeletePost(post) ? (
                                    <button type="button" onClick={() => handleStartEdit(post)}>
                                        Edit
                                    </button>
                                ) : null}
                                {canDeletePost(post) ? (
                                    <button type="button" className="post-delete-btn" onClick={() => handleDeletePost(post.id)}>
                                        Delete
                                    </button>
                                ) : null}
                            </div>
                        </article>
                    ))}
                </div>
            )}
        </div>
    );
}

export default Posts;
