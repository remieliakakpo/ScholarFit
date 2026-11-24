// Données et textes partagés par la fiche d'une bourse (/bourses/ID) et la page de candidature (/postuler/ID).
import { Meta, Scholarship } from "@/lib/api";
import { Lang, countryName } from "@/lib/i18n";

const API = process.env.API_URL_INTERNAL || "http://127.0.0.1:8000";

export async function loadScholarship(id: string, lang: Lang = "fr"): Promise<{ s: Scholarship; meta: Meta } | null> {
  try {
    const [r, m] = await Promise.all([
      fetch(`${API}/api/scholarships/${encodeURIComponent(id)}${lang !== "fr" ? `?lang=${lang}` : ""}`, { cache: "no-store" }),
      fetch(`${API}/api/meta${lang !== "fr" ? `?lang=${lang}` : ""}`, { next: { revalidate: 3600 } }),
    ]);
    if (!r.ok) return null;
    return { s: await r.json(), meta: await m.json() };
  } catch {
    return null;
  }
}

export const COVERAGE: Record<string, string> = { frais: "Frais de scolarité", logement: "Logement", voyage: "Billet d'avion", allocation: "Allocation mensuelle", assurance: "Assurance santé" };
export const GROUPS: Record<string, string> = { AFRICA: "un pays africain", EU: "un pays de l'Union européenne", FRANCOPHONIE: "un pays de la Francophonie", DEVELOPING: "un pays en développement" };
export const TARGETS: Record<string, string> = { refugie: "aux personnes réfugiées", handicap: "aux personnes en situation de handicap", revenus_modestes: "aux étudiants de familles à revenus modestes", femmes: "aux femmes", premiere_generation: "aux étudiants de première génération" };

/** Ce que chaque pièce demande concrètement (utilisé quand la fiche ne le précise pas). */
export const DOC_DETAIL: Record<string, string> = {
  cv: "Une à deux pages, à jour, centrées sur votre parcours scolaire, vos expériences et vos engagements.",
  lettre: "Une page qui explique votre projet d'études, pourquoi ce programme et ce que vous ferez ensuite.",
  recommandation: "En général deux lettres d'enseignants ou d'encadrants qui vous connaissent bien. Demandez-les au moins trois semaines avant.",
  releves: "Les relevés des dernières années d'études, souvent traduits en anglais ou en français et certifiés conformes.",
  test_langue: "Un résultat officiel récent (moins de deux ans en général) au niveau demandé.",
  projet_recherche: "Deux à cinq pages : sujet, question de recherche, méthode, calendrier et directeur pressenti si possible.",
  passeport: "Valide au moins six mois après la date prévue d'arrivée. Lancez la demande tôt si vous n'en avez pas.",
  certificat_medical: "Certificat récent signé par un médecin agréé, parfois sur un formulaire fourni par le programme.",
  lettre_admission: "Lettre d'admission ou de pré-admission de l'université d'accueil, si le programme la demande au dépôt.",
  photo: "Photo d'identité récente sur fond clair, au format demandé.",
  portfolio: "Sélection de vos travaux (arts, design, architecture), en PDF ou en lien en ligne.",
  justificatif_revenus: "Attestation de revenus ou de non-imposition des parents, pour les bourses sur critères sociaux.",
  diplome: "Copie du dernier diplôme obtenu, ou une attestation de réussite s'il n'est pas encore délivré.",
};

export const DEFAULT_STEPS = [
  "Vérifiez que vous remplissez toutes les conditions ci-dessus, en particulier la nationalité, le niveau et l'âge.",
  "Rassemblez les documents demandés. Les traductions, certifications et lettres de recommandation prennent souvent plusieurs semaines.",
  "Rédigez votre lettre de motivation et adaptez votre CV à cette bourse. Vous pouvez les préparer depuis votre espace ScholarFit.",
  "Créez votre compte sur le site officiel et remplissez le formulaire de candidature en ligne.",
  "Envoyez votre candidature avant la date limite, gardez l'accusé de réception et notez la date des résultats.",
];

export type T = (fr: string, vars?: Record<string, string | number | null | undefined>) => string;
export const LANG_NAMES: Record<string, string> = { fr: "français", en: "anglais", de: "allemand", es: "espagnol", ar: "arabe", pt: "portugais", it: "italien" };

export function conditions(s: Scholarship, meta: Meta, t: T, lang: Lang): string[] {
  if (s.eligibility_notes?.length) return s.eligibility_notes;
  const c = (x: string) => countryName(x, lang, meta.countries[x]);
  const or = ` ${t("ou")} `;
  const out: string[] = [];
  if (s.eligible_nationalities.includes("ALL") || !s.eligible_nationalities.length) out.push(t("Ouverte à toutes les nationalités."));
  else out.push(t("Être ressortissant de {list}.", { list: s.eligible_nationalities.map((n) => (GROUPS[n] ? t(GROUPS[n]) : c(n))).join(", ") }));
  if (s.excluded_nationalities.length) out.push(t("Les ressortissants de {list} ne peuvent pas postuler.", { list: s.excluded_nationalities.map(c).join(", ") }));
  if (s.levels.length) out.push(t("Postuler pour un diplôme de niveau {list}.", { list: s.levels.map((l) => t(meta.levels[l] ?? l).split(" : ").pop()).join(`,${or}`) }));
  if (s.domains.length && !s.domains.includes("tous")) out.push(t("Étudier dans l'un de ces domaines : {list}.", { list: s.domains.map((d) => t(meta.domains[d] ?? d)).join(", ") }));
  if (s.max_age) out.push(t("Avoir {n} ans au plus à la date limite de candidature.", { n: s.max_age }));
  if (s.min_grade) out.push(t("Avoir une moyenne d'au moins {n}/20.", { n: s.min_grade }));
  const tests = Object.entries(s.language_tests);
  if (tests.length) out.push(t("Justifier d'un niveau de langue : {list}.", { list: tests.map(([k, v]) => `${k} ${v}`).join(or) }));
  else if (s.languages.length) out.push(t("Pouvoir étudier en {list}.", { list: s.languages.map((l) => (LANG_NAMES[l] ? t(LANG_NAMES[l]) : l)).join(or) }));
  if (s.target_groups.length) out.push(t("Bourse réservée {list}.", { list: s.target_groups.map((g) => (TARGETS[g] ? t(TARGETS[g]) : g)).join(or) }));
  return out;
}

export function documents(s: Scholarship, meta: Meta, t: T): { label: string; detail?: string }[] {
  const det = (code: string) => (DOC_DETAIL[code] ? t(DOC_DETAIL[code]) : undefined);
  if (s.documents?.length) return s.documents.map((d) => ({ label: t(d.label), detail: d.detail ? t(d.detail) : det(d.code) }));
  return s.requirements.map((r) => ({ label: t(meta.requirements[r] ?? r), detail: det(r) }));
}

export const LINK: Record<string, { t: string; cls: string }> = {
  ok: { t: "Lien officiel vérifié", cls: "text-ok" },
  redirige: { t: "Le site officiel a changé d'adresse, le lien suit la nouvelle", cls: "text-gold-dark" },
  casse: { t: "Le site officiel ne répond pas en ce moment, réessayez plus tard ou recherchez le programme par son nom", cls: "text-warm" },
};

