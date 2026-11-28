// Client de l'API FastAPI. Le jeton de connexion est gardé dans le navigateur.
// Vide par défaut : les appels passent par le site lui-même (/api, relayé par next.config.mjs).
// Ne renseigner NEXT_PUBLIC_API_URL que si l'API est sur un autre domaine en production.
import { Lang, clientLang, locale, translate } from "./i18n";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "";
const DOWN_FR = "Le serveur de ScholarFit ne répond pas. Vérifiez que la fenêtre « API ScholarFit » ouverte par start.ps1 tourne toujours, puis rechargez la page.";
const DOWN = () => translate(clientLang(), DOWN_FR);
// Route inconnue du serveur : en ligne, c'est presque toujours un backend Railway resté sur une ancienne version.
const OUTDATED_FR = "Cette fonction n'est pas disponible sur le serveur : il n'est sans doute pas à jour. Réessayez dans quelques minutes.";
// Réponse qui n'est pas celle de l'API (page HTML) : adresse de l'API mal réglée côté site.
const NOT_API_FR = "Le site ne joint pas correctement le serveur de ScholarFit. Réessayez dans quelques minutes.";
const TOKEN_KEY = "bm_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* navigation privée */
  }
  window.dispatchEvent(new Event("auth-change"));
}

/** En-têtes communs. X-Requested-With est exigé par l'API sur toute modification (protection CSRF). */
export function apiHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  headers.set("X-Requested-With", "ScholarFit");
  return headers;
}

export const CREDENTIALS: RequestCredentials = API_URL ? "include" : "same-origin";

/** Déconnexion : l'API efface le cookie, puis on oublie l'indice local. */
export async function signOut() {
  try {
    await fetch(`${API_URL}/api/auth/logout`, { method: "POST", headers: apiHeaders(), credentials: CREDENTIALS });
  } catch {
    /* hors ligne : le cookie expirera de lui-même */
  }
  setSignedIn(false);
  const { clearOfflineData } = await import("./pwa");
  clearOfflineData();
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    const lang = clientLang();
    if (lang !== "fr") headers.set("Accept-Language", lang);
    const url = lang !== "fr" && path.startsWith("/api") ? `${path}${path.includes("?") ? "&" : "?"}lang=${lang}` : path;
    res = await fetch(`${API_URL}${url}`, { ...init, headers });
  } catch {
    throw new ApiError(0, DOWN());
  }
  if (res.status === 401 && token) setToken(null);
  if (!res.ok) {
    const isJson = (res.headers.get("content-type") || "").includes("json");
    if (!isJson && res.status >= 500) throw new ApiError(res.status, DOWN());
    let msg = `${translate(clientLang(), "Erreur")} ${res.status}`;
    try {
      const data = await res.json();
      if (res.status === 404 && data.detail === "Not Found") msg = translate(clientLang(), OUTDATED_FR);
      else if (typeof data.detail === "string") msg = data.detail;
      else if (Array.isArray(data.detail)) msg = data.detail.map((d: { msg: string }) => d.msg).join(" ; ");
    } catch {
      /* corps vide */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError(res.status, translate(clientLang(), NOT_API_FR));
  }
}

// ---------- Types ----------
export type Scholarship = {
  id: number;
  slug: string;
  title: string;
  organization: string;
  official_url: string;
  summary: string;
  levels: string[];
  study_countries: string[];
  eligible_nationalities: string[];
  excluded_nationalities: string[];
  domains: string[];
  languages: string[];
  amount: number | null;
  currency: string | null;
  amount_period: string | null;
  coverage: string[];
  full_funding: boolean;
  deadline: string | null;
  max_age: number | null;
  min_grade: number | null;
  requirements: string[];
  language_tests: Record<string, number>;
  target_groups: string[];
  status: string;
  collected_at: string;
  verified_at: string | null;
  source_name: string | null;
  deadline_estimated?: boolean;
  previous_deadline?: string | null;
  min_experience_years?: number | null;
  statement_type?: string | null;
  application_languages?: string[];
  // Champs ajoutés par la collecte mondiale (facultatifs : l'interface retombe sur les champs ci-dessus).
  eligibility_notes?: string[];
  kind?: "bourse" | "stage" | "conference" | "formation" | "concours" | "echange" | "fellowship" | "cours_en_ligne";
  kind_label?: string | null;
  event_start?: string | null;
  event_end?: string | null;
  city?: string | null;
  remote?: boolean | null;
  duration?: string | null;
  documents?: { code: string; label: string; detail?: string | null }[];
  application_steps?: string[];
  apply_url?: string | null;
  link_status?: "ok" | "redirige" | "casse" | "non_verifie";
  link_checked_at?: string | null;
  deadline_status?: "ouverte" | "bientot" | "urgente" | "expiree" | "inconnue";
  priority?: number;
  days_left?: number | null;
  deadline_label?: string | null;
  next_expected_deadline?: string | null;
  regions?: string[];
};

