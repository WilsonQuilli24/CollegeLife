import { test, expect } from "@playwright/test";

test("login -> create new post entity flow", async ({ page }) => {
  await page.route("**/auth/reset-session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ message: "Session reset" }) });
  });

  await page.route("**/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: 1, email: "student@school.edu", name: "Student", role: "user" }),
    });
  });

  await page.route("**/api/posts", async (route) => {
    const method = route.request().method();

    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ posts: [] }),
      });
      return;
    }

    if (method === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: 2,
          caption: "Created from E2E",
          created_at: "2026-01-01T00:00:00Z",
          author: { id: 1, name: "Student", email: "student@school.edu" },
          media: { public_id: "new-public-id", url: "https://example.com/new.jpg", type: "image" },
          likes: 0,
          views: 0,
          liked_by_me: false,
          viewed_by_me: false,
        }),
      });
      return;
    }

    await route.fallback();
  });

  await page.route("**/api/media/upload", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        public_id: "new-public-id",
        url: "https://example.com/new.jpg",
        type: "image",
      }),
    });
  });

  await page.goto("/posts");

  await page.getByPlaceholder("Add a caption...").fill("Created from E2E");

  await page.setInputFiles("#post-file-input", {
    name: "image.png",
    mimeType: "image/png",
    buffer: Buffer.from("89504E470D0A1A0A", "hex"),
  });

  await page.getByRole("button", { name: /publish post/i }).click();

  await expect(page.getByText(/created from e2e/i)).toBeVisible();
});
