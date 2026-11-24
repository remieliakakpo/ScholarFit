"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import Icon from "@/components/Icon";
import AdvisorBanner from "@/components/AdvisorBanner";
import ScholarshipCard from "@/components/ScholarshipCard";
import { Match, Meta, Scholarship, api, getMeta } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { useT } from "@/components/LangProvider";
import { Lang, countryName } from "@/lib/i18n";
import { regionOf } from "@/lib/geo";

/*
  Questionnaire en 5 étapes pour cerner le profil et sortir les bourses qui correspondent.
  Les questions viennent de GET /api/questionnaire ; si l'API ne les fournit pas encore,
  on utilise la version locale ci-dessous (mêmes identifiants que les champs du profil).
*/

type Opt = { value: string; label: string; region?: string | null };
type Question = {
  id: string; label: string; type: string; required?: boolean; placeholder?: string; help?: string;
  /** Pays : liste réduite aux continents choisis dans la question indiquée (ex. wished_regions). */
  filter_by?: string;
  options?: Opt[] | string[] | Record<string, string>;
};
type Step = { id: string; title: string; subtitle?: string; questions: Question[] };
type Answers = Record<string, unknown>;
type Result = { total_matches: number; destination_total?: number; has_destination?: boolean; items: Match[]; recommended_offer?: string | null; profile_saved?: boolean; missing?: string[] };

const STORE = "sf_questionnaire";

const SITUATIONS: Record<string, string> = {
  revenus_modestes: "Revenus familiaux modestes",
  premiere_generation: "Première génération à l'université",
  refugie: "Statut de réfugié",
  handicap: "Situation de handicap",
  femmes: "Je suis une femme (bourses réservées)",
};

function localSteps(meta: Meta): Step[] {
  const levels = meta.levels;
  const domains = Object.fromEntries(Object.entries(meta.domains).filter(([k]) => k !== "tous"));
  return [
    { id: "identite", title: "Vous", subtitle: "Votre nationalité détermine la plupart des bourses auxquelles vous avez droit.", questions: [
      { id: "nationality", label: "Votre nationalité", type: "country", required: true },
      { id: "residence_country", label: "Le pays où vous vivez aujourd'hui", type: "country" },
      { id: "birth_date", label: "Votre date de naissance", type: "date", required: true, help: "Beaucoup de bourses fixent un âge maximum." },
    ] },
    { id: "etudes", title: "Vos études", subtitle: "Où vous en êtes aujourd'hui.", questions: [
      { id: "current_level", label: "Votre niveau actuel", type: "select", options: levels, required: true },
      { id: "grade_average", label: "Votre moyenne générale (sur 20)", type: "number", placeholder: "ex. 13,5", help: "Une estimation suffit." },
    ] },
    { id: "projet", title: "Votre projet", subtitle: "Le diplôme que vous souhaitez faire financer.", questions: [
      { id: "target_level", label: "Le niveau que vous visez", type: "select", options: levels, required: true },
      { id: "domain", label: "Votre domaine d'études", type: "select", options: domains, required: true },
    ] },
    { id: "destination", title: "Où étudier", subtitle: "Choisissez un ou plusieurs pays, ou laissez vide pour tout voir.", questions: [
      { id: "wished_countries", label: "Les pays qui vous intéressent", type: "countries" },
      { id: "study_language", label: "Vous pouvez étudier en", type: "multiselect", options: { fr: "Français", en: "Anglais", de: "Allemand", es: "Espagnol", ar: "Arabe" } },
      { id: "full_funding_only", label: "Je ne veux que des bourses à financement complet", type: "boolean" },
    ] },
    { id: "situation", title: "Votre situation", subtitle: "Certaines bourses sont réservées à des profils précis. Tout est facultatif.", questions: [
      { id: "situations", label: "Ce qui vous concerne", type: "multiselect", options: SITUATIONS },
      { id: "help_wanted", label: "Pour postuler, vous préférez", type: "select", options: { seul: "Postuler moi-même", accompagne: "Être accompagné par un conseiller", indecis: "Je ne sais pas encore" } },
    ] },
  ];
}

/** Continent de chaque pays proposé (donné par l'API, sinon table locale). */
function regionMap(q: Question): Record<string, string> {
  const out: Record<string, string> = {};
  if (Array.isArray(q.options)) for (const o of q.options) if (typeof o !== "string") out[o.value] = o.region ?? regionOf(o.value) ?? "";
  return out;
}

