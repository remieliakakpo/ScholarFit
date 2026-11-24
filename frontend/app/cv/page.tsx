"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import Icon from "@/components/Icon";
import { ScoreRing } from "@/components/ScholarshipCard";
import PaperCV from "@/components/docs/PaperCV";
import { CreditsBar, PayModal } from "@/components/docs/Credits";
import { Application, Profile, Scholarship, api } from "@/lib/api";
import { CVData, Credits, Diagnostic, Doc, DocError, docApi, downloadDoc } from "@/lib/docs";
import { useT } from "@/components/LangProvider";

const STATUS: Record<string, { label: string; cls: string; bar: string }> = {
  ok: { label: "Conforme", cls: "text-brand", bar: "bg-ok" },
  a_ameliorer: { label: "À améliorer", cls: "text-gold-dark", bar: "bg-gold" },
  manquant: { label: "À reprendre", cls: "text-warm", bar: "bg-warm" },
};

function Step({ n, title, children, done }: { n: number; title: string; children?: React.ReactNode; done?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-bold ${done ? "bg-mint text-[#04140e]" : "border border-line bg-card text-muted"}`}>
        {done ? <Icon name="check" className="h-4 w-4" /> : n}
      </span>
      <h2 className="text-lg sm:text-xl">{title}</h2>
      {children}
    </div>
  );
}

function CVTool() {
  const { t } = useT();
  const params = useSearchParams();
  const router = useRouter();
  const bourseParam = params.get("bourse");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [bourse, setBourse] = useState<Scholarship | null>(null);
  const [pasteMode, setPasteMode] = useState(false);
  const [pasted, setPasted] = useState("");
  const [uploading, setUploading] = useState(false);
  const [diag, setDiag] = useState<Diagnostic | null>(null);
  const [diagBusy, setDiagBusy] = useState(false);
  const [doc, setDoc] = useState<Doc<CVData> | null>(null);
  const [cv, setCv] = useState<CVData | null>(null);
  const [credits, setCredits] = useState<Credits | null>(null);
  const [genBusy, setGenBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [paying, setPaying] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const bourseId = bourse?.id ?? null;

  useEffect(() => {
    api<Profile>("/api/profile").then(setProfile).catch(() => null);
    api<Application[]>("/api/applications").then(setApps).catch(() => null);
  }, []);

  useEffect(() => {
    if (bourseParam) api<Scholarship>(`/api/scholarships/${bourseParam}`).then(setBourse).catch(() => setBourse(null));
    else setBourse(null);
  }, [bourseParam]);

  const loadAdapted = useCallback(() => {
    docApi<{ document: Doc<CVData> | null; credits: Credits }>(`/api/cv/adapted${bourseId ? `?scholarship_id=${bourseId}` : ""}`)
      .then((r) => { setDoc(r.document); setCv(r.document?.data ?? null); setCredits(r.credits); setDirty(false); setEditing(false); })
      .catch(() => null);
  }, [bourseId]);
  useEffect(loadAdapted, [loadAdapted]);

  const runDiagnostic = useCallback(async () => {
    setDiagBusy(true);
    setError(null);
    try {
      setDiag(await docApi<Diagnostic>("/api/cv/review", { method: "POST", body: JSON.stringify({ scholarship_id: bourseId }) }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDiagBusy(false);
    }
  }, [bourseId]);

  useEffect(() => { if (profile?.has_cv) runDiagnostic(); }, [profile?.has_cv, runDiagnostic]);

  async function upload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      setProfile(await api<Profile>("/api/profile/cv", { method: "POST", body: fd }));
      setPasteMode(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function savePasted() {
    const blob = new File([pasted], "cv.txt", { type: "text/plain" });
    await upload(blob);
    setPasted("");
  }

  async function generate() {
    setGenBusy(true);
    setError(null);
    setMsg(null);
    try {
      const r = await docApi<{ document: Doc<CVData>; credits: Credits }>("/api/cv/adapt", { method: "POST", body: JSON.stringify({ scholarship_id: bourseId }) });
      setDoc(r.document);
      setCv(r.document.data);
      setCredits(r.credits);
      setDirty(false);
      setTimeout(() => document.getElementById("cv-adapte")?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    } catch (e) {
      if (e instanceof DocError && e.code === "abonnement_requis") setPaying(true);
      setError((e as Error).message);
    } finally {
      setGenBusy(false);
    }
  }

  async function save() {
    if (!doc || !cv) return;
    await docApi(`/api/documents/${doc.id}`, { method: "PUT", body: JSON.stringify({ data: cv }) });
    setDirty(false);
    setMsg(t("Modifications enregistrées."));
  }

  async function download(fmt: "pdf" | "docx") {
    if (!cv) return;
    try {
      if (dirty) await save();
      await downloadDoc("cv", fmt, cv);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function chooseBourse(id: string) {
    router.replace(id ? `/cv?bourse=${id}` : "/cv", { scroll: false });
  }

  const pack = credits?.packs.find((p) => p.scholarship_id === bourseId);
  const runsLeft = credits ? credits.regenerations - (pack?.cv_runs ?? 0) : 0;
  const tracked = apps.map((a) => a.scholarship);
  const options = bourse && !tracked.some((s) => s.id === bourse.id) ? [bourse, ...tracked] : tracked;

  return (
    <div className="space-y-8 sm:space-y-10">
      <div className="max-w-3xl">
        <p className="eyebrow">{t("Mon CV")}</p>
        <h1 className="mt-2 text-[28px] leading-tight sm:text-4xl">{t("Un CV prêt pour le jury de")} <span className="accent">{t("votre bourse.")}</span></h1>
        <p className="mt-2 text-sm text-muted sm:text-base">{t("Importez votre CV. Nous l'évaluons sur neuf critères précis, puis nous le réécrivons au format attendu dans le pays de la bourse, à partir de votre parcours réel.")}</p>
      </div>

      {/* 1. Import et bourse visée */}
      <section className="space-y-4">
        <Step n={1} title={t("Votre CV et la bourse visée")} done={!!profile?.has_cv} />
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card p-5">
            {profile?.has_cv && !pasteMode ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-soft text-brand"><Icon name="file" className="h-5 w-5" /></span>
                  <div>
                    <p className="font-semibold">{t("CV importé")}</p>
                    <p className="text-xs text-muted">{t("{n} mots lus", { n: (profile.cv_text || "").split(/\s+/).length })}</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => fileRef.current?.click()} disabled={uploading}><Icon name="upload" className="h-4 w-4" /> {t("Remplacer")}</button>
                  <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => { setPasted(profile.cv_text || ""); setPasteMode(true); }}>{t("Modifier le texte")}</button>
                </div>
              </div>
            ) : pasteMode ? (
              <div className="space-y-3">
                <label className="label" htmlFor="cv-text">{t("Texte de votre CV")}</label>
                <textarea id="cv-text" className="input min-h-[220px] text-sm" value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder={"Prénom Nom\nFORMATION\n2022 - 2025 Licence…\nEXPÉRIENCES\n…"} />
                <div className="flex flex-wrap gap-2">
                  <button className="btn-primary" disabled={pasted.trim().length < 30 || uploading} onClick={savePasted}>{uploading ? t("Enregistrement…") : t("Enregistrer")}</button>
                  <button className="btn-ghost" onClick={() => setPasteMode(false)}>{t("Annuler")}</button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) upload(f); }}
                className="flex w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line px-4 py-9 text-center transition hover:border-brand/60"
              >
                <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-soft text-brand animate-float"><Icon name="upload" className="h-6 w-6" /></span>
                <span className="font-semibold">{uploading ? t("Lecture du CV…") : t("Importer mon CV")}</span>
                <span className="text-xs text-muted">{t("PDF, Word (.docx) ou texte, 5 Mo maximum")}</span>
              </button>
            )}
            {!profile?.has_cv && !pasteMode && (
              <button className="mt-3 text-xs font-semibold text-brand hover:underline" onClick={() => setPasteMode(true)}>{t("Ou collez le texte de votre CV")}</button>
            )}
            <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
          </div>
          <div className="card space-y-3 p-5">
            <label className="label" htmlFor="cv-bourse">{t("Bourse visée")}</label>
            <select id="cv-bourse" className="input" value={bourseId ?? ""} onChange={(e) => chooseBourse(e.target.value)}>
              <option value="">{t("Aucune bourse précise (CV international)")}</option>
              {options.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
            </select>
            <p className="text-xs text-muted sm:text-sm">
              {t("Le format, la langue et l'ordre des rubriques suivent la bourse choisie. Pour une autre bourse, ajoutez-la d'abord à")} <Link href="/suivi" className="text-brand hover:underline">{t("votre suivi")}</Link> {t("ou ouvrez sa fiche.")}
            </p>
            {bourse && <Link href={`/preparer/${bourse.id}`} className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:underline">{t("Vérifier ma compatibilité avec cette bourse")} <Icon name="arrow" className="h-4 w-4" /></Link>}
          </div>
        </div>
        {error && <p className="text-sm text-danger" role="alert">{error}</p>}
      </section>

      {/* 2. Diagnostic */}
      {profile?.has_cv && (
        <section className="space-y-4">
          <Step n={2} title={t("Diagnostic")} done={!!diag}>
            <button className="ml-auto text-xs font-semibold text-brand hover:underline disabled:opacity-50" onClick={runDiagnostic} disabled={diagBusy}>{diagBusy ? t("Analyse…") : t("Relancer")}</button>
          </Step>
          {!diag ? (
            <div className="card h-48 animate-pulse" aria-busy="true" />
          ) : (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
              <div className="space-y-4">
                <div className="card overflow-hidden">
                  <div className="flex items-center gap-4 bg-night p-5 text-white">
                    <span className="shrink-0"><ScoreRing value={diag.score} color={diag.score >= 75 ? "#3ee0a8" : diag.score >= 55 ? "#ffb547" : "#ff8a5c"} size={72} /></span>
                    <div>
                      <p className="eyebrow">{t("Score du CV")}</p>
                      <p className="mt-1 text-sm text-white/80">{diag.verdict}</p>
                    </div>
                  </div>
                  {diag.priorities.length > 0 && (
                    <div className="p-5">
                      <h3 className="text-sm font-bold uppercase tracking-[0.08em] text-muted">{t("Trois priorités")}</h3>
                      <ol className="mt-2 space-y-2 text-sm">
                        {diag.priorities.map((p, i) => (
                          <li key={i} className="flex gap-2.5"><span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-gold-soft text-[11px] font-bold text-gold-dark">{i + 1}</span>{p}</li>
                        ))}
                      </ol>
                    </div>
                  )}
                </div>
                {diag.spelling.length > 0 && (
                  <div className="card p-5">
                    <h3 className="text-sm font-bold uppercase tracking-[0.08em] text-muted">{t("Orthographe")}</h3>
                    <ul className="mt-2 space-y-1 text-sm">{diag.spelling.map((s) => <li key={s}>{s}</li>)}</ul>
                  </div>
                )}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {diag.criteria.map((c) => (
                  <div key={c.key} className="card p-4">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold">{c.label}</p>
                      <span className={`text-xs font-semibold ${STATUS[c.status].cls}`}>{t(STATUS[c.status].label)}</span>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-surface"><div className={`h-full rounded-full transition-[width] duration-700 ${STATUS[c.status].bar}`} style={{ width: `${c.score}%` }} /></div>
                    <p className="mt-2 text-xs text-muted sm:text-[13px]">{c.finding}</p>
                    {c.recommendation && <p className="mt-1.5 text-xs sm:text-[13px]">{c.recommendation}</p>}
                  </div>
                ))}
              </div>
              {diag.rewrites.length > 0 && (
                <div className="card p-5 lg:col-span-2">
                  <h3 className="text-sm font-bold uppercase tracking-[0.08em] text-muted">{t("Lignes à reformuler")}</h3>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    {diag.rewrites.map((r, i) => (
                      <div key={i} className="rounded-xl border border-line bg-surface p-3 text-sm">
                        <p className="text-muted line-through decoration-warm/60">{r.original}</p>
                        <p className="mt-1 font-medium">{r.proposal}</p>
                        <p className="mt-1 text-xs text-muted">{r.why}</p>
                      </div>
                    ))}
                  </div>
                  <p className="mt-3 text-xs text-muted">{t("Ces reformulations sont intégrées automatiquement à la version adaptée ci-dessous.")}</p>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* 3. Version adaptée */}
      {profile?.has_cv && credits && (
        <section className="space-y-4" id="cv-adapte">
          <Step n={3} title={bourse ? t("Votre CV adapté à la bourse") : t("Votre CV au format international")} done={!!cv} />
          {!cv && <CreditsBar credits={credits} onBuy={() => setPaying(true)} />}
          {!cv ? (
            <div className="card flex flex-col items-start gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
              <p className="max-w-xl text-sm text-muted">
                {t("Le CV est réécrit avec vos expériences réelles : rubriques dans l'ordre attendu, verbes d'action, mots-clés de la bourse, langue de la candidature et mise en page du pays d'études.")}
              </p>
              <button className="btn-primary shrink-0" disabled={genBusy} onClick={generate}>
                <Icon name="sparkle" className="h-4 w-4" />{genBusy ? t("Rédaction en cours…") : t("Générer mon CV adapté")}
              </button>
            </div>
          ) : (
            <>
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
                <div className="order-2 min-w-0 lg:order-1">
                  <div className="no-print sticky top-16 z-10 mb-3 flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-card/90 p-2 backdrop-blur">
                    <button className={`btn px-3 py-1.5 text-xs ${editing ? "bg-gold text-[#1d1300]" : "btn-ghost"}`} onClick={() => setEditing(!editing)}>
                      <Icon name="pen" className="h-4 w-4" />{editing ? t("Terminer") : t("Modifier")}
                    </button>
                    {dirty && <button className="btn-ghost px-3 py-1.5 text-xs" onClick={save}>{t("Enregistrer")}</button>}
                    <span className="flex-1" />
                    <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => download("pdf")}><Icon name="file" className="h-4 w-4" />{t("Télécharger en PDF")}</button>
                    <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => download("docx")}>Word</button>
                  </div>
                  {editing && <p className="mb-2 text-xs text-muted">{t("Cliquez sur un texte pour le modifier. Videz une ligne pour la retirer.")}</p>}
                  <div className="-mx-4 overflow-x-hidden bg-surface/60 px-2 py-4 sm:mx-0 sm:rounded-2xl sm:p-6">
                    <PaperCV cv={cv} editable={editing} onChange={(v) => { setCv(v); setDirty(true); }} />
                  </div>
                </div>
                <aside className="order-1 space-y-3 lg:order-2">
                  <div className="card p-4">
                    <p className="label">{t("Format appliqué")}</p>
                    <p className="font-semibold">{cv.format_label}</p>
                    <p className="mt-1 text-xs text-muted sm:text-sm">{cv.format_reason}</p>
                  </div>
                  {cv.changes.length > 1 && (
                    <div className="card p-4">
                      <p className="label">{t("Ce qui a été adapté")}</p>
                      <ul className="mt-1 space-y-1.5 text-xs sm:text-sm">
                        {cv.changes.slice(1).map((c) => <li key={c} className="flex gap-2"><Icon name="check" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" />{c}</li>)}
                      </ul>
                    </div>
                  )}
                  <div className="card p-4">
                    <p className="text-xs text-muted sm:text-sm">{runsLeft > 0 ? t("Vous pouvez encore régénérer ce CV {n} fois pour cette bourse.", { n: runsLeft }) : t("Générations épuisées pour cette bourse. Vous pouvez toujours modifier et télécharger le CV.")}</p>
                    <button className="btn-ghost mt-3 w-full text-xs" disabled={genBusy || runsLeft <= 0} onClick={generate}>{genBusy ? t("Rédaction…") : t("Régénérer")}</button>
                    {bourse && <Link href={`/lettre/${bourse.id}`} className="btn-primary mt-2 w-full text-xs">{t("Rédiger la lettre de motivation")}</Link>}
                  </div>
                </aside>
              </div>
              {msg && <p className="text-sm text-brand">{msg}</p>}
            </>
          )}
        </section>
      )}

      {paying && credits && (
        <PayModal credits={credits} onClose={() => setPaying(false)} onDone={() => docApi<Credits>("/api/credits").then(setCredits).catch(() => null)} />
      )}
    </div>
  );
}

export default function Page() {
  return <RequireAuth><Suspense><CVTool /></Suspense></RequireAuth>;
}
