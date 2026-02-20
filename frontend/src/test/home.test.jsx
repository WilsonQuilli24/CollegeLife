import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Home from "../pages/Home";

describe("Home page login state", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("shows Google login button when not authenticated", async () => {
    sessionStorage.setItem("initial_session_reset_done", "1");

    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: false,
      json: async () => ({ error: "Unauthorized" }),
    });

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /log in with google/i })).toBeInTheDocument();
    });
  });

  it("shows welcome message when authenticated", async () => {
    sessionStorage.setItem("initial_session_reset_done", "1");

    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ email: "student@example.edu", name: "Student", role: "user" }),
    });

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /welcome student/i })).toBeInTheDocument();
    });
  });
});
