import type { MetadataRoute } from "next";
import { KIND_OF, KIND_SLUGS, SITE_URL, loadDestinations } from "@/lib/seo";

const API = process.env.API_URL_INTERNAL || "http://127.0.0.1:8000";
export const dynamic = "force-dynamic"; // calculé à la demande (les appels à l'API restent mis en cache une heure)

/** Plan du site pour les moteurs de recherche : pages publiques, pays, types d'offre par pays et fiches. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const pages: MetadataRoute.Sitemap = ["", "/bourses", "/bourses?kind=stage", "/bourses?kind=conference", "/destinations", "/questionnaire", "/a-propos", "/conditions", "/confidentialite"]
    .map((p) => ({ url: `${SITE_URL}${p}`, lastModified: now, changeFrequency: "weekly", priority: p === "" ? 1 : 0.7 }));
  const dest = await loadDestinations();
  for (const d of dest) {
    pages.push({ url: `${SITE_URL}/destinations/${d.slug}`, lastModified: now, changeFrequency: "weekly", priority: 0.8 });
    for (const k of KIND_SLUGS) if ((d.counts[KIND_OF[k]] ?? 0) > 0) pages.push({ url: `${SITE_URL}/destinations/${d.slug}/${k}`, lastModified: now, changeFrequency: "weekly", priority: 0.7 });
  }
  try {
    for (let page = 1; page <= 20; page++) {
      const r = await fetch(`${API}/api/scholarships?per_page=100&page=${page}`, { next: { revalidate: 3600 } });
      if (!r.ok) break;
      const data: { total: number; items: { id: number; collected_at: string }[] } = await r.json();
      for (const s of data.items) pages.push({ url: `${SITE_URL}/bourses/${s.id}`, lastModified: new Date(s.collected_at), changeFrequency: "weekly", priority: 0.6 });
      if (page * 100 >= data.total) break;
    }
  } catch {
    /* API injoignable pendant la construction : le plan sera complété au prochain passage */
  }
  return pages;
}
