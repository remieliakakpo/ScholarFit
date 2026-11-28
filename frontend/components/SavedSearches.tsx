"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Icon from "./Icon";
import { useT } from "./LangProvider";

export type SavedSearch = { id: number; name: string; filters: Record<string, string | boolean>; alerts_enabled: boolean };

// Paramètres du catalogue qu'une recherche retient (les autres, comme le tri, restent à l'écran)
const SAVED_KEYS = ["q", "kind", "level", "region", "country", "country_exact", "domain", "nationality", "full_funding", "include_expired"];

export function searchHref(filters: SavedSearch["filters"]) {
  const p = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => p.set(k, String(v)));
  return `/bourses?${p.toString()}`;
}

/** Bouton du catalogue : enregistre les filtres affichés et prévient des nouvelles offres. */
export function SaveSearchButton({ filters, suggestedName }: { filters: Record<string, string>; suggestedName: string }) {
  const { t } = useT();
  const { me } = useAuth();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(suggestedName);
  const [state, setState] = useState<"idle" | "busy" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setName(suggestedName); setState("idle"); }, [suggestedName]);

  const clean: Record<string, string> = {};
  SAVED_KEYS.forEach((k) => {
    const v = filters[k];
    if (v && !(k === "kind" && v === "tout")) clean[k] = v;
  });
  if (Object.keys(clean).filter((k) => k !== "kind").length === 0) return null;

  if (!me) {
    return (
      <Link href="/connexion?mode=inscription" className="flex w-full items-center justify-center gap-2 rounded-full border border-brand/40 py-2 text-xs font-semibold text-brand hover:bg-brand-soft">
        <Icon name="bell" className="h-3.5 w-3.5" />{t("Créer un compte pour être alerté")}
      </Link>
    );
  }
  if (state === "saved") {
    return <p className="rounded-xl bg-brand-soft p-3 text-xs text-brand">{t("Recherche enregistrée : vous recevrez une alerte pour chaque nouvelle offre.")} <Link href="/mes-bourses" className="font-semibold underline">{t("Mes recherches")}</Link></p>;
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setState("busy");
    setError(null);
    try {
      await api("/api/recherches", { method: "POST", body: JSON.stringify({ name, filters: clean, alerts_enabled: true }) });
      setState("saved");
    } catch (err) {
      setError((err as Error).message);
      setState("idle");
    }
  }
  return open ? (
    <form onSubmit={save} className="space-y-2 rounded-xl border border-line p-3">
      <label className="label" htmlFor="search-name">{t("Nom de la recherche")}</label>
      <input id="search-name" className="input" value={name} maxLength={120} required minLength={2} onChange={(e) => setName(e.target.value)} />
      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="flex gap-2">
        <button className="btn-primary flex-1 py-2 text-xs" disabled={state === "busy"}>{state === "busy" ? "…" : t("Enregistrer et m'alerter")}</button>
        <button type="button" className="btn-ghost py-2 text-xs" onClick={() => setOpen(false)}>{t("Annuler")}</button>
      </div>
    </form>
  ) : (
    <button type="button" onClick={() => setOpen(true)} className="flex w-full items-center justify-center gap-2 rounded-full border border-brand/40 py-2 text-xs font-semibold text-brand hover:bg-brand-soft">
      <Icon name="bell" className="h-3.5 w-3.5" />{t("M'alerter des nouvelles offres")}
    </button>
  );
}

/** Liste des recherches enregistrées (espace « Mes bourses »). */
export function SavedSearchList() {
  const { t } = useT();
  const [items, setItems] = useState<SavedSearch[] | null>(null);
  useEffect(() => { api<SavedSearch[]>("/api/recherches").then(setItems).catch(() => setItems([])); }, []);

  async function toggle(s: SavedSearch) {
    const out = await api<SavedSearch>(`/api/recherches/${s.id}`, { method: "PATCH", body: JSON.stringify({ alerts_enabled: !s.alerts_enabled }) });
    setItems((items ?? []).map((x) => (x.id === s.id ? out : x)));
  }
  async function remove(s: SavedSearch) {
    if (!confirm(t("Supprimer la recherche « {n} » ?", { n: s.name }))) return;
    await api(`/api/recherches/${s.id}`, { method: "DELETE" });
    setItems((items ?? []).filter((x) => x.id !== s.id));
  }

  return (
    <div className="card p-5">
      <p className="flex items-center gap-2 text-sm font-semibold"><Icon name="bell" className="h-4 w-4 text-brand" />{t("Mes recherches")}</p>
      {items === null ? (
        <p className="mt-2 text-sm text-muted">…</p>
      ) : items.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("Dans Explorer, choisissez vos filtres puis « M'alerter des nouvelles offres ».")}</p>
      ) : (
        <ul className="mt-3 space-y-3 text-sm">
          {items.map((s) => (
            <li key={s.id} className="space-y-1">
              <Link href={searchHref(s.filters)} className="font-medium hover:text-brand hover:underline">{s.name}</Link>
              <div className="flex items-center gap-3 text-xs text-muted">
                <label className="flex cursor-pointer items-center gap-1.5">
                  <input type="checkbox" className="accent-[#3ee0a8]" checked={s.alerts_enabled} onChange={() => toggle(s)} />{t("Alertes")}
                </label>
                <button type="button" className="hover:text-danger hover:underline" onClick={() => remove(s)}>{t("Supprimer")}</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
