"use client";
import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import Icon from "@/components/Icon";
import PaperLetter from "@/components/docs/PaperLetter";
import { CreditsBar, PayModal } from "@/components/docs/Credits";
import { Meta, Scholarship, api, getMeta } from "@/lib/api";
import { Credits, Doc, DocError, LetterData, docApi, downloadDoc } from "@/lib/docs";
import { useT } from "@/components/LangProvider";

type Context = {
  missing: { field: string; label: string }[];
  language: "fr" | "en";
  style: string;
  questions: { key: string; label: string }[];
  answers: Record<string, string>;
  document: Doc<LetterData> | null;
  credits: Credits;
  header: { full_name: string | null; phone: string | null; city: string | null; address: string | null; residence_country: string | null; gender: string | null; email: string };
};

const HINTS: Record<string, { ph: string; help: string }> = {
  target_program: { ph: "ex. Master Public Health Informatics, Université de Heidelberg", help: "Apparaît dans l'objet et dans la lettre." },
  why_country: { ph: "Une raison académique et une raison personnelle, avec un fait précis", help: "Ce que ce pays offre pour votre domaine que vous ne trouvez pas ailleurs." },
  why_program: { ph: "Un cours, un laboratoire, une méthode, une valeur de l'organisme", help: "Citez ce qui vous a fait choisir ce programme plutôt qu'un autre." },
  study_plan: { ph: "Cours que vous suivrez, sujet de mémoire, stage visé", help: "Ce que vous ferez concrètement pendant vos études." },
  project_after: { ph: "Le métier visé, le problème que vous voulez traiter, pour qui", help: "Les jurys attendent un projet réaliste et utile." },
  proud_of: { ph: "Ce que vous avez fait, pour qui, avec quel résultat", help: "Un seul exemple, bien raconté, vaut mieux que trois cités." },
  extra: { ph: "Un parcours atypique, une difficulté surmontée…", help: "Facultatif." },
};