export type Match = {
  scholarship: Scholarship;
  in_destination?: boolean | null;
  score: number | null;
  chance: "faible" | "moyenne" | "bonne" | null;
  reasons: string[];
  gaps: string[];
  days_left: number | null;
};

export type Meta = {
  kinds?: Record<string, string>; // types d'opportunités affichés (réglage de l'administration)
  levels: Record<string, string>;
  domains: Record<string, string>;
  countries: Record<string, string>;
  statuses: Record<string, string>;
  requirements: Record<string, string>;
};

export type Profile = {
  full_name: string | null;
  birth_date: string | null;
  nationalities: string[];
  residence_country: string | null;
  phone: string | null;
  alerts_opt_in: boolean;
  current_level: string | null;
  target_level: string | null;
  domain: string | null;
  institution: string | null;
  grade_average: number | null;
  diplomas: string[];
  wished_countries: string[];
  languages: Record<string, string>;
  language_scores: Record<string, number>;
  experiences: string | null;
  engagement: string | null;
  interests: string | null;
  work_experience_years: number | null;
  project: string | null;
  full_funding_only: boolean;
  situations: string[];
  cv_text: string | null;
  has_cv: boolean;
  completeness: number;
  minimum_ok: boolean;
  missing_minimum: string[];
  completeness_tip: string | null;
};

export type Application = {
  id: number;
  status: string;
  checklist: Record<string, boolean>;
  notes: string | null;
  letter: string | null;
  created_at: string;
  updated_at: string;
  scholarship: Scholarship;
};

export type AlertItem = { id: number; kind: string; message: string; scholarship_id: number | null; read: boolean; created_at: string };

let metaCache: Promise<Meta> | null = null;
/** À appeler après un changement de réglage dans l'administration. */
export function clearMetaCache() {
  metaCache = null;
}

export function getMeta(): Promise<Meta> {
  if (!metaCache) metaCache = api<unknown>("/api/meta").then(normalizeMeta).catch((e) => { metaCache = null; throw e; });
  return metaCache;
}

/** Profil complété par des valeurs par défaut : un serveur plus ancien (ou une base incomplète)
 * peut omettre des champs, et la page Profil ne doit jamais planter pour autant. */
export function normalizeProfile(raw: unknown): Profile {
  if (!raw || typeof raw !== "object") throw new ApiError(0, translate(clientLang(), NOT_API_FR));
  const r = raw as Partial<Profile>;
  const arr = (v: unknown) => (Array.isArray(v) ? v.filter((x) => typeof x === "string") : []);
  const obj = <V,>(v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, V>) : {});
  return {
    ...r,
    full_name: r.full_name ?? null, birth_date: r.birth_date ?? null, residence_country: r.residence_country ?? null,
    phone: r.phone ?? null, current_level: r.current_level ?? null, target_level: r.target_level ?? null,
    domain: r.domain ?? null, institution: r.institution ?? null, grade_average: r.grade_average ?? null,
    experiences: r.experiences ?? null, engagement: r.engagement ?? null, interests: r.interests ?? null, work_experience_years: r.work_experience_years ?? null, project: r.project ?? null,
    cv_text: r.cv_text ?? null, completeness_tip: r.completeness_tip ?? null,
    nationalities: arr(r.nationalities), diplomas: arr(r.diplomas), wished_countries: arr(r.wished_countries),
    situations: arr(r.situations), missing_minimum: arr(r.missing_minimum),
    languages: obj<string>(r.languages), language_scores: obj<number>(r.language_scores),
    alerts_opt_in: !!r.alerts_opt_in, full_funding_only: !!r.full_funding_only, has_cv: !!r.has_cv,
    minimum_ok: !!r.minimum_ok, completeness: typeof r.completeness === "number" ? r.completeness : 0,
  };
}

/** Listes de référence (niveaux, domaines, pays…) toujours présentes, même vides. */
function normalizeMeta(raw: unknown): Meta {
  if (!raw || typeof raw !== "object") throw new ApiError(0, translate(clientLang(), NOT_API_FR));
  const r = raw as Partial<Meta>;
  const obj = (v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, string>) : {});
  return { levels: obj(r.levels), domains: obj(r.domains), countries: obj(r.countries), statuses: obj(r.statuses), requirements: obj(r.requirements) };
}

