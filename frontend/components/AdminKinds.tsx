"use client";
import { useEffect, useState } from "react";
import { api, clearMetaCache } from "@/lib/api";
import Icon from "./Icon";

type KindRow = { kind: string; label: string; enabled: boolean; total: number; open: number };

const ICONS: Record<string, string> = {
  bourse: "medal", stage: "people", conference: "chat", formation: "book", concours: "star", echange: "globe", fellowship: "cap", cours_en_ligne: "sparkle",
};

/** Types d'opportunités affichés sur le site. Un type désactivé reste en base mais disparaît des
 *  onglets, de la recherche, des fiches, du matching et des alertes, et n'est plus collecté (aucun coût d'IA). */
export default function AdminKinds() {
  const [rows, setRows] = useState<KindRow[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => { api<KindRow[]>("/api/admin/types").then(setRows).catch((e) => setError(e.message)); }, []);

  async function toggle(row: KindRow) {
    if (!rows) return;
    const next = rows.map((r) => (r.kind === row.kind ? { ...r, enabled: !r.enabled } : r));
    if (!next.some((r) => r.enabled)) {
      setError("Gardez au moins un type affiché.");
      return;
    }
    setBusy(row.kind);
    setError(null);
    setSaved(false);
    try {
      await api("/api/admin/types", { method: "PUT", body: JSON.stringify({ kinds_enabled: next.filter((r) => r.enabled).map((r) => r.kind) }) });
      setRows(next);
      clearMetaCache();
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const shown = rows?.filter((r) => r.enabled).length ?? 0;
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-xl">Types d&apos;opportunités</h2>
          <p className="text-sm text-muted">Choisissez ce qui est affiché sur le site. Un type désactivé reste en base, mais n&apos;apparaît plus nulle part et n&apos;est plus collecté (aucun coût d&apos;IA).</p>
        </div>
        {rows && <p className="text-sm text-muted">{shown} type{shown > 1 ? "s" : ""} affiché{shown > 1 ? "s" : ""} sur {rows.length}</p>}
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
      {saved && <p className="text-sm text-ok">Enregistré : le site est à jour (les visiteurs le voient au prochain chargement de page).</p>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {rows?.map((r) => (
          <div key={r.kind} className={`card flex items-center gap-3 p-4 transition ${r.enabled ? "border-brand/50" : "opacity-70"}`}>
            <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${r.enabled ? "bg-brand-soft text-brand" : "bg-surface text-muted"}`}>
              <Icon name={ICONS[r.kind] ?? "star"} className="h-5 w-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-semibold">{r.label}</span>
              <span className="block text-xs text-muted">{r.open} ouverte{r.open > 1 ? "s" : ""} · {r.total} en base</span>
            </span>
            <button type="button" role="switch" aria-checked={r.enabled} disabled={busy !== null} onClick={() => toggle(r)}
              aria-label={`${r.enabled ? "Masquer" : "Afficher"} : ${r.label}`}
              className={`relative h-6 w-11 shrink-0 rounded-full transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-60 ${r.enabled ? "bg-mint" : "bg-line"}`}>
              <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${r.enabled ? "left-[22px]" : "left-0.5"}`} />
            </button>
          </div>
        ))}
        {!rows && !error && <p className="text-sm text-muted">Chargement…</p>}
      </div>
    </section>
  );
}
