// CV, lettres, compatibilité et dossiers payants : types et appels à l'API.
import { API_URL, ApiError, getToken } from "./api";
import { clientLang, translate } from "./i18n";

export type CVEntry = { title: string; organization: string; location: string; dates: string; bullets: string[] };
export type CVSection = { key: string; title: string; kind: "entries" | "list"; entries: CVEntry[]; items: string[] };
export type CVData = {
  language: "fr" | "en";
  format: string;
  format_label: string;
  format_reason: string;
  format_rules: string[];
  layout: "single" | "dated";
  header: { name: string; headline: string; email: string; phone: string; location: string; links: string; objective?: string; birth_date: string; nationality: string };
  summary_title: string;
  summary: string;
  sections: CVSection[];
  signature: string;
  changes: string[];
  scholarship_id: number | null;
  scholarship_title: string | null;
};

export type LetterData = {
  language: "fr" | "en";
  style: "fr" | "en_uk" | "en_us";
  sender: string[];
  recipient: string[];
  place_date: string;
  subject: string;
  salutation: string;
  paragraphs: string[];
  closing: string;
  signature: string;
  answers?: Record<string, string>;
  max_words?: number;
  scholarship_id: number;
  scholarship_title: string;
  /** Remarques sur la version hors IA (langue du CV ou des réponses différente de celle de la lettre). */
  notes?: string[];
};

export type Doc<T> = { id: number; kind: string; title: string; data: T; scholarship_id: number | null; updated_at: string | null };

export type Criterion = { key: string; label: string; weight: number; score: number; status: "ok" | "a_ameliorer" | "manquant"; finding: string; recommendation: string | null };
export type Diagnostic = {
  score: number;
  verdict: string;
  criteria: Criterion[];
  priorities: string[];
  rewrites: { original: string; proposal: string; why: string }[];
  spelling: string[];
  sections_found: string[];
  word_count: number;
};

export type Fit = {
  score: number;
  verdict: string;
  verdict_detail: string;
  level: "ok" | "moyen" | "faible" | "ko";
  checks: { key: string; label: string; status: "ok" | "ko" | "inconnu" | "attention"; detail: string }[];
  documents: { key: string; label: string; ready: boolean }[];
  themes: { key: string; label: string; covered: boolean }[];
  cv_score: number | null;
  improvements: { priority: number; text: string; action: "profil" | "cv" | "lettre" | "conditions" }[];
};

export type PayMethod = { code: string; label: string; logo: string; number: string; how: string };
export type Credits = {
  free_total: number;
  free_left: number;
  paid_total: number;
  used: number;
  available: number;
  pending_orders: number;
  price: number;
  price_label: string;
  regenerations: number;
  subscription: { active: boolean; until: string | null; until_label: string | null; monthly_packs: number; used_this_period: number; left_this_period: number; days: number };
  packs: { scholarship_id: number | null; scholarship_title: string | null; cv_runs: number; letter_runs: number; source: string }[];
  methods: PayMethod[];
  orders?: { id: number; amount: number; method: string; reference: string | null; status: string; status_label: string; created_at: string }[];
};

/** Erreur de l'API avec son code métier (abonnement_requis, limite_mensuelle, relances_epuisees…). */
export class DocError extends ApiError {
  constructor(status: number, message: string, public code: string | null) {
    super(status, message);
  }
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    const lang = clientLang();
    const url = lang !== "fr" ? `${path}${path.includes("?") ? "&" : "?"}lang=${lang}` : path;
    res = await fetch(`${API_URL}${url}`, { ...init, headers });
  } catch {
    throw new DocError(0, translate(clientLang(), "Le serveur de ScholarFit ne répond pas. Réessayez dans un instant."), null);
  }
  if (!res.ok) {
    let msg = `Erreur ${res.status}`;
    let code: string | null = null;
    try {
      const data = await res.json();
      const d = data.detail;
      if (typeof d === "string") msg = d;
      else if (d && typeof d === "object" && !Array.isArray(d)) { msg = d.message ?? msg; code = d.code ?? null; }
      else if (Array.isArray(d)) msg = d.map((x: { msg: string }) => x.msg).join(" ; ");
    } catch {
      /* corps vide */
    }
    throw new DocError(res.status, msg, code);
  }
  return res;
}

export async function docApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await call(path, init);
  return res.status === 204 ? (undefined as T) : res.json();
}

/** Télécharge le CV ou la lettre en PDF ou Word, tel qu'il est affiché. */
export async function downloadDoc(kind: "cv" | "lettre", fmt: "pdf" | "docx", data: CVData | LetterData) {
  const res = await call(`/api/export/${kind}?fmt=${fmt}`, { method: "POST", body: JSON.stringify({ data }) });
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? `${kind}.${fmt}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
