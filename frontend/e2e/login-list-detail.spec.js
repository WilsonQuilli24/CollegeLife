import { test, expect } from "@playwright/test";

test("login -> list -> detail(view) flow", async ({ page }) => {
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
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          posts: [
            {
              id: 1,
              caption: "Post Detail Example",
              created_at: "2026-01-01T00:00:00Z",
              author: { id: 1, name: "Student", email: "student@school.edu" },
              media: { public_id: "p1", url: "https://example.com/image.jpg", type: "image" },
              likes: 0,
              views: 0,
              liked_by_me: false,
              viewed_by_me: false,
            },
          ],
        }),
      });
      return;
    }

    await route.fallback();
  });

  await page.route("**/api/posts/1/view", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1,
        caption: "Post Detail Example",
        created_at: "2026-01-01T00:00:00Z",
        author: { id: 1, name: "Student", email: "student@school.edu" },
        media: { public_id: "p1", url: "https://example.com/image.jpg", type: "image" },
        likes: 0,
        views: 1,
        liked_by_me: false,
        viewed_by_me: true,
      }),
    });
  });

  await page.goto("/");
  await expect(page.getByRole("button", { name: /welcome student/i })).toBeVisible();

  await page.getByRole("button", { name: /go to posts/i }).click();
  await expect(page.getByText(/post detail example/i)).toBeVisible();

  await page.locator("img.post-media").first().click();
  await expect(page.getByText(/1 views/i)).toBeVisible();
});