function optionsOf(q: Question, meta: Meta | null, lang: Lang): Opt[] {
  if (q.type === "country" || q.type === "countries") {
    const regions = regionMap(q);
    return Object.entries(meta?.countries ?? {})
      .map(([value, label]) => ({ value, label: countryName(value, lang, label), region: regions[value] ?? regionOf(value) }))
      .sort((a, b) => a.label.localeCompare(b.label, lang));
  }
  const o = q.options;
  if (!o) return [];
  if (Array.isArray(o)) return o.map((x) => (typeof x === "string" ? { value: x, label: x } : x));
  return Object.entries(o).map(([value, label]) => ({ value, label }));
}

/** Traduit les libellés des étapes (sans effet si l'API les sert déjà dans la bonne langue). */
function translateSteps(steps: Step[], t: (fr: string) => string): Step[] {
  const tr = (x?: string) => (x ? t(x) : x);
  const opts = (o: Question["options"]): Question["options"] => {
    if (!o) return o;
    if (Array.isArray(o)) return o.map((x) => (typeof x === "string" ? { value: x, label: t(x) } : { ...x, label: t(x.label) }));
    return Object.fromEntries(Object.entries(o).map(([k, v]) => [k, t(v)]));
  };
  return steps.map((st) => ({ ...st, title: t(st.title), subtitle: tr(st.subtitle), questions: st.questions.map((q) => ({ ...q, label: t(q.label), help: tr(q.help), placeholder: tr(q.placeholder), options: opts(q.options) })) }));
}

function isEmpty(v: unknown) {
  return v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0);
}

/** Si l'API questionnaire n'est pas encore disponible : on enregistre le profil (connecté) ou on filtre la liste publique. */
async function fallbackMatch(a: Answers, loggedIn: boolean): Promise<Result> {
  const nat = a.nationality as string | undefined;
  if (loggedIn) {
    const languages = Object.fromEntries(((a.study_language as string[]) ?? []).map((l) => [l, "?"]));
    await api("/api/profile", { method: "PUT", body: JSON.stringify({
      nationalities: nat ? [nat] : undefined, residence_country: a.residence_country || undefined, birth_date: a.birth_date || undefined,
      current_level: a.current_level || undefined, grade_average: a.grade_average === "" || a.grade_average == null ? undefined : Number(a.grade_average),
      target_level: a.target_level || undefined, domain: a.domain || undefined, wished_countries: a.wished_countries ?? undefined,
      languages: Object.keys(languages).length ? languages : undefined, full_funding_only: Boolean(a.full_funding_only), situations: a.situations ?? undefined,
    }) });
    const m = await api<{ items: Match[] }>("/api/matches");
    return { total_matches: m.items.length, items: m.items, recommended_offer: a.help_wanted === "accompagne" ? "standard" : null, profile_saved: true };
  }
  const p = new URLSearchParams({ per_page: "100" });
  if (a.target_level) p.set("level", String(a.target_level));
  if (nat) p.set("nationality", nat);
  if (a.full_funding_only) p.set("full_funding", "true");
  const page = await api<{ items: Scholarship[] }>(`/api/scholarships?${p}`);
  const wished = (a.wished_countries as string[]) ?? [];
  const items = page.items.filter((s) =>
    (!a.domain || !s.domains.length || s.domains.includes("tous") || s.domains.includes(String(a.domain))) &&
    (!wished.length || !s.study_countries.length || s.study_countries.some((c) => wished.includes(c))),
  );
  return {
    total_matches: items.length,
    items: items.slice(0, 3).map((s) => ({ scholarship: s, score: 0, chance: "moyenne", reasons: [], gaps: [], days_left: null })),
    recommended_offer: a.help_wanted === "accompagne" ? "standard" : null,
  };
}

