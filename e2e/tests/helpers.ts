import { APIRequestContext, Page, expect } from "@playwright/test";

export const PASSWORD = "Parcours2026";

export function uniqueEmail(prefix = "e2e") {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.org`;
}

/** Crée un compte par l'API et renvoie son jeton. */
export async function register(request: APIRequestContext, email = uniqueEmail()): Promise<{ email: string; token: string }> {
  const r = await request.post("/api/auth/register", { data: { email, password: PASSWORD } });
  expect(r.status(), await r.text()).toBe(201);
  return { email, token: (await r.json()).access_token };
}

/** Ouvre le site déjà connecté (même stockage que le formulaire de connexion). */
export async function signedIn(page: Page, token: string) {
  await page.goto("/");
  await page.evaluate((t) => localStorage.setItem("bm_token", t), token);
}

export const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

/** Réponses du questionnaire : étudiante sénégalaise, licence → master en informatique. */
export const ANSWERS = {
  nationalities: ["SN"],
  residence_country: "SN",
  birth_date: "2001-05-14",
  current_level: "BAC3",
  target_level: "BAC5",
  domain: "informatique",
  grade_average: 14,
  wished_regions: ["europe"],
  wished_countries: ["FR"],
  full_funding_only: false,
  languages: ["fr", "en"],
  situations: [],
  applications_planned: 2,
  help_preference: "seul",
};

export const CV_TEXT = `Awa Diop
Dakar, Sénégal | +221 77 000 00 00 | awa.diop@example.org

FORMATION
2021 - 2024 Licence en informatique, Université Cheikh Anta Diop, Dakar. Mention bien.

EXPÉRIENCES
2023 Stage développeuse web, Orange Digital Center, Dakar. Application de suivi des stocks pour 3 boutiques.

COMPÉTENCES
Python, JavaScript, SQL, Git

LANGUES
Français (natif), anglais (B2), wolof (natif)`;