function HeaderForm({ ctx, meta, onSaved }: { ctx: Context; meta: Meta | null; onSaved: () => void }) {
  const { t, lang } = useT();
  const [f, setF] = useState({ full_name: ctx.header.full_name ?? "", phone: ctx.header.phone ?? "", city: ctx.header.city ?? "", address: ctx.header.address ?? "", residence_country: ctx.header.residence_country ?? "", gender: ctx.header.gender ?? "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const needCv = ctx.missing.some((m) => m.field === "cv");
  const needProfile = ctx.missing.some((m) => m.field === "domain" || m.field === "target_level");
  async function save() {
    setBusy(true);
    setError(null);
    try {
      const body = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, v.trim() || null]));
      await api("/api/profile", { method: "PUT", body: JSON.stringify(body) });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const input = (k: keyof typeof f, label: string, ph = "", type = "text") => (
    <div>
      <label className="label" htmlFor={`h-${k}`}>{t(label)}</label>
      <input id={`h-${k}`} type={type} className="input" placeholder={ph && t(ph)} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
    </div>
  );
  return (
    <div className="card space-y-4 border-gold/40 p-5 sm:p-6">
      <div>
        <p className="eyebrow !text-gold-dark">{t("Avant de rédiger")}</p>
        <h2 className="mt-1 text-lg sm:text-xl">{t("Les informations de votre en-tête")}</h2>
        <p className="mt-1 text-sm text-muted">{t("Elles figurent en haut de la lettre et du CV. Il manque : {x}.", { x: ctx.missing.map((m) => m.label.toLowerCase()).join(", ") })}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {input("full_name", "Nom complet", "Prénom Nom")}
        {input("phone", "Téléphone", "+228 90 00 00 00", "tel")}
        {input("address", "Adresse (facultatif)", "Quartier, rue")}
        {input("city", "Ville", "Lomé")}
        <div>
          <label className="label" htmlFor="h-country">{t("Pays de résidence")}</label>
          <select id="h-country" className="input" value={f.residence_country} onChange={(e) => setF({ ...f, residence_country: e.target.value })}>
            <option value="">{t("Choisir")}</option>
            {meta && Object.entries(meta.countries).sort((a, b) => a[1].localeCompare(b[1], lang)).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="h-gender">{t("Accords dans la lettre")}</label>
          <select id="h-gender" className="input" value={f.gender} onChange={(e) => setF({ ...f, gender: e.target.value })}>
            <option value="">{t("Tournures neutres")}</option>
            <option value="f">{t("Au féminin")}</option>
            <option value="m">{t("Au masculin")}</option>
          </select>
        </div>
      </div>
      {(needCv || needProfile) && (
        <div className="flex flex-wrap gap-2 text-sm">
          {needCv && <Link href="/cv" className="btn-ghost px-3 py-1.5 text-xs"><Icon name="upload" className="h-4 w-4" />{t("Importer mon CV")}</Link>}
          {needProfile && <Link href="/profil" className="btn-ghost px-3 py-1.5 text-xs">{t("Indiquer domaine et diplôme visé")}</Link>}
        </div>
      )}
      {error && <p className="text-sm text-danger">{error}</p>}
      <button className="btn-primary" disabled={busy} onClick={save}>{busy ? t("Enregistrement…") : t("Enregistrer")}</button>
    </div>
  );
}

function LetterTool({ id }: { id: string }) {
  const { t } = useT();
  const [s, setS] = useState<Scholarship | null>(null);
  const [ctx, setCtx] = useState<Context | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [language, setLanguage] = useState<"fr" | "en">("fr");
  const [maxWords, setMaxWords] = useState(450);
  const [tone, setTone] = useState("sobre");
  const [doc, setDoc] = useState<Doc<LetterData> | null>(null);
  const [letter, setLetter] = useState<LetterData | null>(null);
  const [credits, setCredits] = useState<Credits | null>(null);
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [paying, setPaying] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadContext = useCallback(() => {
    docApi<Context>(`/api/letters/${id}/context`).then((c) => {
      setCtx(c);
      setCredits(c.credits);
      setAnswers((a) => (Object.keys(a).length ? a : c.answers || {}));
      setLanguage((c.document?.data.language as "fr" | "en") ?? c.language);
      if (c.document) { setDoc(c.document); setLetter(c.document.data); if (c.document.data.max_words) setMaxWords(c.document.data.max_words); }
    }).catch((e) => setError(e.message));
  }, [id]);

  useEffect(() => {
    api<Scholarship>(`/api/scholarships/${id}`).then(setS).catch((e) => setError(e.message));
    getMeta().then(setMeta).catch(() => null);
    loadContext();
  }, [id, loadContext]);

  async function generate() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const r = await docApi<{ document: Doc<LetterData>; credits: Credits }>("/api/letters", {
        method: "POST", body: JSON.stringify({ scholarship_id: Number(id), ...answers, language, max_words: maxWords, tone }),
      });
      setDoc(r.document);
      setLetter(r.document.data);
      setCredits(r.credits);
      setDirty(false);
      setEditing(false);
      setTimeout(() => document.getElementById("ma-lettre")?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    } catch (e) {
      if (e instanceof DocError && e.code === "abonnement_requis") setPaying(true);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!doc || !letter) return;
    await docApi(`/api/documents/${doc.id}`, { method: "PUT", body: JSON.stringify({ data: letter }) });
    setDirty(false);
    setMsg(t("Modifications enregistrées dans votre suivi."));
  }

  async function download(fmt: "pdf" | "docx") {
    if (!letter) return;
    try {
      if (dirty) await save();
      await downloadDoc("lettre", fmt, letter);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!s || !ctx || !credits) return <p className="text-muted">{error ?? t("Chargement…")}</p>;
  const blocked = ctx.missing.length > 0;
  const pack = credits.packs.find((p) => p.scholarship_id === s.id);
  const runsLeft = credits.regenerations - (pack?.letter_runs ?? 0);
  const words = letter ? letter.paragraphs.join(" ").split(/\s+/).filter(Boolean).length : 0;

  return (
    <div className="space-y-8">
      <div className="max-w-3xl">
        <Link href={`/bourses/${s.id}`} className="inline-flex items-center gap-1 text-sm text-brand hover:underline"><span aria-hidden>←</span> {s.title}</Link>
        <h1 className="mt-2 text-[28px] leading-tight sm:text-4xl">{t("Lettre de motivation")}</h1>
        <p className="mt-2 text-sm text-muted sm:text-base">
          {t("Rédigée pour {org}, à partir de votre profil, de votre CV et de vos réponses.", { org: s.organization })} {language === "en" ? t("Présentation anglophone : date, formule d'appel et formule de politesse selon l'usage.") : t("Présentation française : coordonnées, destinataire, lieu et date, objet et formule de politesse.")}
        </p>
        <Link href={`/preparer/${s.id}`} className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:underline">{t("Vérifier ma compatibilité avec la bourse")} <Icon name="arrow" className="h-4 w-4" /></Link>
      </div>

      {blocked && <HeaderForm ctx={ctx} meta={meta} onSaved={loadContext} />}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <section className={`space-y-4 ${blocked ? "pointer-events-none opacity-50" : ""}`} aria-disabled={blocked}>
          <div className="card space-y-4 p-5 sm:p-6">
            <div>
              <h2 className="text-lg sm:text-xl">{t("Vos réponses")}</h2>
              <p className="mt-1 text-sm text-muted">{t("Toutes facultatives. Plus elles sont précises, plus la lettre vous ressemble.")}</p>
            </div>
            {ctx.questions.map((q) => (
              <div key={q.key}>
                <label className="label" htmlFor={`q-${q.key}`}>{q.label}</label>
                {q.key === "target_program" ? (
                  <input id={`q-${q.key}`} className="input" placeholder={HINTS[q.key] ? t(HINTS[q.key].ph) : undefined} value={answers[q.key] ?? ""} onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })} />
                ) : (
                  <textarea id={`q-${q.key}`} className="input" rows={q.key === "extra" ? 2 : 3} placeholder={HINTS[q.key] ? t(HINTS[q.key].ph) : undefined} value={answers[q.key] ?? ""} onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })} />
                )}
                {HINTS[q.key] && <p className="mt-1 text-xs text-muted">{t(HINTS[q.key].help)}</p>}
              </div>
            ))}
            <details className="rounded-xl border border-line p-3">
              <summary className="cursor-pointer text-sm font-semibold">{t("Adresse du destinataire")}</summary>
              <textarea className="input mt-3" rows={3} placeholder={t("Service des bourses\nAdresse\nVille, pays")} value={answers.recipient_address ?? ""} onChange={(e) => setAnswers({ ...answers, recipient_address: e.target.value })} />
            </details>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <label className="label" htmlFor="l-lang">{t("Langue")}</label>
                <select id="l-lang" className="input" value={language} onChange={(e) => setLanguage(e.target.value as "fr" | "en")}><option value="fr">{t("Français")}</option><option value="en">{t("Anglais")}</option></select>
              </div>
              <div>
                <label className="label" htmlFor="l-len">{t("Longueur")}</label>
                <select id="l-len" className="input" value={maxWords} onChange={(e) => setMaxWords(Number(e.target.value))}>
                  <option value={300}>{t("Courte, 300 mots")}</option><option value={450}>{t("Une page, 450 mots")}</option><option value={650}>{t("Détaillée, 650 mots")}</option><option value={900}>{t("Longue, 900 mots")}</option>
                </select>
              </div>
              <div>
                <label className="label" htmlFor="l-tone">{t("Ton")}</label>
                <select id="l-tone" className="input" value={tone} onChange={(e) => setTone(e.target.value)}><option value="sobre">{t("Sobre")}</option><option value="chaleureux">{t("Chaleureux")}</option><option value="dynamique">{t("Dynamique")}</option></select>
              </div>
            </div>
            {!letter && <CreditsBar credits={credits} onBuy={() => setPaying(true)} compact />}
            <button className="btn-primary w-full" disabled={busy || blocked || (!!letter && runsLeft <= 0)} onClick={generate}>
              <Icon name="sparkle" className="h-4 w-4" />{busy ? t("Rédaction en cours…") : letter ? t("Régénérer la lettre") : t("Rédiger ma lettre")}
            </button>
            {letter && <p className="text-center text-xs text-muted">{runsLeft > 0 ? (runsLeft > 1 ? t("Encore {n} générations pour cette bourse.", { n: runsLeft }) : t("Encore 1 génération pour cette bourse.")) : t("Générations épuisées pour cette bourse. La lettre reste modifiable.")}</p>}
            {error && <p className="text-sm text-danger" role="alert">{error}</p>}
          </div>
        </section>

        <section id="ma-lettre" className="min-w-0 space-y-3">
          {!letter ? (
            <div className="card grid min-h-[320px] place-items-center p-8 text-center">
              <div>
                <span className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-brand-soft text-brand animate-float"><Icon name="pen" className="h-6 w-6" /></span>
                <p className="font-serif text-xl font-bold">{t("Votre lettre apparaîtra ici")}</p>
                <p className="mt-1 text-sm text-muted">{t("Mise en page prête à envoyer, modifiable avant le téléchargement.")}</p>
              </div>
            </div>
          ) : (
            <>
              <div className="sticky top-16 z-10 flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-card/90 p-2 backdrop-blur">
                <button className={`btn px-3 py-1.5 text-xs ${editing ? "bg-gold text-[#1d1300]" : "btn-ghost"}`} onClick={() => setEditing(!editing)}>
                  <Icon name="pen" className="h-4 w-4" />{editing ? t("Terminer") : t("Modifier")}
                </button>
                {dirty && <button className="btn-ghost px-3 py-1.5 text-xs" onClick={save}>{t("Enregistrer")}</button>}
                <span className={`text-xs ${words > maxWords ? "text-danger" : "text-muted"}`}>{t("{n} mots", { n: words })}</span>
                <span className="flex-1" />
                <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => download("pdf")}><Icon name="file" className="h-4 w-4" />{t("Télécharger en PDF")}</button>
                <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => download("docx")}>Word</button>
              </div>
              {editing && <p className="text-xs text-muted">{t("Cliquez sur un texte pour le modifier. Une ligne vide entre deux phrases crée un nouveau paragraphe.")}</p>}
              <div className="-mx-4 bg-surface/60 px-2 py-4 sm:mx-0 sm:rounded-2xl sm:p-6">
                <PaperLetter letter={letter} editable={editing} onChange={(l) => { setLetter(l); setDirty(true); }} />
              </div>
              {msg && <p className="text-sm text-brand">{msg}</p>}
            </>
          )}
        </section>
      </div>

      {paying && <PayModal credits={credits} onClose={() => setPaying(false)} onDone={() => docApi<Credits>("/api/credits").then(setCredits).catch(() => null)} />}
    </div>
  );
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <RequireAuth><LetterTool id={id} /></RequireAuth>;
}
