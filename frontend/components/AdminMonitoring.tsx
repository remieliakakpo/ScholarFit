"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

// ---------------------------------------------------------------- signalements
type Report = {
  id: number; reason: string; reason_label: string; comment: string | null; status: string; created_at: string;
  resolution_note: string | null; reporter: string | null; open_for_scholarship: number;
  scholarship: { id: number; title: string; official_url: string; link_status: string } | null;
};

const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "");

/** Fiches signalées par les membres : à corriger (bouton Modifier) ou à rejeter. */
export function AdminReports() {
  const [status, setStatus] = useState("ouvert");
  const [items, setItems] = useState<Report[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    api<Report[]>(`/api/admin/signalements?status=${status}`).then(setItems).catch((e) => setError(e.message));
  }, [status]);
  useEffect(load, [load]);

  async function resolve(r: Report, next: "corrige" | "rejete") {
    const note = next === "rejete" ? prompt("Pourquoi rejeter ce signalement ? (facultatif)") ?? "" : "";
    await api(`/api/admin/signalements/${r.id}`, { method: "PATCH", body: JSON.stringify({ status: next, note, all_for_scholarship: true }) });
    load();
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl">Fiches signalées {items && status === "ouvert" ? `(${items.length})` : ""}</h2>
        <select className="input w-auto py-1.5 text-sm" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Statut des signalements">
          <option value="ouvert">À traiter</option><option value="corrige">Corrigés</option><option value="rejete">Rejetés</option><option value="tous">Tous</option>
        </select>
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
      {items?.length === 0 && <p className="card p-4 text-sm text-muted">Aucun signalement.</p>}
      <div className="space-y-2">
        {items?.map((r) => (
          <div key={r.id} className="card flex flex-wrap items-start justify-between gap-3 p-4 text-sm">
            <div className="min-w-0 flex-1 space-y-1">
              <p className="font-semibold">
                {r.scholarship ? <Link href={`/bourses/${r.scholarship.id}`} className="hover:text-brand hover:underline">{r.scholarship.title}</Link> : "Fiche supprimée"}
                {r.open_for_scholarship > 1 && r.status === "ouvert" && <span className="ml-2 rounded-full bg-gold/20 px-2 text-xs text-gold-dark">{r.open_for_scholarship} signalements</span>}
              </p>
              <p><span className="font-medium text-warm">{r.reason_label}</span>{r.comment ? ` : « ${r.comment} »` : ""}</p>
              <p className="text-xs text-muted">{fmt(r.created_at)} · {r.reporter ?? "compte supprimé"}{r.scholarship ? ` · lien ${r.scholarship.link_status}` : ""}</p>
              {r.scholarship && <a href={r.scholarship.official_url} target="_blank" rel="noopener noreferrer" className="block truncate text-xs text-brand underline">{r.scholarship.official_url}</a>}
              {r.resolution_note && <p className="text-xs text-muted">Note : {r.resolution_note}</p>}
            </div>
            {r.status === "ouvert" && (
              <div className="flex gap-2">
                <button className="btn-primary px-3 py-1.5 text-xs" onClick={() => resolve(r, "corrige")}>Corrigé</button>
                <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => resolve(r, "rejete")}>Rejeter</button>
              </div>
            )}
          </div>
        ))}
      </div>
      <p className="text-xs text-muted">« Corrigé » prévient les personnes qui ont signalé la fiche. Corrigez d&apos;abord la fiche elle-même (lien, date) dans la liste des bourses.</p>
    </section>
  );
}

// ---------------------------------------------------------------- journal d'audit
type AuditItem = { id: number; created_at: string; actor: string | null; action: string; target_type: string | null; target_id: string | null; details: Record<string, unknown>; ip: string | null };

