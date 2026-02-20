import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Account from "../pages/Account";

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

describe("Account page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows not logged in message for unauthenticated user", async () => {
    mockFetchWithRoutes({
      "GET http://localhost:8000/users/me": async () => ({
        ok: false,
        json: async () => ({ error: "Unauthorized" }),
      }),
    });

    render(
      <MemoryRouter>
        <Account />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/you are not logged in/i)).toBeInTheDocument();
    });
  });

  it("shows admin account list when current user is admin", async () => {
    mockFetchWithRoutes({
      "GET http://localhost:8000/users/me": async () => ({
        ok: true,
        json: async () => ({ id: 9, email: "admin@gmail.com", name: "Admin", role: "admin" }),
      }),
      "GET http://localhost:8000/users": async () => ({
        ok: true,
        json: async () => [
          { id: 9, email: "admin@gmail.com", name: "Admin", role: "admin" },
          { id: 1, email: "u@school.edu", name: "User", role: "user" },
        ],
      }),
    });

    render(
      <MemoryRouter>
        <Account />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/admin: manage accounts/i)).toBeInTheDocument();
      expect(screen.getByText(/u@school.edu/i)).toBeInTheDocument();
    });
  });

  it("admin can trigger delete account action", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    mockFetchWithRoutes({
      "GET http://localhost:8000/users/me": async () => ({
        ok: true,
        json: async () => ({ id: 9, email: "admin@gmail.com", name: "Admin", role: "admin" }),
      }),
      "GET http://localhost:8000/users": async () => ({
        ok: true,
        json: async () => [
          { id: 9, email: "admin@gmail.com", name: "Admin", role: "admin" },
          { id: 1, email: "u@school.edu", name: "User", role: "user" },
        ],
      }),
      "DELETE http://localhost:8000/users/1": async () => ({
        ok: true,
        json: async () => ({ deleted: 1 }),
      }),
    });

    render(
      <MemoryRouter>
        <Account />
      </MemoryRouter>
    );

    const deleteButtons = await screen.findAllByRole("button", { name: /delete account/i });
    fireEvent.click(deleteButtons[1]);

    await waitFor(() => {
      expect(screen.queryByText(/u@school.edu/i)).not.toBeInTheDocument();
    });
  });
});