function Field({ q, value, onChange, meta, answers }: { q: Question; value: unknown; onChange: (v: unknown) => void; meta: Meta | null; answers: Answers }) {
  const { t, lang } = useT();
  const chosenRegions = q.filter_by ? ((answers[q.filter_by] as string[] | undefined) ?? []) : [];
  const opts = optionsOf(q, meta, lang).filter((o) => !chosenRegions.length || chosenRegions.includes(o.region ?? ""));
  const id = `q-${q.id}`;
  const label = <label className="label" htmlFor={id}>{q.label}{q.required && <span className="text-gold-dark"> *</span>}</label>;
  const hint = q.help ?? (q.type === "date" ? q.placeholder : undefined);
  const help = hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>;
  if (q.type === "language_scores") {
    const v = (value as Record<string, number>) ?? {};
    return (
      <div>
        {label}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {opts.map((o) => (
            <label key={o.value} className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-sm">
              <span className="w-14 shrink-0 font-semibold">{o.label}</span>
              <input type="number" step="0.5" min={0} inputMode="decimal" className="w-full bg-transparent text-right outline-none placeholder:text-muted/60" placeholder={t("score")}
                value={v[o.value] ?? ""} onChange={(e) => {
                  const next = { ...v };
                  if (e.target.value === "") delete next[o.value]; else next[o.value] = Number(e.target.value);
                  onChange(next);
                }} />
            </label>
          ))}
        </div>
        <p className="mt-1.5 text-xs text-muted">{t("Laissez vide les tests que vous n'avez pas passés.")}</p>
      </div>
    );
  }
  if (q.type === "text")
    return (
      <div>
        {label}
        <textarea id={id} rows={3} className="input" placeholder={q.placeholder} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />
        {help}
      </div>
    );
  if (q.type === "boolean")
    return (
      <label className="flex cursor-pointer items-center gap-3 rounded-2xl border border-line bg-surface p-4 text-sm">
        <input id={id} type="checkbox" className="h-4 w-4 accent-[#3ee0a8]" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
        {q.label}
      </label>
    );
  if (q.type === "multiselect" || q.type === "countries") {
    const list = (value as string[]) ?? [];
    const toggle = (v: string) => onChange(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
    if (q.type === "countries")
      return (
        <div>
          {label}
          {list.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {list.map((c) => (
                <button key={c} type="button" onClick={() => toggle(c)} className="inline-flex items-center gap-1 rounded-full bg-brand-soft px-3 py-1 text-xs font-semibold text-brand">
                  {meta?.countries[c] ?? c}<Icon name="close" className="h-3 w-3" />
                </button>
              ))}
            </div>
          )}
          <select id={id} className="input" value="" onChange={(e) => e.target.value && toggle(e.target.value)}>
            <option value="">{chosenRegions.length === 1 ? t("Ajouter un pays de ce continent…") : chosenRegions.length > 1 ? t("Ajouter un pays de ces continents…") : t("Ajouter un pays…")}</option>
            {opts.filter((o) => !list.includes(o.value)).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          {chosenRegions.length > 0 && <p className="mt-1.5 text-xs text-muted">{t("La liste ne montre que les pays des continents que vous avez choisis.")}</p>}
          {help}
        </div>
      );
    return (
      <div>
        {label}
        <div className="flex flex-wrap gap-2">
          {opts.map((o) => (
            <button key={o.value} type="button" onClick={() => toggle(o.value)} aria-pressed={list.includes(o.value)}
              className={`rounded-full border px-3.5 py-2 text-sm transition ${list.includes(o.value) ? "border-brand bg-brand-soft font-semibold text-brand" : "border-line bg-surface text-muted hover:text-ink"}`}>
              {o.label}
            </button>
          ))}
        </div>
        {help}
      </div>
    );
  }
  if (q.type === "select" && opts.length <= 6)
    return (
      <div>
        {label}
        <div className="grid gap-2 sm:grid-cols-2">
          {opts.map((o) => (
            <button key={o.value} type="button" onClick={() => onChange(o.value)} aria-pressed={value === o.value}
              className={`flex items-center justify-between gap-2 rounded-2xl border px-4 py-3 text-left text-sm transition ${value === o.value ? "border-brand bg-brand-soft/60 font-semibold text-ink" : "border-line bg-surface text-muted hover:border-brand/40 hover:text-ink"}`}>
              {o.label}
              <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full border ${value === o.value ? "border-brand bg-mint text-[#04140e]" : "border-line"}`}>{value === o.value && <Icon name="check" className="h-3 w-3" />}</span>
            </button>
          ))}
        </div>
        {help}
      </div>
    );
  if (q.type === "select" || q.type === "country")
    return (
      <div>
        {label}
        <select id={id} className="input" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)}
          autoComplete={q.id === "residence_country" ? "country" : undefined}>
          <option value="">{t("Choisir…")}</option>
          {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        {help}
      </div>
    );
  return (
    <div>
      {label}
      <input id={id} className="input" type={q.type === "number" ? "number" : q.type === "date" ? "date" : "text"}
        step={q.type === "number" ? "0.1" : undefined} min={q.type === "number" ? 0 : undefined} max={q.type === "number" ? 20 : undefined}
        autoComplete={q.type === "date" && q.id.includes("birth") ? "bday" : undefined}
        placeholder={q.type === "date" ? undefined : q.placeholder} value={(value as string | number) ?? ""} onChange={(e) => onChange(e.target.value)} />
      {help}
    </div>
  );
}

function Questionnaire() {
  const { t } = useT();
  const { me, ready } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [remote, setRemote] = useState<Step[] | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMeta().then(setMeta).catch(() => setError(t("Le service n'est pas joignable pour le moment. Réessayez dans un instant.")));
    api<{ steps: Step[] }>("/api/questionnaire").then((d) => d.steps?.length && setRemote(d.steps)).catch(() => {});
    try { const saved = localStorage.getItem(STORE); if (saved) setAnswers(JSON.parse(saved)); } catch { /* stockage indisponible */ }
  }, []);
  useEffect(() => { try { localStorage.setItem(STORE, JSON.stringify(answers)); } catch { /* idem */ } }, [answers]);

  const steps = useMemo(() => translateSteps(remote ?? (meta ? localSteps(meta) : []), t), [remote, meta, t]);
  const current = steps[step];

  /** Enregistre une réponse. Si des continents sont choisis, les pays précis hors de ces continents sont retirés. */
  function setAnswer(id: string, v: unknown) {
    setAnswers((a) => {
      const next: Answers = { ...a, [id]: v };
      const regions = Array.isArray(v) ? (v as string[]) : [];
      for (const q of steps.flatMap((s) => s.questions)) {
        if (q.filter_by !== id || !regions.length || !Array.isArray(next[q.id])) continue;
        const map = regionMap(q);
        next[q.id] = (next[q.id] as string[]).filter((c) => regions.includes(map[c] ?? regionOf(c) ?? ""));
      }
      return next;
    });
  }
  const missing = current?.questions.filter((q) => q.required && isEmpty(answers[q.id])) ?? [];

  async function submit() {
    setBusy(true); setError(null);
    try {
      let r: Result;
      try {
        if (remote) r = await api<Result>("/api/questionnaire", { method: "POST", body: JSON.stringify({ answers }) });
        else throw new Error("local");
      } catch {
        r = await fallbackMatch(answers, Boolean(me));
      }
      setResult(r);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError((e as Error).message);
    } finally { setBusy(false); }
  }

  // Retour après création de compte : on relance le calcul avec le compte pour enregistrer le profil.
  const auto = params.get("etape") === "resultats";
  useEffect(() => {
    if (auto && ready && steps.length && !result && !busy && Object.keys(answers).length) submit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, ready, steps.length]);

  // Connexion ou inscription faite dans la fenêtre par-dessus le résultat : on recalcule avec le compte.
  const meId = me?.id;
  useEffect(() => {
    if (meId && result && !result.profile_saved && !busy) submit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meId]);

  if (error && !steps.length) return <div className="mx-auto max-w-xl py-16 text-center text-muted">{error}</div>;
  if (!steps.length) return <div className="mx-auto max-w-xl py-16 text-center text-muted">{t("Chargement…")}</div>;

  if (result) return <Results result={result} meta={meta} loggedIn={Boolean(me)} onRestart={() => { setResult(null); setStep(0); }} />;

  const last = step === steps.length - 1;
  return (
    <div className="relative mx-auto max-w-5xl py-4 sm:py-8">
      <div className="bg-grid pointer-events-none absolute inset-0 -z-10" />
      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <aside className="relative overflow-hidden rounded-3xl bg-night p-6 text-white">
          <div className="pointer-events-none absolute -left-20 -top-20 h-56 w-56 rounded-full bg-mint/25 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-24 -right-16 h-56 w-56 rounded-full bg-gold/20 blur-3xl" />
          <p className="relative font-mono text-[11px] uppercase tracking-[0.18em] text-[#3ee0a8]">{t("Votre profil ·")} {steps.length} {t("étapes")}</p>
          <h1 className="relative mt-3 text-[1.65rem] sm:text-3xl leading-tight text-white">{t("Trouvons vos")} <span className="accent">{t("bourses.")}</span></h1>
          <p className="relative mt-2 text-sm text-white/60">{t("Deux minutes. Vos réponses restent sur cet appareil tant que vous ne créez pas de compte.")}</p>
          <ol className="relative mt-6 space-y-1">
            {steps.map((s, i) => (
              <li key={s.id}>
                <button type="button" disabled={i > step} onClick={() => setStep(i)}
                  className={`flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm transition ${i === step ? "bg-white/10 text-white" : i < step ? "text-white/80 hover:bg-white/5" : "text-white/35"}`}>
                  <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full font-mono text-[11px] transition ${i < step ? "bg-[#3ee0a8] text-[#04140e]" : i === step ? "border border-[#3ee0a8] text-[#3ee0a8]" : "border border-white/20"}`}>
                    {i < step ? <Icon name="check" className="h-3.5 w-3.5" /> : i + 1}
                  </span>
                  {s.title}
                </button>
              </li>
            ))}
          </ol>
        </aside>

        <section className="card relative overflow-hidden p-6 sm:p-8">
          <div className="absolute inset-x-0 top-0 h-1 bg-surface">
            <div className="h-full bg-gradient-to-r from-mint to-gold transition-all duration-500" style={{ width: `${(100 * (step + 1)) / steps.length}%` }} />
          </div>
          <div key={current.id} className="animate-step-in">
            <p className="eyebrow">{t("Étape {a} sur {b}", { a: step + 1, b: steps.length })}</p>
            <h2 className="mt-2 text-[1.65rem] sm:text-3xl">{current.title}</h2>
            {current.subtitle && <p className="mt-1 text-muted">{current.subtitle}</p>}
            <div className="mt-7 space-y-6">
              {current.questions.map((q) => (
                <Field key={q.id} q={q} meta={meta} answers={answers} value={answers[q.id]} onChange={(v) => setAnswer(q.id, v)} />
              ))}
            </div>
          </div>
          {error && <p className="mt-4 text-sm text-danger">{error}</p>}
          <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
            <button type="button" className="text-sm text-muted hover:text-ink disabled:opacity-0" disabled={step === 0} onClick={() => setStep(step - 1)}>{t("← Retour")}</button>
            <div className="flex items-center gap-3">
              {missing.length > 0 && <span className="hidden text-xs text-muted sm:inline">{t("Encore :")} {missing.map((q) => q.label.toLowerCase()).join(", ")}</span>}
              <button type="button" className="btn-primary" disabled={missing.length > 0 || busy}
                onClick={() => (last ? submit() : setStep(step + 1))}>
                {busy ? "Recherche…" : last ? t("Voir mes bourses") : t("Continuer")} <Icon name="arrow" />
              </button>
            </div>
          </div>
        </section>
      </div>
      {!me && ready && (
        <p className="mt-6 text-center text-xs text-muted">{t("Déjà un compte ?")} <button className="font-semibold text-brand hover:underline" onClick={() => router.push("/connexion?next=/mes-bourses")}>{t("Connectez-vous")}</button> {t("pour voir directement vos scores.")}</p>
      )}
    </div>
  );
}

