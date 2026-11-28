"use client";
import { useEffect, useState } from "react";
import { API_URL, CREDENTIALS, Scholarship, api, apiHeaders } from "@/lib/api";

type Item = Scholarship & { review?: string; source_name?: string | null; source_page?: string | null };

/** Fiches trouvées par la collecte automatique : rien n'est publié avant votre relecture. */
export default function AdminReview() {
  const [items, setItems] = useState<Item[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => api<Item[]>("/api/admin/relecture").then(setItems).catch((e) => setMsg((e as Error).message));
  useEffect(() => { load(); }, []);

  async function decide(id: number, decision: "publie" | "rejete") {
    try {
      await api(`/api/admin/relecture/${id}`, { method: "POST", body: JSON.stringify({ decision }) });
      setItems((xs) => xs.filter((x) => x.id !== id));
    } catch (e) { setMsg((e as Error).message); }
  }

  async function backup() {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch(`${API_URL}/api/admin/sauvegarde`, { headers: apiHeaders(), credentials: CREDENTIALS });
      if (!res.ok) throw new Error(`Erreur ${res.status}`);
      const blob = await res.blob();
      const name = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") || "")?.[1] || "scholarfit-sauvegarde.json.gz";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
      setMsg("Sauvegarde téléchargée. Rangez-la hors de Railway (Google Drive, clé USB).");
    } catch (e) { setMsg((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl">Fiches à relire <span className="text-muted">({items.length})</span></h2>
        <button className="btn-ghost" onClick={backup} disabled={busy}>{busy ? "Préparation…" : "Télécharger une sauvegarde de la base"}</button>
      </div>
      <p className="text-sm text-muted">
        Trouvées par la collecte automatique (sites d&apos;annonces, recherche IA). Ouvrez le lien officiel, vérifiez la date et les conditions, puis publiez ou rejetez. Une fiche rejetée ne revient pas.
      </p>
      {msg && <p className="text-sm">{msg}</p>}
      {items.length === 0 && <p className="card p-4 text-sm text-muted">Aucune fiche en attente.</p>}
      <ul className="space-y-2">
        {items.map((s) => (
          <li key={s.id} className="card flex flex-wrap items-start justify-between gap-3 p-4">
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{s.title}</p>
              <p className="text-sm text-muted">
                {s.organization} · {s.deadline ? `date limite ${s.deadline}` : "sans date"} · {s.source_name || "saisie"}
              </p>
              <p className="mt-1 text-sm">{s.summary}</p>
              <p className="mt-1 flex flex-wrap gap-3 text-sm">
                <a className="text-brand underline" href={s.official_url} target="_blank" rel="noreferrer">Lien officiel</a>
                {s.source_page && <a className="text-muted underline" href={s.source_page} target="_blank" rel="noreferrer">Annonce d&apos;origine</a>}
              </p>
            </div>
            <div className="flex gap-2">
              <button className="btn-primary" onClick={() => decide(s.id, "publie")}>Publier</button>
              <button className="btn-ghost" onClick={() => decide(s.id, "rejete")}>Rejeter</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
