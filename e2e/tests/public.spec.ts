import { expect, test } from "@playwright/test";

test.describe("Site public", () => {
  test("accueil, liste et fiche d'une bourse", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: /ScholarFit/ }).first()).toBeVisible();
    await page.goto("/bourses");
    const first = page.locator('a[href^="/bourses/"]').first();
    await expect(first).toBeVisible();
    await first.click();
    await expect(page).toHaveURL(/\/bourses\/\d+/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByText(/Fiche mise à jour le/)).toBeVisible();
  });

  test("pages pays et plan du site", async ({ page, request }) => {
    await page.goto("/destinations");
    await expect(page.getByRole("heading", { name: "Bourses d'études par pays" })).toBeVisible();
    await page.getByRole("link", { name: /France/ }).first().click();
    await expect(page).toHaveURL(/\/destinations\/france$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("France");
    await page.getByRole("link", { name: /Bourses d'études ·/ }).click();
    await expect(page).toHaveURL(/\/destinations\/france\/bourses$/);
    const sitemap = await request.get("/sitemap.xml");
    expect(sitemap.ok()).toBeTruthy();
    expect(await sitemap.text()).toContain("/destinations/france");
    expect(await (await request.get("/robots.txt")).text()).toContain("Sitemap:");
  });

  test("pages légales accessibles depuis le pied de page", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Conditions d'utilisation" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Conditions d'utilisation" })).toBeVisible();
    await page.goto("/confidentialite");
    await expect(page.getByRole("heading", { level: 1, name: "Politique de confidentialité" })).toBeVisible();
    await page.goto("/a-propos");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
});
