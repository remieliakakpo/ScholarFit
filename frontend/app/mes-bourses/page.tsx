"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import Icon from "@/components/Icon";
import ScholarshipCard from "@/components/ScholarshipCard";
import { SavedSearchList } from "@/components/SavedSearches";
import { AlertItem, Match, Meta, api, getMeta } from "@/lib/api";
import { useT } from "@/components/LangProvider";

type MatchesOut = { minimum_ok: boolean; missing_minimum: string[]; excluded_count: number; items: Match[] };

function Matches() {
  const { t } = useT();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [data, setData] = useState<MatchesOut | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [chance, setChance] = useState("");

  useEffect(() => {
    getMeta().then(setMeta);
    api<MatchesOut>("/api/matches").then(setData).catch((e) => setError(e.message));
    api<AlertItem[]>("/api/alerts").then(setAlerts).catch(() => {});
  }, []);

  if (error) return <p className="text-danger">{error}</p>;
  if (!data) return <p className="text-muted">{t("Calcul de vos bourses…")}</p>;
  if (!data.minimum_ok)
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <div className="card p-8 text-center">
          <p className="font-serif text-2xl">{t("Complétez d'abord votre profil minimum")}</p>
          <p className="mt-2 text-sm text-muted">{t("Il manque :")} {data.missing_minimum.join(", ")}{t(". Sans ces informations, nous ne pouvons pas exclure les bourses auxquelles vous n'avez pas droit.")}</p>
          <Link href="/profil" className="btn-primary mt-4">{t("Compléter mon profil")}</Link>
        </div>
        {/* Les recherches enregistrées et leurs alertes ne dépendent pas du profil */}
        <SavedSearchList />
      </div>
    );

  const unread = alerts.filter((a) => !a.read);
  const items = chance ? data.items.filter((m) => m.chance === chance) : data.items;
  const count = (c: string) => data.items.filter((m) => m.chance === c).length;
  const tabs: [string, string, number][] = [["", t("Recommandées"), data.items.length], ["bonne", t("Très compatibles"), count("bonne")], ["moyenne", t("Compatibles"), count("moyenne")], ["faible", t("À renforcer"), count("faible")]];
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-5">
        <div>
          <h1 className="text-[1.65rem] sm:text-3xl">{t("Mes bourses")}</h1>
          <p className="mt-1 text-muted">{t("{n} bourse(s) ouverte(s) pour vous, triées par pertinence et urgence.", { n: data.items.length })} {t("{n} exclue(s) car vous n'y avez pas droit.", { n: data.excluded_count })}</p>
        </div>
        <div className="flex gap-1 overflow-x-auto border-b border-line">
          {tabs.map(([k, label, n]) => (
            <button key={k} onClick={() => setChance(k)}
              className={`-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-sm ${chance === k ? "border-brand font-semibold text-ink" : "border-transparent text-muted hover:text-ink"}`}>
              {label}<span className={`rounded-full px-1.5 text-[11px] ${chance === k ? "bg-mint text-[#04140e]" : "bg-surface text-muted"}`}>{n}</span>
            </button>
          ))}
        </div>
        <div className="space-y-4">
          {items.map((m) => <ScholarshipCard key={m.scholarship.id} s={m.scholarship} match={m} meta={meta} loggedIn />)}
          {items.length === 0 && <p className="card p-6 text-center text-sm text-muted">{t("Aucune bourse dans cette catégorie.")}</p>}
        </div>
      </div>

      <aside className="space-y-4">
        <div className="card p-5">
          <p className="flex items-center gap-2 text-sm font-semibold"><Icon name="bolt" className="h-4 w-4 text-gold" />{t("Alertes")}</p>
          {unread.length === 0 ? (
            <p className="mt-2 text-sm text-muted">{t("Rien de nouveau. Nous vous prévenons dès qu'une bourse correspond ou qu'une date limite approche.")}</p>
          ) : (
            <ul className="mt-3 space-y-3 text-sm">
              {unread.slice(0, 5).map((a) => (
                <li key={a.id} className="flex items-start justify-between gap-3 border-l-2 border-gold pl-3">
                  <span>{a.message}</span>
                  <button className="text-xs text-muted hover:underline" onClick={async () => { await api(`/api/alerts/${a.id}/read`, { method: "POST" }); setAlerts(alerts.map((x) => x.id === a.id ? { ...x, read: true } : x)); }}>OK</button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <SavedSearchList />
        <div className="card p-5 text-sm">
          <p className="font-semibold">{t("Comment lire le score")}</p>
          <p className="mt-2 text-muted">{t("Le score mesure la compatibilité entre votre profil et les critères de chaque bourse : niveau, domaine, notes, langues, pays et financement.")}</p>
          <Link href="/profil" className="mt-3 inline-flex items-center gap-1 font-semibold text-brand hover:underline">{t("Améliorer mon profil")} <Icon name="arrow" className="h-3.5 w-3.5" /></Link>
        </div>
      </aside>
    </div>
  );
}

export default function Page() {
  return <RequireAuth><Matches /></RequireAuth>;
}
