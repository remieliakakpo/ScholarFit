// Client de l'API FastAPI. La session est un cookie httpOnly posé par l'API : le JavaScript de la
// page ne le voit jamais (une faille XSS ne peut pas le voler). Le navigateur l'envoie tout seul.
// Vide par défaut : les appels passent par le site lui-même (/api, relayé par next.config.mjs).
// Ne renseigner NEXT_PUBLIC_API_URL que si l'API est sur un autre domaine en production.
import { Lang, clientLang, locale, translate } from "./i18n";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "";
const DOWN_FR = "Le serveur de ScholarFit ne répond pas. Vérifiez que la fenêtre « API ScholarFit » ouverte par start.ps1 tourne toujours, puis rechargez la page.";
const DOWN = () => translate(clientLang(), DOWN_FR);
// Simple indice « une session a été ouverte dans ce navigateur » (pas un secret) : évite d'appeler
// /api/auth/me à chaque page pour un visiteur. L'API reste seule juge (cookie httpOnly).
const SESSION_HINT = "sf_signed_in";
const OLD_TOKEN_KEY = "bm_token"; // ancien jeton gardé en localStorage : effacé

export function isSignedIn(): boolean {
  if (typeof window === "undefined") return false;
  try {
    localStorage.removeItem(OLD_TOKEN_KEY);
    return localStorage.getItem(SESSION_HINT) === "1";
  } catch {
    return true; // stockage bloqué : on demande à l'API
  }
}

export function setSignedIn(on: boolean) {
  try {
    if (on) localStorage.setItem(SESSION_HINT, "1");
    else localStorage.removeItem(SESSION_HINT);
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
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = apiHeaders(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    const lang = clientLang();
    if (lang !== "fr") headers.set("Accept-Language", lang);
    const url = lang !== "fr" && path.startsWith("/api") ? `${path}${path.includes("?") ? "&" : "?"}lang=${lang}` : path;
    res = await fetch(`${API_URL}${url}`, { ...init, headers, credentials: CREDENTIALS });
  } catch {
    throw new ApiError(0, DOWN());
  }
  if (res.status === 401 && isSignedIn()) setSignedIn(false);
  if (!res.ok) {
    const isJson = (res.headers.get("content-type") || "").includes("json");
    if (!isJson && res.status >= 500) throw new ApiError(res.status, DOWN());
    let msg = `${translate(clientLang(), "Erreur")} ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") msg = data.detail;
      else if (Array.isArray(data.detail)) msg = data.detail.map((d: { msg: string }) => d.msg).join(" ; ");
    } catch {
      /* corps vide */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
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
  // Champs ajoutés par la collecte mondiale (facultatifs : l'interface retombe sur les champs ci-dessus).
  eligibility_notes?: string[];
  kind?: "bourse" | "stage" | "conference";
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
export function getMeta(): Promise<Meta> {
  if (!metaCache) metaCache = api<Meta>("/api/meta").catch((e) => { metaCache = null; throw e; });
  return metaCache;
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

export type CoachingDetail = Coaching & {
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
  const label = days === null ? t("Date limite variable") : days < 0 ? t("Clôturée le {date}", { date: formatDate(s.deadline, lang) }) : days === 0 ? t("Clôture aujourd'hui") : `${formatDate(s.deadline, lang)} · ${t("J-{n}", { n: days })}`;
  return { status, days, label, long: s.deadline_label ?? null };
}

export function applyUrl(s: Scholarship): string {
  return s.apply_url || s.official_url;
}
