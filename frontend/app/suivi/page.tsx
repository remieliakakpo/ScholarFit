"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import { DeadlineBadge } from "@/components/ScholarshipCard";
import { API_URL, Application, Meta, api, getMeta } from "@/lib/api";
import Icon from "@/components/Icon";
import { warmOffline } from "@/lib/pwa";
import { useT } from "@/components/LangProvider";

const COLUMNS: { key: string; label: string; statuses: string[]; dot: string }[] = [
  { key: "a_preparer", label: "À préparer", statuses: ["a_preparer"], dot: "bg-muted" },
  { key: "en_cours", label: "En cours", statuses: ["en_cours"], dot: "bg-gold" },
  { key: "envoyee", label: "Envoyée", statuses: ["envoyee"], dot: "bg-brand" },
  { key: "resultat", label: "Résultat", statuses: ["acceptee", "refusee"], dot: "bg-ok" },
];

type Check = { ok: boolean; items: { label: string; ok: boolean; detail: string | null }[] };

function Board() {
  const { t } = useT();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [apps, setApps] = useState<Application[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [check, setCheck] = useState<Check | null>(null);
  const [dragId, setDragId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMeta().then(setMeta);
    api<Application[]>("/api/applications")
      .then((list) => {
        setApps(list);
        warmOffline(list.map((a) => `/bourses/${a.scholarship.id}`)); // fiches lisibles sans réseau
      })
      .catch((e) => setError(e.message));
  }, []);

  async function patch(id: number, body: object) {
    const out = await api<Application>(`/api/applications/${id}`, { method: "PATCH", body: JSON.stringify(body) });
    setApps((a) => a?.map((x) => (x.id === id ? out : x)) ?? null);
    if (open === id) setCheck(null);
  }

  async function remove(id: number) {
    if (!confirm(t("Retirer cette bourse de votre suivi ?"))) return;
    await api(`/api/applications/${id}`, { method: "DELETE" });
    setApps((a) => a?.filter((x) => x.id !== id) ?? null);
  }

  if (error) return <p className="text-danger">{error}</p>;
  if (!apps) return <p className="text-muted">{t("Chargement…")}</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[1.65rem] sm:text-3xl">{t("Suivi de mes candidatures")}</h1>
        <p className="mt-1 text-muted">{t("Glissez une carte d'une colonne à l'autre. Vous recevez un rappel à J-30, J-7 et J-1 pour chaque candidature pas encore envoyée.")}</p>
        {apps.length > 0 && (
          <a href={`${API_URL}/api/calendrier.ics`} download className="btn-ghost mt-3 inline-flex gap-2 text-sm">
            <Icon name="calendar" className="h-4 w-4 text-brand" />{t("Mettre mes dates limites dans mon agenda")}
          </a>
        )}
      </div>
      {apps.length === 0 && (
        <div className="card p-8 text-center text-muted">
          Aucune candidature suivie. Ajoutez des bourses depuis <Link href="/mes-bourses" className="text-brand underline">{t("Mes bourses")}</Link>.
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {COLUMNS.map((col) => (
          <div key={col.key} className="min-h-[200px] rounded-2xl bg-surface p-3"
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => { if (dragId) patch(dragId, { status: col.key === "resultat" ? "acceptee" : col.key }); setDragId(null); }}>
            <h2 className="mb-3 flex items-center gap-2 px-1 font-sans text-xs font-semibold uppercase tracking-wider text-muted"><span className={`h-2 w-2 rounded-full ${col.dot}`} />{t(col.label)}<span className="ml-auto rounded-full bg-card px-2 py-0.5 text-[11px] ring-1 ring-line">{apps.filter((a) => col.statuses.includes(a.status)).length}</span></h2>
            <div className="space-y-3">
              {apps.filter((a) => col.statuses.includes(a.status)).map((a) => {
                const done = Object.values(a.checklist).filter(Boolean).length;
                const total = Object.keys(a.checklist).length;
                return (
                  <div key={a.id} draggable onDragStart={() => setDragId(a.id)} className="card cursor-grab p-4 active:cursor-grabbing">
                    <Link href={`/bourses/${a.scholarship.id}`} className="font-semibold leading-snug hover:text-brand">{a.scholarship.title}</Link>
                    <div className="mt-2"><DeadlineBadge deadline={a.scholarship.deadline} s={a.scholarship} /></div>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-paper"><div className="h-full bg-brand" style={{ width: `${total ? (100 * done) / total : 0}%` }} /></div>
                    <p className="mt-1 text-xs text-muted">{done}/{total} {t("pièces prêtes")}</p>
                    {col.key === "resultat" && (
                      <select className="input mt-2" value={a.status} onChange={(e) => patch(a.id, { status: e.target.value })}>
                        <option value="acceptee">{t("Acceptée 🎉")}</option>
                        <option value="refusee">{t("Refusée")}</option>
                      </select>
                    )}
                    <select className="input mt-2 md:hidden" value={a.status} onChange={(e) => patch(a.id, { status: e.target.value })} aria-label={t("Changer de colonne")}>
                      {meta && Object.entries(meta.statuses).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                    <button className="mt-2 text-xs text-brand hover:underline" onClick={() => { setOpen(open === a.id ? null : a.id); setCheck(null); }}>
                      {open === a.id ? t("Fermer") : t("Checklist et notes")}
                    </button>
                    {open === a.id && (
                      <div className="mt-3 space-y-2 border-t border-line pt-3">
                        {Object.entries(a.checklist).map(([k, v]) => (
                          <label key={k} className="flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={v} onChange={(e) => patch(a.id, { checklist: { [k]: e.target.checked } })} />
                            {meta?.requirements[k] ?? k}
                          </label>
                        ))}
                        <textarea className="input" rows={2} placeholder={t("Notes")} defaultValue={a.notes ?? ""} onBlur={(e) => e.target.value !== (a.notes ?? "") && patch(a.id, { notes: e.target.value })} />
                        <div className="flex flex-wrap gap-2">
                          <Link href={`/lettre/${a.scholarship.id}`} className="btn-ghost px-2 py-1 text-xs">{a.letter ? t("Revoir la lettre") : t("Écrire la lettre")}</Link>
                          <button className="btn-ghost px-2 py-1 text-xs" onClick={async () => setCheck(await api<Check>(`/api/applications/${a.id}/check`))}>{t("Vérifier le dossier")}</button>
                          <button className="px-2 py-1 text-xs text-danger hover:underline" onClick={() => remove(a.id)}>{t("Retirer")}</button>
                        </div>
                        {check && (
                          <ul className="space-y-1 text-xs">
                            {check.items.map((i) => <li key={i.label} className={i.ok ? "text-brand" : "text-warm"}>{i.ok ? "✓" : "!"} {i.label}{i.detail ? ` : ${i.detail}` : ""}</li>)}
                            {check.ok && <li className="font-semibold text-brand">{t("Dossier complet, prêt à envoyer.")}</li>}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return <RequireAuth><Board /></RequireAuth>;
}
