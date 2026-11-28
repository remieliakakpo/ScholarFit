import { expect, test } from "@playwright/test";
import { ANSWERS, CV_TEXT, PASSWORD, auth, register, signedIn, uniqueEmail } from "./helpers";

test.describe.configure({ mode: "serial" });

test("connexion par le formulaire puis arrivée sur le tableau de bord", async ({ page, request }) => {
  const { email } = await register(request, uniqueEmail("connexion"));
  await page.goto("/connexion");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("form").getByRole("button", { name: /Se connecter/ }).click();
  await expect(page).not.toHaveURL(/\/connexion/, { timeout: 15_000 });
  await expect(page.getByText(email).first()).toBeVisible();
});

test("questionnaire, résultats et scores visibles", async ({ page, request }) => {
  const { token } = await register(request);
  await signedIn(page, token);
  await page.evaluate((a) => localStorage.setItem("sf_questionnaire", JSON.stringify(a)), ANSWERS);
  const saved = page.waitForResponse((r) => r.url().includes("/api/questionnaire") && r.request().method() === "POST");
  await page.goto("/questionnaire?etape=resultats");
  expect((await saved).status()).toBe(200);
  await expect(page.locator('a[href^="/bourses/"], a[href^="/postuler/"]').first()).toBeVisible();
  await page.goto("/mes-bourses");
  await expect(page.getByText(/\d+\s*%/).filter({ visible: true }).first()).toBeVisible();
});

test("postuler : conditions, pièces et lien officiel", async ({ page, request }) => {
  const { token } = await register(request);
  await signedIn(page, token);
  const list = await (await request.get("/api/scholarships?per_page=1")).json();
  await page.goto(`/postuler/${list.items[0].id}`);
  await expect(page.getByRole("heading", { name: /Envoyez votre candidature/ })).toBeVisible();
  const official = page.getByRole("link", { name: /Postuler sur le site officiel|Voir la page officielle/ });
  await expect(official).toHaveAttribute("href", /^https?:\/\//);
});

test("CV : texte collé puis diagnostic", async ({ page, request }) => {
  const { token } = await register(request);
  await signedIn(page, token);
  await page.goto("/cv");
  await page.getByRole("button", { name: "Ou collez le texte de votre CV" }).click();
  await page.locator("#cv-text").fill(CV_TEXT);
  await page.getByRole("button", { name: "Enregistrer" }).click();
  await expect(page.getByRole("heading", { name: "Diagnostic" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Relancer/ })).toBeEnabled({ timeout: 30_000 });
});

test("abonnement CV payé en ligne (mode d'essai)", async ({ page, request }) => {
  const { token } = await register(request);
  const cfg = await (await request.get("/api/payments/config")).json();
  test.skip(cfg.provider !== "simulation", "PAYMENT_PROVIDER doit valoir simulation");
  await signedIn(page, token);
  const p = await (await request.post("/api/payments/checkout", { headers: auth(token), data: { purpose: "abonnement" } })).json();
  await page.goto(new URL(p.checkout_url).pathname + new URL(p.checkout_url).search);
  await expect(page.getByText("2 500 F CFA").first()).toBeVisible();
  await page.getByRole("button", { name: "Simuler un paiement réussi" }).click();
  await expect(page.getByRole("heading", { name: "Paiement confirmé" })).toBeVisible();
  const credits = await (await request.get("/api/credits", { headers: auth(token) })).json();
  expect(credits.subscription.active).toBe(true);
});

test("accompagnement Standard payé depuis l'espace candidat", async ({ page, request }) => {
  const { token } = await register(request);
  const cfg = await (await request.get("/api/payments/config")).json();
  test.skip(cfg.provider !== "simulation", "PAYMENT_PROVIDER doit valoir simulation");
  const c = await request.post("/api/accompagnement", { headers: auth(token), data: { goal: "Obtenir une bourse de master en France", needs: ["lettre"], application_ids: [], share_consent: true, offer: "standard" } });
  expect(c.status()).toBe(201);
  await signedIn(page, token);
  await page.goto("/accompagnement");
  await page.getByRole("button", { name: /Payer 15 000 F CFA/ }).click();
  await page.getByRole("button", { name: "Simuler un paiement réussi" }).click();
  await expect(page.getByRole("heading", { name: "Paiement confirmé" })).toBeVisible();
  await page.getByRole("link", { name: /Ouvrir mon accompagnement/ }).click();
  await expect(page.getByText("Payé", { exact: true }).first()).toBeVisible();
  await page.getByRole("tab", { name: /Documents/ }).click();
  await page.locator("#file-up").setInputFiles({ name: "releves.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 e2e") });
  await expect(page.getByText("releves.pdf")).toBeVisible();
});
