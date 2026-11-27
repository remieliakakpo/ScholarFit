"use client";
import { useEffect, useState } from "react";
import AdminCoaching from "@/components/AdminCoaching";
import AdminPayments from "@/components/AdminPayments";
import AdminReview from "@/components/AdminReview";
import AdminCredits from "@/components/docs/AdminCredits";
import RequireAuth from "@/components/RequireAuth";
import { Meta, Scholarship, api, getMeta } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

type Source = { id: number; name: string; url: string; method: string; connector: string; robots_allowed: boolean | null; last_run_at: string | null; last_status: string | null };

const EMPTY = { title: "", organization: "", official_url: "", summary: "", levels: [] as string[], study_countries: "", eligible_nationalities: "ALL", domains: ["tous"], amount: "", currency: "EUR", amount_period: "mois", full_funding: false, deadline: "", requirements: "cv,lettre" };

function Admin() {
  const { me } = useAuth();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [toVerify, setToVerify] = useState<Scholarship[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [url, setUrl] = useState("");
  const [log, setLog] = useState<string | null>(null);

  const refresh = () => {
    api<Source[]>("/api/admin/sources").then(setSources).catch((e) => setLog(e.message));
    api<{ items: Scholarship[] }>("/api/scholarships?per_page=100&sort=recent").then((d) => setToVerify(d.items.filter((s) => s.status === "a_verifier")));
  };
  useEffect(() => { getMeta().then(setMeta); refresh(); }, []);

  if (me && !me.is_admin) return <p className="text-danger">Réservé aux administrateurs.</p>;

  async function run(name: string) {
    setLog(`Collecte « ${name} » en cours…`);
    try {
      const r = await api<{ status: string }>(`/api/admin/sources/${encodeURIComponent(name)}/run`, { method: "POST" });
      setLog(`${name} : ${r.status}`);
      refresh();
    } catch (e) { setLog((e as Error).message); }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    const body = {
      ...form,
      study_countries: form.study_countries.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean),
      eligible_nationalities: form.eligible_nationalities.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean),
      requirements: form.requirements.split(",").map((x) => x.trim()).filter(Boolean),
      amount: form.amount ? Number(form.amount) : null,
      deadline: form.deadline || null,
    };
    try {
      const s = await api<Scholarship>("/api/admin/scholarships", { method: "POST", body: JSON.stringify(body) });
      setLog(`Bourse ajoutée : ${s.title}`);
      setForm(EMPTY);
    } catch (err) { setLog((err as Error).message); }
  }

  async function extract(save: boolean) {
    setLog("Extraction…");
    try {
      const r = await api<Record<string, unknown>>("/api/admin/extract", { method: "POST", body: JSON.stringify({ url, save }) });
      setLog(JSON.stringify(r, null, 2));
      if (save) refresh();
    } catch (e) { setLog((e as Error).message); }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-3xl">Administration</h1>
      {log && <pre className="card overflow-x-auto whitespace-pre-wrap p-4 text-xs">{log}</pre>}

      <AdminReview />
      <AdminCoaching meta={meta} />
      <AdminPayments />
      <AdminCredits />

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl">Sources de collecte</h2>
          <button className="btn-ghost" onClick={async () => setLog(JSON.stringify(await api("/api/admin/maintenance", { method: "POST" })))}>Lancer la maintenance (expirations + alertes)</button>
        </div>
        <p className="text-sm text-muted">Les sources se configurent dans <code>backend/app/data/sources.json</code>. robots.txt est lu avant chaque collecte.</p>
        <div className="card divide-y divide-line">
          {sources.map((s) => (
            <div key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
              <div className="min-w-0">
                <p className="font-semibold">{s.name} <span className="chip ml-1">{s.connector}</span></p>
                <p className="truncate text-xs text-muted">{s.url}</p>
                <p className="text-xs text-muted">{s.last_run_at ? `Dernière collecte : ${new Date(s.last_run_at).toLocaleString("fr-FR")} · ${s.last_status}` : "Jamais collectée"}{s.robots_allowed === false ? " · robots.txt interdit" : ""}</p>
              </div>
              <button className="btn-ghost" onClick={() => run(s.name)}>Collecter</button>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl">Tester l&apos;extraction d&apos;une page</h2>
        <div className="flex flex-wrap gap-2">
          <input className="input flex-1" placeholder="https://… page officielle d'une bourse" value={url} onChange={(e) => setUrl(e.target.value)} />
          <button className="btn-ghost" disabled={!url} onClick={() => extract(false)}>Extraire</button>
          <button className="btn-primary" disabled={!url} onClick={() => extract(true)}>Extraire et ajouter</button>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl">Bourses à vérifier ({toVerify.length})</h2>
        <div className="card divide-y divide-line">
          {toVerify.slice(0, 15).map((s) => (
            <div key={s.id} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
              <a href={s.official_url} target="_blank" rel="noopener noreferrer" className="hover:text-brand">{s.title} ↗</a>
              <button className="btn-ghost px-2 py-1 text-xs" onClick={async () => { await api(`/api/admin/scholarships/${s.id}/verify`, { method: "POST" }); refresh(); }}>Marquer vérifiée</button>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl">Ajouter une bourse à la main</h2>
        <form onSubmit={create} className="card grid gap-3 p-5 sm:grid-cols-2">
          <input required className="input" placeholder="Titre" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <input required className="input" placeholder="Organisme" value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} />
          <input required type="url" className="input sm:col-span-2" placeholder="Lien officiel" value={form.official_url} onChange={(e) => setForm({ ...form, official_url: e.target.value })} />
          <textarea className="input sm:col-span-2" rows={2} placeholder="Résumé (2 phrases, avec vos mots)" value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} />
          <div className="flex flex-wrap gap-3 text-sm sm:col-span-2">
            {meta && Object.entries(meta.levels).map(([k, v]) => (
              <label key={k} className="flex items-center gap-1"><input type="checkbox" checked={form.levels.includes(k)} onChange={(e) => setForm({ ...form, levels: e.target.checked ? [...form.levels, k] : form.levels.filter((x) => x !== k) })} />{v}</label>
            ))}
          </div>
          <select multiple className="input h-28" value={form.domains} onChange={(e) => setForm({ ...form, domains: Array.from(e.target.selectedOptions).map((o) => o.value) })}>
            {meta && Object.entries(meta.domains).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <div className="space-y-3">
            <input className="input" placeholder="Pays d'étude (codes : FR,CA)" value={form.study_countries} onChange={(e) => setForm({ ...form, study_countries: e.target.value })} />
            <input className="input" placeholder="Nationalités (ALL, AFRICA, SN,CI…)" value={form.eligible_nationalities} onChange={(e) => setForm({ ...form, eligible_nationalities: e.target.value })} />
          </div>
          <div className="flex gap-2">
            <input className="input" type="number" placeholder="Montant" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
            <input className="input w-24" placeholder="EUR" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} />
            <select className="input w-28" value={form.amount_period} onChange={(e) => setForm({ ...form, amount_period: e.target.value })}><option value="mois">/ mois</option><option value="an">/ an</option><option value="total">total</option></select>
          </div>
          <input type="date" className="input" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} />
          <input className="input" placeholder="Pièces (cv,lettre,recommandation,releves,test_langue)" value={form.requirements} onChange={(e) => setForm({ ...form, requirements: e.target.value })} />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.full_funding} onChange={(e) => setForm({ ...form, full_funding: e.target.checked })} />Financement complet</label>
          <button className="btn-primary sm:col-span-2">Ajouter la bourse</button>
        </form>
      </section>
    </div>
  );
}

export default function Page() {
  return <RequireAuth><Admin /></RequireAuth>;
}