function Results({ result, meta, loggedIn, onRestart }: { result: Result; meta: Meta | null; loggedIn: boolean; onRestart: () => void }) {
  const { t } = useT();
  const n = result.total_matches;
  const max = loggedIn ? 6 : 3;
  // Les bourses des pays ou continents choisis d'abord, puis « Autres bourses disponibles ».
  const split = Boolean(result.has_destination);
  const inDest = split ? result.items.filter((m) => m.in_destination) : result.items;
  const others = split ? result.items.filter((m) => !m.in_destination) : [];
  const shown = inDest.slice(0, max);
  const shownOthers = others.slice(0, Math.max(loggedIn ? 4 : 0, max - shown.length));
  const destTotal = result.destination_total ?? inDest.length;
  const card = (m: Match) => (
    <ScholarshipCard key={m.scholarship.id} s={m.scholarship} meta={meta} loggedIn={loggedIn}
      match={loggedIn && m.score != null ? m : undefined} lockedScore={!loggedIn} />
  );
  return (
    <div className="mx-auto max-w-5xl space-y-10 py-4 sm:py-8">
      <div className="relative overflow-hidden rounded-3xl bg-night p-6 text-white sm:p-10">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-mint/25 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 left-10 h-60 w-60 rounded-full bg-gold/15 blur-3xl" />
        <p className="relative font-mono text-[11px] uppercase tracking-[0.18em] text-[#3ee0a8]">{t("Votre résultat")}</p>
        <h1 className="relative mt-3 max-w-2xl text-[1.65rem] sm:text-3xl leading-tight text-white sm:text-5xl">
          {n > 0 ? <><span className="text-[#3ee0a8]">{n}</span> {t(n > 1 ? "bourses correspondent" : "bourse correspond")} <span className="accent">{t("à votre profil.")}</span></> : <>{t("Aucune bourse ouverte")} <span className="accent">{t("pour l'instant.")}</span></>}
        </h1>
        <p className="relative mt-3 max-w-xl text-sm text-white/65">
          {loggedIn
            ? t("Votre profil est enregistré. Chaque bourse a maintenant un score de compatibilité et la liste de ce qu'il vous manque.")
            : n > 0 ? `Voici ${Math.min(3, n)} d'entre elles. Créez votre compte gratuit pour voir toute la liste, votre score pour chacune et ce qui peut le faire monter.` : t("De nouvelles bourses sont ajoutées chaque semaine. Créez votre compte pour être prévenu dès qu'une bourse vous correspond.")}
        </p>
        {result.missing && result.missing.length > 0 && <p className="relative mt-3 text-xs text-white/50">{t("Pour un résultat plus précis, complétez :")} {result.missing.join(", ")}.</p>}
        <div className="relative mt-6 flex flex-wrap gap-3">
          {loggedIn
            ? <Link href="/mes-bourses" className="btn-primary">{t("Voir toutes mes bourses et mes scores")} <Icon name="arrow" /></Link>
            : <Link href={`/connexion?mode=inscription&next=${encodeURIComponent("/questionnaire?etape=resultats")}`} className="btn-primary">{t("Créer mon compte et voir mes scores")} <Icon name="arrow" /></Link>}
          <button type="button" onClick={onRestart} className="btn rounded-full border border-white/15 text-white hover:border-white/40">{t("Modifier mes réponses")}</button>
        </div>
      </div>

      {split && (
        <section>
          <p className="eyebrow">{t("Dans votre destination")}</p>
          <h2 className="mt-2 text-xl sm:text-2xl">
            {destTotal > 0
              ? t(destTotal > 1 ? "{n} bourses dans les pays que vous avez choisis" : "{n} bourse dans les pays que vous avez choisis", { n: destTotal })
              : t("Aucune bourse ouverte pour l'instant dans les pays que vous avez choisis")}
          </h2>
          {destTotal === 0 && <p className="mt-1 text-sm text-muted">{t("Nous vous prévenons dès qu'une bourse s'ouvre dans ces pays. En attendant, voici les autres bourses qui correspondent à votre profil.")}</p>}
          {shown.length > 0 && <div className="mt-4 grid gap-4 lg:grid-cols-2">{shown.map(card)}</div>}
        </section>
      )}

      {split && shownOthers.length > 0 && (
        <section>
          <p className="eyebrow">{t("Ailleurs dans le monde")}</p>
          <h2 className="mt-2 text-xl sm:text-2xl">{t("Autres bourses disponibles")}</h2>
          <p className="mt-1 text-sm text-muted">{t("Elles correspondent à votre profil, dans d'autres pays que ceux que vous avez choisis.")}</p>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">{shownOthers.map(card)}</div>
        </section>
      )}

      {(split ? !loggedIn && n > 3 : shown.length > 0) && (
        <section>
          {!split && (
            <>
              <p className="eyebrow">{loggedIn ? t("Les mieux classées") : t("Un aperçu")}</p>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">{shown.map(card)}</div>
            </>
          )}
          {!loggedIn && n > 3 && (
            <div className="relative mt-4 overflow-hidden rounded-2xl border border-dashed border-line p-6 text-center">
              <p className="font-semibold"><Icon name="lock" className="mr-1 inline h-4 w-4 text-brand" />{t(n - 3 > 1 ? "{n} autres bourses vous attendent" : "{n} autre bourse vous attend", { n: n - 3 })}</p>
              <p className="mt-1 text-sm text-muted">{t("Visibles avec votre score dès la création de votre compte.")}</p>
            </div>
          )}
        </section>
      )}

      <section>
        <p className="eyebrow">{t("Et maintenant")}</p>
        <h2 className="mt-2 text-[1.65rem] sm:text-3xl">{t("Postulez seul, ou faites-vous")} <span className="accent">{t("accompagner.")}</span></h2>
        <div className="mt-6">
          <AdvisorBanner note={result.recommended_offer ? <>{t("D'après vos réponses, la formule")} <span className="font-semibold">{result.recommended_offer === "premium" ? t("Premium") : t("Standard")}</span> {t("vous conviendrait.")}</> : undefined} />
        </div>
      </section>
    </div>
  );
}

export default function Page() {
  return <Suspense><Questionnaire /></Suspense>;
}
