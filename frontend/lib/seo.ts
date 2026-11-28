// Pages de référencement : un pays d'études, et un type d'offre dans ce pays. Voir backend/app/routers/seo.py.
import { Meta, Scholarship } from "@/lib/api";
import { Lang } from "@/lib/i18n";

const API = process.env.API_URL_INTERNAL || "http://127.0.0.1:8000";
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");

export type KindSlug = "bourses" | "stages" | "conferences";
export const KIND_SLUGS: KindSlug[] = ["bourses", "stages", "conferences"];
export const KIND_OF: Record<KindSlug, "bourse" | "stage" | "conference"> = { bourses: "bourse", stages: "stage", conferences: "conference" };

export type DestinationRow = { code: string; slug: string; name: string; region: string | null; counts: Record<string, number>; total: number };
export type Destination = {
  code: string; slug: string; name: string; region: string | null; region_name: string | null; kind: KindSlug | null;
  counts: Record<string, number>; total: number; full_funding: number; items: Scholarship[];
};

const q = (lang: Lang) => (lang !== "fr" ? `lang=${lang}` : "");

export async function loadDestinations(lang: Lang = "fr"): Promise<DestinationRow[]> {
  try {
    const r = await fetch(`${API}/api/seo/destinations?${q(lang)}`, { next: { revalidate: 3600 } });
    return r.ok ? r.json() : [];
  } catch {
    return [];
  }
}

export async function loadDestination(slug: string, kind: KindSlug | null, lang: Lang = "fr"): Promise<{ d: Destination; meta: Meta } | null> {
  try {
    const params = [kind ? `kind=${kind}` : "", q(lang)].filter(Boolean).join("&");
    const [r, m] = await Promise.all([
      fetch(`${API}/api/seo/destinations/${encodeURIComponent(slug)}?${params}`, { next: { revalidate: 3600 } }),
      fetch(`${API}/api/meta?${q(lang)}`, { next: { revalidate: 3600 } }),
    ]);
    if (!r.ok) return null;
    return { d: await r.json(), meta: await m.json() };
  } catch {
    return null;
  }
}

/** « en France », « au Canada », « aux États-Unis » : préposition courante devant un nom de pays. */
export function inCountry(name: string, lang: Lang): string {
  if (lang === "en") return `in ${name}`;
  const plural = /^(États-Unis|Pays-Bas|Émirats arabes unis|Philippines|Comores|Seychelles|Maldives|Bahamas|Fidji)/.test(name);
  if (plural) return `aux ${name}`;
  const masc = new Set(["Canada", "Japon", "Maroc", "Sénégal", "Togo", "Bénin", "Burkina Faso", "Cameroun", "Gabon", "Ghana", "Kenya", "Mali", "Niger", "Nigeria", "Rwanda", "Tchad", "Congo", "Royaume-Uni", "Portugal", "Brésil", "Mexique", "Chili", "Pérou", "Danemark", "Luxembourg", "Liban", "Qatar", "Koweït", "Vietnam", "Cambodge", "Pakistan", "Bangladesh", "Népal", "Sri Lanka", "Zimbabwe", "Botswana", "Malawi", "Mozambique", "Burundi", "Soudan", "Soudan du Sud", "Lesotho", "Liberia", "Venezuela", "Panama", "Guatemala", "Honduras", "Nicaragua", "Salvador", "Paraguay", "Costa Rica", "Kazakhstan", "Kirghizistan", "Tadjikistan", "Ouzbékistan", "Turkménistan", "Myanmar", "Laos", "Yémen", "Bhoutan", "Brunei", "Monténégro", "Kosovo", "Liechtenstein", "Vatican", "Groenland", "Swaziland", "Eswatini", "Togo"]);
  if (/^[AEIOUYÉÈÊÂÎÔ]/i.test(name)) return `en ${name}`;
  if (masc.has(name)) return `au ${name}`;
  return `en ${name}`;
}