export function AdminAudit() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [data, setData] = useState<{ total: number; items: AuditItem[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const perPage = 25;

  useEffect(() => {
    const p = new URLSearchParams({ page: String(page), per_page: String(perPage) });
    if (action) p.set("action", action);
    if (actor) p.set("actor", actor);
    const id = setTimeout(() => api<{ total: number; items: AuditItem[] }>(`/api/admin/audit?${p}`).then(setData).catch((e) => setError(e.message)), 300);
    return () => clearTimeout(id);
  }, [page, action, actor]);

  const pages = data ? Math.max(1, Math.ceil(data.total / perPage)) : 1;
  return (
    <section className="space-y-3">
      <h2 className="text-xl">Journal d&apos;audit</h2>
      <p className="text-sm text-muted">Toute modification faite dans l&apos;administration, les connexions des administrateurs et les changements de mot de passe ou suppressions de compte.</p>
      <div className="flex flex-wrap gap-2">
        <input className="input w-auto py-1.5 text-sm" placeholder="Action (ex. credit-orders)" value={action} onChange={(e) => { setPage(1); setAction(e.target.value); }} aria-label="Filtrer par action" />
        <input className="input w-auto py-1.5 text-sm" placeholder="Auteur (e-mail)" value={actor} onChange={(e) => { setPage(1); setActor(e.target.value); }} aria-label="Filtrer par auteur" />
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="text-xs uppercase text-muted"><tr className="border-b border-line">
            <th className="p-3">Date</th><th className="p-3">Auteur</th><th className="p-3">Action</th><th className="p-3">Cible</th><th className="p-3">Détails</th><th className="p-3">Adresse IP</th>
          </tr></thead>
          <tbody>
            {data?.items.map((a) => (
              <tr key={a.id} className="border-b border-line/60 align-top">
                <td className="whitespace-nowrap p-3 text-xs">{fmt(a.created_at)}</td>
                <td className="p-3 text-xs">{a.actor ?? "—"}</td>
                <td className="p-3 font-mono text-xs">{a.action}</td>
                <td className="p-3 text-xs">{a.target_type ?? ""}{a.target_id ? ` #${a.target_id}` : ""}</td>
                <td className="max-w-[280px] p-3 text-xs text-muted">{Object.entries(a.details).map(([k, v]) => `${k} : ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ")}</td>
                <td className="p-3 font-mono text-xs text-muted">{a.ip ?? ""}</td>
              </tr>
            ))}
            {data && data.items.length === 0 && <tr><td colSpan={6} className="p-4 text-center text-muted">Aucune entrée.</td></tr>}
          </tbody>
        </table>
      </div>
      {data && pages > 1 && (
        <div className="flex items-center gap-3 text-sm">
          <button className="btn-ghost px-3 py-1.5 text-xs" disabled={page <= 1} onClick={() => setPage(page - 1)}>Précédent</button>
          <span className="text-muted">Page {page} / {pages} · {data.total} entrées</span>
          <button className="btn-ghost px-3 py-1.5 text-xs" disabled={page >= pages} onClick={() => setPage(page + 1)}>Suivant</button>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- coût de l'IA
type Costs = {
  ai_enabled: boolean; model: string; daily_budget: number | null; today: number; total: number; average_per_day: number;
  days: { day: string; cost: number; calls: number; input_tokens: number; output_tokens: number; web_searches: number }[];
  by_purpose: { purpose: string; cost: number; calls: number }[];
};

const usd = (n: number) => `${n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 4 })} $`;
const PURPOSES: Record<string, string> = { cv: "CV", letter: "Lettres", chat: "Assistant de recherche", fit: "Compatibilité", discovery: "Découverte de bourses", recherche_web: "Recherche web (découverte)", extract: "Extraction de pages", translate: "Traduction" };

export function AdminAICosts() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Costs | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<Costs>(`/api/admin/couts-ia?days=${days}`).then(setData).catch((e) => setError(e.message)); }, [days]);

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl">Coût de l&apos;IA</h2>
        <select className="input w-auto py-1.5 text-sm" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Période">
          <option value={7}>7 jours</option><option value={30}>30 jours</option><option value={90}>90 jours</option>
        </select>
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
      {data && (
        <>
          <p className="text-sm text-muted">
            {data.ai_enabled ? `Modèle ${data.model}.` : "IA désactivée (pas de clé ANTHROPIC_API_KEY) : aucun coût."}{" "}
            Aujourd&apos;hui : <strong className="text-ink">{usd(data.today)}</strong>{data.daily_budget ? ` sur un plafond de ${usd(data.daily_budget)} par jour` : " (pas de plafond : AI_DAILY_BUDGET_USD)"}.
            {" "}Sur la période : <strong className="text-ink">{usd(data.total)}</strong>, soit {usd(data.average_per_day)} par jour en moyenne. Montants estimés d&apos;après les tarifs réglés dans la configuration.
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="card overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-muted"><tr className="border-b border-line"><th className="p-3">Jour</th><th className="p-3 text-right">Appels</th><th className="p-3 text-right">Jetons (entrée / sortie)</th><th className="p-3 text-right">Coût</th></tr></thead>
                <tbody>
                  {[...data.days].reverse().map((d) => (
                    <tr key={d.day} className="border-b border-line/60">
                      <td className="p-3">{new Date(d.day + "T00:00:00").toLocaleDateString("fr-FR")}</td>
                      <td className="p-3 text-right tabular-nums">{d.calls}</td>
                      <td className="p-3 text-right tabular-nums text-muted">{d.input_tokens.toLocaleString("fr-FR")} / {d.output_tokens.toLocaleString("fr-FR")}</td>
                      <td className="p-3 text-right font-medium tabular-nums">{usd(d.cost)}</td>
                    </tr>
                  ))}
                  {data.days.length === 0 && <tr><td colSpan={4} className="p-4 text-center text-muted">Aucun appel à l&apos;IA sur la période.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="card overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-muted"><tr className="border-b border-line"><th className="p-3">Fonction</th><th className="p-3 text-right">Appels</th><th className="p-3 text-right">Coût</th></tr></thead>
                <tbody>
                  {data.by_purpose.map((p) => (
                    <tr key={p.purpose} className="border-b border-line/60">
                      <td className="p-3">{PURPOSES[p.purpose] ?? p.purpose}</td>
                      <td className="p-3 text-right tabular-nums">{p.calls}</td>
                      <td className="p-3 text-right font-medium tabular-nums">{usd(p.cost)}</td>
                    </tr>
                  ))}
                  {data.by_purpose.length === 0 && <tr><td colSpan={3} className="p-4 text-center text-muted">—</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
