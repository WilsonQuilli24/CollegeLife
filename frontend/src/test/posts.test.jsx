import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Posts from "../pages/Posts";

function mockFetchWithRoutes(routes) {
  vi.spyOn(global, "fetch").mockImplementation(async (url, options = {}) => {
    const key = `${options.method || "GET"} ${url}`;
    const handler = routes[key] || routes[url];
    if (!handler) {
      throw new Error(`No mock for ${key}`);
    }
    return handler(url, options);
  });
}

function makePost(overrides = {}) {
  return {
    id: 1,
    caption: "Hello world",
    created_at: "2026-01-01T00:00:00Z",
    author: { id: 1, name: "A", email: "a@school.edu" },
    media: { url: "https://cdn/img.jpg", type: "image", public_id: "p1" },
    likes: 0,
    views: 0,
    liked_by_me: false,
    viewed_by_me: false,
    ...overrides,
  };
}

describe("Posts page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders loading then fetched posts", async () => {
    mockFetchWithRoutes({
      "GET http://localhost:8000/api/posts": async () => ({
        ok: true,
        json: async () => ({ posts: [makePost()] }),
      }),
      "GET http://localhost:8000/users/me": async () => ({
        ok: true,
        json: async () => ({ id: 1, email: "a@school.edu", name: "A", role: "user" }),
      }),
    });

    render(
      <MemoryRouter>
        <Posts />
      </MemoryRouter>
    );

    expect(screen.getByText(/loading posts/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/hello world/i)).toBeInTheDocument();
    });
  });

  it("shows validation error when publish is clicked without a file", async () => {
    mockFetchWithRoutes({
      "GET http://localhost:8000/api/posts": async () => ({ ok: true, json: async () => ({ posts: [] }) }),
      "GET http://localhost:8000/users/me": async () => ({
        ok: true,
        json: async () => ({ id: 1, email: "a@school.edu", name: "A", role: "user" }),
      }),
    });

    render(
      <MemoryRouter>
        <Posts />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /publish post/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /publish post/i }));

    expect(screen.getByText(/please choose a photo or video to upload/i)).toBeInTheDocument();
  });

  it("shows auth-related error state when protected posts API returns 401", async () => {
    mockFetchWithRoutes({
      "GET http://localhost:8000/api/posts": async () => ({
        ok: false,
        json: async () => ({ error: "Unauthorized" }),
      }),
      "GET http://localhost:8000/users/me": async () => ({
        ok: false,
        json: async () => ({ error: "Unauthorized" }),
      }),
    });

    render(
      <MemoryRouter>
        <Posts />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/unauthorized/i)).toBeInTheDocument();
    });
  });

  it("clicking like sends API call and updates button state", async () => {
    mockFetchWithRoutes({
      "GET http://localhost:8000/api/posts": async () => ({
        ok: true,
        json: async () => ({ posts: [makePost({ id: 2, caption: "Second" })] }),
      }),
      "GET http://localhost:8000/users/me": async () => ({
        ok: true,
        json: async () => ({ id: 1, email: "a@school.edu", name: "A", role: "user" }),
      }),
      "POST http://localhost:8000/api/posts/2/like": async () => ({
        ok: true,
        json: async () => makePost({ id: 2, caption: "Second", likes: 1, liked_by_me: true }),
      }),
    });

    render(
      <MemoryRouter>
        <Posts />
      </MemoryRouter>
    );

    const likeButton = await screen.findByRole("button", { name: /like \(0\)/i });
    fireEvent.click(likeButton);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /unlike \(1\)/i })).toBeInTheDocument();
    });
  });

  it("creates a post after upload success", async () => {
    mockFetchWithRoutes({
      "GET http://localhost:8000/api/posts": async () => ({ ok: true, json: async () => ({ posts: [] }) }),
      "GET http://localhost:8000/users/me": async () => ({
        ok: true,
        json: async () => ({ id: 1, email: "a@school.edu", name: "A", role: "user" }),
      }),
      "POST http://localhost:8000/api/media/upload": async () => ({
        ok: true,
        json: async () => ({ public_id: "new-public", url: "https://cdn/new.jpg", type: "image" }),
      }),
      "POST http://localhost:8000/api/posts": async () => ({
        ok: true,
        json: async () => makePost({ id: 33, caption: "Created", media: { url: "https://cdn/new.jpg", type: "image", public_id: "new-public" } }),
      }),
    });

    render(
      <MemoryRouter>
        <Posts />
      </MemoryRouter>
    );

    await screen.findByRole("button", { name: /publish post/i });

    fireEvent.change(screen.getByPlaceholderText(/add a caption/i), { target: { value: "Created" } });
    const file = new File(["abc"], "image.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/select file/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /publish post/i }));

    await waitFor(() => {
      expect(screen.getByText(/created/i)).toBeInTheDocument();
    });
  });

  it("shows upload failure message on create", async () => {
    mockFetchWithRoutes({
      "GET http://localhost:8000/api/posts": async () => ({ ok: true, json: async () => ({ posts: [] }) }),
      "GET http://localhost:8000/users/me": async () => ({
        ok: true,
        json: async () => ({ id: 1, email: "a@school.edu", name: "A", role: "user" }),
      }),
      "POST http://localhost:8000/api/media/upload": async () => ({
        ok: false,
        json: async () => ({ error: "Upload failed" }),
      }),
    });

    render(
      <MemoryRouter>
        <Posts />
      </MemoryRouter>
    );

    await screen.findByRole("button", { name: /publish post/i });

    const file = new File(["abc"], "image.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/select file/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /publish post/i }));

    await waitFor(() => {
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
    });
  });

  it("registers view when media is clicked", async () => {
    mockFetchWithRoutes({
      "GET http://localhost:8000/api/posts": async () => ({
        ok: true,
        json: async () => ({ posts: [makePost({ id: 9, views: 0 })] }),
      }),
      "GET http://localhost:8000/users/me": async () => ({
        ok: true,
        json: async () => ({ id: 1, email: "a@school.edu", name: "A", role: "user" }),
      }),
      "POST http://localhost:8000/api/posts/9/view": async () => ({
        ok: true,
        json: async () => makePost({ id: 9, views: 1, viewed_by_me: true }),
      }),
    });

    render(
      <MemoryRouter>
        <Posts />
      </MemoryRouter>
    );

    const media = await screen.findByRole("img", { name: /hello world/i });
    fireEvent.click(media);

    await waitFor(() => {
      expect(screen.getByText(/1 views/i)).toBeInTheDocument();
    });
  });

  it("allows owner to edit caption and delete post", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    mockFetchWithRoutes({
      "GET http://localhost:8000/api/posts": async () => ({
        ok: true,
        json: async () => ({ posts: [makePost({ id: 5, caption: "Old" })] }),
      }),
      "GET http://localhost:8000/users/me": async () => ({
        ok: true,
        json: async () => ({ id: 1, email: "a@school.edu", name: "A", role: "user" }),
      }),
      "PUT http://localhost:8000/api/posts/5": async () => ({
        ok: true,
        json: async () => makePost({ id: 5, caption: "New caption" }),
      }),
      "DELETE http://localhost:8000/api/posts/5": async () => ({
        ok: true,
        json: async () => ({ deleted: 5 }),
      }),
    });

    render(
      <MemoryRouter>
        <Posts />
      </MemoryRouter>
    );

    const editButton = await screen.findByRole("button", { name: /^edit$/i });
    fireEvent.click(editButton);

    const editArea = screen.getAllByRole("textbox")[1];
    fireEvent.change(editArea, { target: { value: "New caption" } });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(screen.getByText(/new caption/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() => {
      expect(screen.queryByText(/new caption/i)).not.toBeInTheDocument();
    });
  });
});