// ---------- Mise en forme ----------
export function formatAmount(s: Scholarship, lang: Lang = clientLang()): string {
  if (!s.amount) return translate(lang, s.full_funding ? "Financement complet" : "Montant variable");
  const n = new Intl.NumberFormat(locale(lang), { maximumFractionDigits: 0 }).format(s.amount);
  const period = s.amount_period === "mois" ? translate(lang, " / mois") : s.amount_period === "an" ? translate(lang, " / an") : "";
  return `${n} ${s.currency ?? ""}${period}`.trim();
}

export function formatDate(iso: string | null, lang: Lang = clientLang()): string {
  if (!iso) return translate(lang, "Date non précisée");
  return new Date(iso + "T00:00:00").toLocaleDateString(locale(lang), { day: "numeric", month: "long", year: "numeric" });
}

export function formatMonth(iso: string | null, lang: Lang = clientLang()): string {
  if (!iso) return translate(lang, "Date non précisée");
  return new Date(iso + "T00:00:00").toLocaleDateString(locale(lang), { month: "long", year: "numeric" });
}

/** Date limite à afficher : une date reconstituée d'après la session précédente n'est jamais présentée comme exacte. */
export function deadlineText(s: Scholarship, lang: Lang = clientLang()): string {
  if (!s.deadline) return translate(lang, "Variable selon le programme");
  if (s.deadline_estimated && !s.verified_at) return translate(lang, "Attendue vers {month} (à confirmer)", { month: formatMonth(s.deadline, lang) });
  return formatDate(s.deadline, lang);
}

export function daysUntil(iso: string | null): number | null {
  if (!iso) return null;
  const d = new Date(iso + "T00:00:00").getTime();
  const today = new Date(new Date().toDateString()).getTime();
  return Math.round((d - today) / 86400000);
}

// ---------- Accompagnement ----------
export type CoachingMeta = {
  statuses: Record<string, string>;
  needs: Record<string, string>;
  meeting_modes: Record<string, string>;
  meeting_statuses: Record<string, string>;
};

export type AdvisorPublic = { id: number; display_name: string; bio: string; levels: string[]; countries: string[]; domains: string[]; languages: string[] };
export type AdvisorAdmin = AdvisorPublic & { email: string; capacity: number; active: boolean; load: number };

export type Step = { id: number; position: number; title: string; description: string | null; due_date: string | null; done: boolean; done_at: string | null; application_id: number | null };
export type CoachingMessage = { id: number; author_role: string; author_name: string | null; content: string; application_id: number | null; created_at: string; mine: boolean };
export type Meeting = { id: number; starts_at: string; duration_minutes: number; mode: string; link: string | null; topic: string | null; status: string; proposed_by: string; summary: string | null };

export type Coaching = {
  id: number;
  status: "demande" | "en_cours" | "termine" | "annule";
  goal: string;
  needs: string[];
  application_ids: number[];
  offer?: string | null;
  offer_name?: string | null;
  price_label?: string | null;
  payment_status?: string | null;
  preferred_language: string;
  availability: string | null;
  share_consent: boolean;
  rating: number | null;
  feedback: string | null;
  created_at: string;
  assigned_at: string | null;
  closed_at: string | null;
  advisor: AdvisorPublic | null;
  student_name: string | null;
  progress: number;
  next_step: Step | null;
  next_meeting: Meeting | null;
  unread: number;
  my_role: "candidat" | "conseiller" | "admin";
};

export type StudentSummary = {
  full_name: string | null; email: string; nationalities: string[]; residence_country: string | null;
  current_level: string | null; target_level: string | null; domain: string | null; institution: string | null;
  grade_average: number | null; wished_countries: string[]; languages: Record<string, string>;
  language_scores: Record<string, number>; project: string | null; experiences: string | null; cv_text: string | null; completeness: number;
};

export type CoachingFile = {
  id: number; author_role: string; category: "livrable" | "piece" | "preuve_depot"; filename: string;
  content_type: string; size: number; note: string | null; created_at: string; mine: boolean;
};

export type CoachingDetail = Coaching & {
  files?: CoachingFile[];
  steps: Step[];
  messages: CoachingMessage[];
  meetings: Meeting[];
  student: StudentSummary | null;
  applications: Application[];
};

export type AdminCoaching = Coaching & { student_email: string; suggestions: AdvisorAdmin[] };

let coachingMetaCache: Promise<CoachingMeta> | null = null;
export function getCoachingMeta(): Promise<CoachingMeta> {
  if (!coachingMetaCache) coachingMetaCache = api<CoachingMeta>("/api/accompagnement/meta").catch((e) => { coachingMetaCache = null; throw e; });
  return coachingMetaCache;
}

