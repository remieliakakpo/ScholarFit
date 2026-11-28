"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { DeadlineBadge } from "@/components/ScholarshipCard";
import { useT } from "@/components/LangProvider";
import CoachingFiles from "@/components/CoachingFiles";
import {
  CoachingDetail, CoachingMeta, Meeting, Meta, Step, api, formatDate, formatDateTime, getCoachingMeta, getMeta,
} from "@/lib/api";

const STATUS_STYLE: Record<string, string> = {
  demande: "bg-warm-soft text-warm",
  en_cours: "bg-brand-soft text-brand-dark",
  termine: "bg-paper text-muted",
  annule: "bg-paper text-muted",
};

export function StatusChip({ status, label }: { status: string; label?: string }) {
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLE[status] ?? "bg-paper text-muted"}`}>{label ?? status}</span>;
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-paper ring-1 ring-line">
      <div className="h-full bg-brand transition-all" style={{ width: `${value}%` }} />
    </div>
  );
}

/** Espace de travail partagé entre le candidat et son conseiller. */
export default function CoachingWorkspace({ id, onChange }: { id: number; onChange?: (c: CoachingDetail) => void }) {
  const { t } = useT();
  const [c, setC] = useState<CoachingDetail | null>(null);
  const [cm, setCm] = useState<CoachingMeta | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"plan" | "messages" | "rdv" | "dossier" | "documents">("plan");

  const reload = useCallback(async () => {
    try {
      const d = await api<CoachingDetail>(`/api/accompagnement/${id}`);
      setC(d);
      onChange?.(d);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id, onChange]);

  useEffect(() => {
    getCoachingMeta().then(setCm);
    getMeta().then(setMeta);
    reload();
  }, [reload]);

  // nouveaux messages toutes les 30 s quand l'onglet messages est ouvert
  useEffect(() => {
    if (tab !== "messages" || !c || c.status !== "en_cours") return;
    const t = setInterval(reload, 30000);
    return () => clearInterval(t);
  }, [tab, c, reload]);

  if (error) return <p className="text-danger">{error}</p>;
  if (!c || !cm) return <p className="text-muted">{t("Chargement…")}</p>;

  const isAdvisor = c.my_role !== "candidat";
  const open = c.status === "en_cours" || c.status === "demande";
  const tabs: { k: typeof tab; label: string }[] = [
    { k: "plan", label: `Plan · ${c.progress} %` },
    { k: "messages", label: `Messages${c.messages.length ? ` · ${c.messages.length}` : ""}` },
    { k: "rdv", label: "Rendez-vous" },
    { k: "documents", label: `${t("Documents")}${c.files?.length ? ` · ${c.files.length}` : ""}` },
    { k: "dossier", label: isAdvisor ? t("Dossier du candidat") : t("Mes candidatures") },
  ];

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusChip status={c.status} label={cm.statuses[c.status]} />
              {c.needs.map((n) => <span key={n} className="chip">{cm.needs[n] ?? n}</span>)}
              {c.offer_name && <span className="chip">{c.offer_name}</span>}
              {c.payment_status === "paye" && <span className="chip border-brand/40 text-brand">{t("Payé")}</span>}
              {c.payment_status === "a_payer" && <span className="chip border-warm/40 text-warm">{t("En attente de paiement")}</span>}
            </div>
            <p className="mt-3 font-serif text-lg leading-snug">{c.goal}</p>
            {c.availability && <p className="mt-1 text-sm text-muted">{t("Disponibilités :")} {c.availability}</p>}
          </div>
          <div className="text-right text-sm">
            {isAdvisor ? (
              <p><span className="text-muted">{t("Candidat :")}</span> <strong>{c.student_name}</strong></p>
            ) : c.advisor ? (
              <p><span className="text-muted">{t("Votre conseiller :")}</span> <strong>{c.advisor.display_name}</strong></p>
            ) : (
              <p className="text-warm">{t("Conseiller en cours d'attribution")}</p>
            )}
            {c.next_meeting && <p className="mt-1 text-muted">{t("Prochain rendez-vous :")} {formatDateTime(c.next_meeting.starts_at)}</p>}
          </div>
        </div>
        {!isAdvisor && c.advisor?.bio && <p className="mt-3 border-t border-line pt-3 text-sm text-muted">{c.advisor.bio}</p>}
        <div className="mt-4"><ProgressBar value={c.progress} /></div>
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-line" role="tablist">
        {tabs.map((t) => (
          <button key={t.k} role="tab" aria-selected={tab === t.k} onClick={() => setTab(t.k)}
            className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${tab === t.k ? "border-brand font-semibold text-brand-dark" : "border-transparent text-muted hover:text-ink"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "plan" && <Plan c={c} isAdvisor={isAdvisor} open={open} reload={reload} />}
      {tab === "messages" && <Messages c={c} open={open} reload={reload} />}
      {tab === "rdv" && <Meetings c={c} cm={cm} isAdvisor={isAdvisor} reload={reload} />}
      {tab === "documents" && <CoachingFiles c={c} open={open} isAdvisor={isAdvisor} reload={reload} />}
      {tab === "dossier" && <Dossier c={c} meta={meta} isAdvisor={isAdvisor} />}

      {isAdvisor && c.status === "en_cours" && <FinishBox id={c.id} reload={reload} />}
    </div>
  );
}

// ---------- Plan d'étapes ----------
function Plan({ c, isAdvisor, open, reload }: { c: CoachingDetail; isAdvisor: boolean; open: boolean; reload: () => void }) {
  const { t } = useT();
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const today = new Date().toISOString().slice(0, 10);

  async function patch(s: Step, body: object) {
    try { await api(`/api/accompagnement/etapes/${s.id}`, { method: "PATCH", body: JSON.stringify(body) }); reload(); }
    catch (e) { setErr((e as Error).message); }
  }
  async function add(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api(`/api/accompagnement/${c.id}/etapes`, { method: "POST", body: JSON.stringify({ title, due_date: due || null }) });
      setTitle(""); setDue(""); reload();
    } catch (e2) { setErr((e2 as Error).message); }
  }

  if (!c.steps.length)
    return <p className="card p-6 text-center text-muted">{t("Votre plan d'étapes sera prêt dès qu'un expert vous sera attribué.")}</p>;

  return (
    <div className="space-y-3">
      {err && <p className="text-sm text-danger">{err}</p>}
      <ol className="card divide-y divide-line">
        {c.steps.map((s) => {
          const late = !s.done && s.due_date && s.due_date < today;
          return (
            <li key={s.id} className="flex items-start gap-3 px-4 py-3">
              <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--color-brand)]" checked={s.done} disabled={!open}
                onChange={(e) => patch(s, { done: e.target.checked })} aria-label={`Étape faite : ${s.title}`} />
              <div className="min-w-0 flex-1">
                <p className={`font-medium ${s.done ? "text-muted line-through" : ""}`}>{s.title}</p>
                {s.description && <p className="text-sm text-muted">{s.description}</p>}
              </div>
              <div className="shrink-0 text-right text-xs">
                {s.due_date && <p className={late ? "font-semibold text-danger" : "text-muted"}>{late ? t("En retard · ") : ""}{formatDate(s.due_date)}</p>}
                {isAdvisor && open && (
                  <div className="mt-1 flex justify-end gap-2">
                    <input type="date" className="rounded border border-line px-1 text-xs" defaultValue={s.due_date ?? ""} aria-label={t("Changer l'échéance")}
                      onBlur={(e) => e.target.value !== (s.due_date ?? "") && patch(s, { due_date: e.target.value || null })} />
                    <button className="text-danger hover:underline" onClick={async () => {
                      if (!confirm(t("Supprimer cette étape ?"))) return;
                      await api(`/api/accompagnement/etapes/${s.id}`, { method: "DELETE" }); reload();
                    }}>{t("Suppr.")}</button>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {open && (
        <form onSubmit={add} className="flex flex-wrap gap-2">
          <input className="input min-w-0 flex-1" placeholder={isAdvisor ? t("Ajouter une étape pour le candidat") : t("Ajouter une étape pour vous")} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} />
          <input type="date" className="input w-auto" value={due} min={today} onChange={(e) => setDue(e.target.value)} aria-label={t("Échéance")} />
          <button className="btn-primary">{t("Ajouter")}</button>
        </form>
      )}
    </div>
  );
}

// ---------- Messages ----------
function Messages({ c, open, reload }: { c: CoachingDetail; open: boolean; reload: () => void }) {
  const { t } = useT();
  const [text, setText] = useState("");
  const [appId, setAppId] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const appTitle = (id: number | null) => c.applications.find((a) => a.id === id)?.scholarship.title;

  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [c.messages.length]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    try {
      await api(`/api/accompagnement/${c.id}/messages`, { method: "POST", body: JSON.stringify({ content: text, application_id: appId ? Number(appId) : null }) });
      setText(""); setAppId(""); reload();
    } catch (e2) { setErr((e2 as Error).message); }
    finally { setSending(false); }
  }

  return (
    <div className="card flex flex-col">
      <div className="max-h-[28rem] min-h-40 space-y-3 overflow-y-auto p-4">
        {c.messages.length === 0 && <p className="py-8 text-center text-sm text-muted">{t("Aucun message pour l'instant. Présentez-vous et posez votre première question.")}</p>}
        {c.messages.map((m) => (
          <div key={m.id} className={`flex ${m.mine ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${m.mine ? "bg-mint text-[#04140e]" : "bg-surface ring-1 ring-line"}`}>
              {!m.mine && <p className="mb-0.5 text-xs font-semibold text-brand-dark">{m.author_name ?? (m.author_role === "candidat" ? t("Candidat") : t("Conseiller"))}</p>}
              {m.application_id && appTitle(m.application_id) && <p className={`mb-1 text-xs ${m.mine ? "text-[#04140e]/70" : "text-muted"}`}>{t("À propos de :")} {appTitle(m.application_id)}</p>}
              <p className="whitespace-pre-wrap">{m.content}</p>
              <p className={`mt-1 text-[11px] ${m.mine ? "text-[#04140e]/60" : "text-muted"}`}>{formatDateTime(m.created_at)}</p>
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>
      {open ? (
        <form onSubmit={send} className="space-y-2 border-t border-line p-3">
          {err && <p className="text-sm text-danger">{err}</p>}
          <textarea className="input" rows={3} placeholder={t("Votre message…")} value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send(e); }} />
          <div className="flex flex-wrap items-center justify-between gap-2">
            {c.applications.length > 0 ? (
              <select className="input w-auto" value={appId} onChange={(e) => setAppId(e.target.value)} aria-label={t("Candidature concernée")}>
                <option value="">{t("Message général")}</option>
                {c.applications.map((a) => <option key={a.id} value={a.id}>{a.scholarship.title}</option>)}
              </select>
            ) : <span />}
            <button className="btn-primary" disabled={sending || !text.trim()}>{sending ? "Envoi…" : t("Envoyer")}</button>
          </div>
        </form>
      ) : <p className="border-t border-line p-3 text-center text-sm text-muted">{t("Accompagnement clos : la conversation est en lecture seule.")}</p>}
    </div>
  );
}

// ---------- Rendez-vous ----------
function Meetings({ c, cm, isAdvisor, reload }: { c: CoachingDetail; cm: CoachingMeta; isAdvisor: boolean; reload: () => void }) {
  const { t } = useT();
  const [form, setForm] = useState({ starts_at: "", duration_minutes: 30, mode: "visio", link: "", topic: "" });
  const [err, setErr] = useState<string | null>(null);
  const me = isAdvisor ? "conseiller" : "candidat";

  async function propose(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api(`/api/accompagnement/${c.id}/rendez-vous`, {
        method: "POST",
        body: JSON.stringify({ ...form, starts_at: new Date(form.starts_at).toISOString(), link: form.link || null, topic: form.topic || null }),
      });
      setForm({ ...form, starts_at: "", topic: "" }); setErr(null); reload();
    } catch (e2) { setErr((e2 as Error).message); }
  }
  async function patch(m: Meeting, body: object) {
    try { await api(`/api/accompagnement/rendez-vous/${m.id}`, { method: "PATCH", body: JSON.stringify(body) }); reload(); }
    catch (e) { setErr((e as Error).message); }
  }

  return (
    <div className="space-y-4">
      {err && <p className="text-sm text-danger">{err}</p>}
      {c.meetings.length === 0 && <p className="card p-6 text-center text-muted">{t("Aucun rendez-vous pour l'instant.")}</p>}
      <div className="space-y-3">
        {c.meetings.map((m) => (
          <div key={m.id} className="card p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold">{formatDateTime(m.starts_at)} · {m.duration_minutes} min · {cm.meeting_modes[m.mode] ?? m.mode}</p>
              <StatusChip status={m.status === "confirme" ? "en_cours" : m.status === "propose" ? "demande" : "termine"} label={cm.meeting_statuses[m.status]} />
            </div>
            {m.topic && <p className="mt-1 text-sm">{m.topic}</p>}
            {m.link && <a href={m.link} target="_blank" rel="noreferrer" className="mt-1 block truncate text-sm text-brand underline">{m.link}</a>}
            {m.summary && <p className="mt-2 whitespace-pre-wrap rounded-lg bg-paper p-3 text-sm"><strong>{t("Compte rendu :")}</strong> {m.summary}</p>}
            {c.status === "en_cours" && (
              <div className="mt-3 flex flex-wrap gap-2">
                {m.status === "propose" && m.proposed_by !== me && <button className="btn-primary px-3 py-1 text-xs" onClick={() => patch(m, { status: "confirme" })}>{t("Confirmer")}</button>}
                {m.status === "propose" && m.proposed_by === me && <span className="text-xs text-muted">{t("En attente de confirmation")}</span>}
                {(m.status === "propose" || m.status === "confirme") && <button className="btn-ghost px-3 py-1 text-xs" onClick={() => patch(m, { status: "annule" })}>{t("Annuler")}</button>}
                {isAdvisor && m.status === "confirme" && (
                  <button className="btn-ghost px-3 py-1 text-xs" onClick={() => {
                    const summary = prompt(t("Compte rendu du rendez-vous (visible par le candidat) :"));
                    if (summary !== null) patch(m, { status: "fait", summary });
                  }}>{t("Marquer comme fait")}</button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      {c.status === "en_cours" && (
        <form onSubmit={propose} className="card grid gap-3 p-4 sm:grid-cols-2">
          <h3 className="text-lg sm:col-span-2">{t("Proposer un rendez-vous")}</h3>
          <div><label className="label" htmlFor="rdv-date">{t("Date et heure")}</label>
            <input id="rdv-date" type="datetime-local" className="input" required value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-2">
            <div><label className="label" htmlFor="rdv-mode">{t("Mode")}</label>
              <select id="rdv-mode" className="input" value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
                {Object.entries(cm.meeting_modes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
            <div><label className="label" htmlFor="rdv-duree">{t("Durée")}</label>
              <select id="rdv-duree" className="input" value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: Number(e.target.value) })}>
                {[20, 30, 45, 60, 90].map((d) => <option key={d} value={d}>{d} min</option>)}
              </select></div>
          </div>
          <div><label className="label" htmlFor="rdv-sujet">{t("Sujet")}</label>
            <input id="rdv-sujet" className="input" placeholder={t("ex. Relecture de la lettre Eiffel")} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} /></div>
          <div><label className="label" htmlFor="rdv-lien">{t("Lien visio ou lieu")}</label>
            <input id="rdv-lien" className="input" placeholder={t("https://meet…")} value={form.link} onChange={(e) => setForm({ ...form, link: e.target.value })} /></div>
          <div className="sm:col-span-2"><button className="btn-primary">{t("Proposer")}</button>
            <span className="ml-3 text-xs text-muted">{t("L'autre personne reçoit une alerte et confirme.")}</span></div>
        </form>
      )}
    </div>
  );
}

// ---------- Dossier ----------
function Dossier({ c, meta, isAdvisor }: { c: CoachingDetail; meta: Meta | null; isAdvisor: boolean }) {
  const { t } = useT();
  const s = c.student;
  const name = (dict: Record<string, string> | undefined, k: string | null) => (k ? dict?.[k] ?? k : t("non renseigné"));
  return (
    <div className="space-y-5">
      {isAdvisor && s && (
        <div className="card space-y-3 p-5 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-lg">{s.full_name ?? s.email}</h3>
            <span className="chip">{t("Profil complet à")} {s.completeness} %</span>
          </div>
          <p className="text-muted">{s.email}</p>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            <div><dt className="text-muted">{t("Nationalité")}</dt><dd>{s.nationalities.map((n) => meta?.countries[n] ?? n).join(", ") || t("non renseignée")}</dd></div>
            <div><dt className="text-muted">{t("Niveau actuel → visé")}</dt><dd>{name(meta?.levels, s.current_level)} → {name(meta?.levels, s.target_level)}</dd></div>
            <div><dt className="text-muted">{t("Domaine")}</dt><dd>{name(meta?.domains, s.domain)}</dd></div>
            <div><dt className="text-muted">{t("Établissement")}</dt><dd>{s.institution ?? t("non renseigné")}</dd></div>
            <div><dt className="text-muted">{t("Moyenne")}</dt><dd>{s.grade_average != null ? `${s.grade_average}/20` : t("non renseignée")}</dd></div>
            <div><dt className="text-muted">{t("Pays souhaités")}</dt><dd>{s.wished_countries.map((n) => meta?.countries[n] ?? n).join(", ") || t("non renseignés")}</dd></div>
            <div><dt className="text-muted">{t("Langues")}</dt><dd>{Object.entries(s.languages).map(([k, v]) => `${k} ${v}`).join(", ") || t("non renseignées")}</dd></div>
            <div><dt className="text-muted">{t("Scores")}</dt><dd>{Object.entries(s.language_scores).map(([k, v]) => `${k} ${v}`).join(", ") || "aucun"}</dd></div>
          </dl>
          {s.project && <div><p className="text-muted">{t("Projet")}</p><p className="whitespace-pre-wrap">{s.project}</p></div>}
          {s.experiences && <div><p className="text-muted">{t("Expériences")}</p><p className="whitespace-pre-wrap">{s.experiences}</p></div>}
          {s.cv_text && (
            <details><summary className="cursor-pointer text-brand">{t("Voir le CV importé")}</summary>
              <pre className="mt-2 max-h-80 overflow-y-auto whitespace-pre-wrap rounded-lg bg-paper p-3 text-xs">{s.cv_text}</pre></details>
          )}
        </div>
      )}
      <div className="space-y-3">
        <h3 className="text-lg">{c.application_ids.length ? t("Candidatures concernées") : t("Candidatures du suivi")}</h3>
        {c.applications.length === 0 && (
          <p className="card p-6 text-center text-sm text-muted">
            Aucune candidature. {isAdvisor ? t("Le candidat n'a pas encore ajouté de bourse à son suivi.") : <>{t("Ajoutez des bourses depuis")} <Link href="/mes-bourses" className="text-brand underline">{t("Mes bourses")}</Link>.</>}
          </p>
        )}
        {c.applications.map((a) => {
          const done = Object.values(a.checklist).filter(Boolean).length;
          const total = Object.keys(a.checklist).length;
          return (
            <div key={a.id} className="card p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <Link href={`/bourses/${a.scholarship.id}`} className="font-semibold hover:text-brand">{a.scholarship.title}</Link>
                <span className="chip">{meta?.statuses[a.status] ?? a.status}</span>
              </div>
              <div className="mt-2"><DeadlineBadge deadline={a.scholarship.deadline} s={a.scholarship} /></div>
              <p className="mt-2 text-xs text-muted">{done}/{total} {t("pièces prêtes :")} {Object.entries(a.checklist).map(([k, v]) => `${v ? "✓" : "○"} ${meta?.requirements[k] ?? k}`).join(" · ")}</p>
              {a.notes && <p className="mt-1 text-xs text-muted">{t("Notes :")} {a.notes}</p>}
              {a.letter && (
                <details className="mt-2 text-sm"><summary className="cursor-pointer text-brand">{t("Lettre de motivation ({n} mots)", { n: a.letter.split(/\s+/).length })}</summary>
                  <p className="mt-2 whitespace-pre-wrap rounded-lg bg-paper p-3">{a.letter}</p></details>
              )}
              {!isAdvisor && <Link href={`/lettre/${a.scholarship.id}`} className="mt-2 inline-block text-xs text-brand hover:underline">{a.letter ? t("Revoir la lettre") : t("Écrire la lettre")}</Link>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FinishBox({ id, reload }: { id: number; reload: () => void }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  if (!open) return <button className="btn-ghost" onClick={() => setOpen(true)}>{t("Terminer l'accompagnement")}</button>;
  return (
    <div className="card space-y-2 p-4">
      <label className="label" htmlFor="fin-note">{t("Mot de fin (facultatif, envoyé au candidat)")}</label>
      <textarea id="fin-note" className="input" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="flex gap-2">
        <button className="btn-primary" onClick={async () => { await api(`/api/accompagnement/${id}/terminer`, { method: "POST", body: JSON.stringify({ note }) }); reload(); }}>{t("Terminer")}</button>
        <button className="btn-ghost" onClick={() => setOpen(false)}>{t("Annuler")}</button>
      </div>
    </div>
  );
}