export function formatDateTime(iso: string, lang: Lang = clientLang()): string {
  return new Date(iso).toLocaleString(locale(lang), { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

// ---------- Données de la vitrine (avec repli si l'API ne les fournit pas encore) ----------
export type CountryStat = { code: string; name: string; region?: string | null; count: number; open_count?: number; lat?: number; lon?: number };

export async function getCountryStats(): Promise<CountryStat[]> {
  try {
    const rows = await api<CountryStat[]>("/api/stats/countries?kind=bourse");
    if (Array.isArray(rows) && rows.length) return rows;
  } catch { /* repli ci-dessous */ }
  // Repli : on compte nous-mêmes. Une bourse ouverte à « plusieurs pays » compte pour chacun,
  // comme le filtre « pays d'études » de la liste.
  const [meta, page] = await Promise.all([getMeta(), api<{ items: Scholarship[] }>("/api/scholarships?per_page=100")]);
  const specific = new Map<string, number>();
  let multi = 0;
  page.items.forEach((s) => (s.study_countries.length ? s.study_countries.forEach((c) => specific.set(c, (specific.get(c) ?? 0) + 1)) : multi++));
  return [...specific.entries()]
    .map(([code, n]) => ({ code, name: meta.countries[code] ?? code, count: n + multi, open_count: n + multi }))
    .sort((a, b) => b.count - a.count);
}

export type Offer = { code: string; name: string; price: number; currency: string; price_label: string; description: string; features: string[]; recommended?: boolean };

/** Formules affichées avant la réponse de /api/offres (même contenu que backend/app/offers.py). */
export const DEFAULT_OFFERS: Offer[] = [
  { code: "autonome", name: "Je postule seul", price: 0, currency: "XOF", price_label: "Gratuit", description: "Vous suivez les étapes de chaque fiche et déposez vous-même votre candidature sur le site officiel.", features: ["Matching et score pour toutes les bourses", "Conditions, pièces à fournir et étapes pour chaque bourse", "Premier dossier CV et lettre offert, puis abonnement à 2 500 F CFA par mois", "Suivi de vos candidatures et rappels avant les dates limites"] },
  { code: "standard", name: "Accompagnement Standard", price: 15000, currency: "XOF", price_label: "15 000 F CFA", description: "Un expert prépare votre dossier et dépose lui-même votre candidature à une bourse.", features: ["1 bourse choisie avec vous", "CV et lettre de motivation adaptés par l'expert (2 révisions)", "Vérification de toutes les pièces du dossier", "Dépôt de la candidature par l'expert, avec preuve de dépôt", "Suivi jusqu'au résultat"], recommended: true },
  { code: "premium", name: "Accompagnement Premium", price: 35000, currency: "XOF", price_label: "35 000 F CFA", description: "Un expert prépare et dépose vos candidatures à trois bourses, jusqu'à l'entretien et au visa.", features: ["Tout l'accompagnement Standard, pour 3 bourses", "Révisions illimitées du CV et des lettres", "Rédaction du projet d'études ou de recherche", "Conseils pour les lettres de recommandation", "Entretien blanc en visio", "Aide au visa si vous êtes retenu"] },
];

export async function getOffers(): Promise<Offer[]> {
  try {
    const rows = await api<Offer[]>("/api/offres");
    if (Array.isArray(rows) && rows.length) return rows;
  } catch { /* repli */ }
  return DEFAULT_OFFERS;
}

export type DeadlineInfo = { status: "ouverte" | "bientot" | "urgente" | "expiree" | "inconnue"; days: number | null; label: string; long: string | null };

export function deadlineInfo(s: Scholarship, lang: Lang = clientLang()): DeadlineInfo {
  const days = s.days_left ?? daysUntil(s.deadline);
  let status = s.deadline_status;
  if (!status) status = days === null ? "inconnue" : days < 0 ? "expiree" : days <= 14 ? "urgente" : days <= 45 ? "bientot" : "ouverte";
  const t = (fr: string, v?: Record<string, string | number>) => translate(lang, fr, v);
  const estimated = !!(s.deadline_estimated && !s.verified_at);
  const label = days === null ? t("Date limite variable") : days < 0 ? t("Clôturée le {date}", { date: formatDate(s.deadline, lang) })
    : estimated ? t("Attendue vers {month}", { month: formatMonth(s.deadline, lang) })
    : days === 0 ? t("Clôture aujourd'hui") : `${formatDate(s.deadline, lang)} · ${t("J-{n}", { n: days })}`;
  return { status, days, label, long: s.deadline_label ?? null };
}

export function applyUrl(s: Scholarship): string {
  return s.apply_url || s.official_url;
}
