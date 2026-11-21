"use client";
import { Suspense, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Icon from "@/components/Icon";
import { REGIONS } from "@/lib/geo";
import { SaveSearchButton } from "@/components/SavedSearches";
import ScholarshipCard from "@/components/ScholarshipCard";
import { Meta, Scholarship, api, getMeta } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { useT } from "@/components/LangProvider";
import { countryName } from "@/lib/i18n";

type Filters = { kind: string; q: string; level: string; region: string; country: string; country_exact: string; domain: string; nationality: string; full_funding: string; include_expired: string; sort: string };
const EMPTY: Filters = { kind: "bourse", q: "", level: "", region: "", country: "", country_exact: "", domain: "", nationality: "", full_funding: "", include_expired: "", sort: "priority" };
const KEYS = Object.keys(EMPTY) as (keyof Filters)[];
const KINDS: Record<string, { label: string; icon: string; title: string; open1: string; openN: string; all1: string; allN: string }> = {
  bourse: { label: "Bourses", icon: "medal", title: "Toutes les bourses", open1: "{n} bourse ouverte", openN: "{n} bourses ouvertes", all1: "{n} bourse", allN: "{n} bourses" },
  stage: { label: "Stages", icon: "people", title: "Tous les stages", open1: "{n} stage ouvert", openN: "{n} stages ouverts", all1: "{n} stage", allN: "{n} stages" },
  conference: { label: "Conférences", icon: "chat", title: "Conférences et événements", open1: "{n} conférence ouverte", openN: "{n} conférences ouvertes", all1: "{n} conférence", allN: "{n} conférences" },
  tout: { label: "Tout", icon: "globe", title: "Toutes les opportunités", open1: "{n} opportunité ouverte", openN: "{n} opportunités ouvertes", all1: "{n} opportunité", allN: "{n} opportunités" },
};

function fromParams(p: URLSearchParams): Filters {
  const f = { ...EMPTY };
  KEYS.forEach((k) => { const v = p.get(k); if (v) f[k] = v; });
  return f;
}

function Sel({ id, label, value, active, onChange, children }: { id: string; label: string; value: string; active: boolean; onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void; children: React.ReactNode }) {
  return (
    <div>
      <label className="label" htmlFor={`f-${id}`}>{label}</label>
      <select id={`f-${id}`} className={`input ${active ? "border-brand/60" : ""}`} value={value} onChange={onChange}>{children}</select>
    </div>
  );
}

export default function BoursesPage() {
  return <Suspense><Bourses /></Suspense>;
}

function Bourses() {
  const { t, lang } = useT();
  const { me } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [f, setF] = useState<Filters>(() => fromParams(params));
  const [page, setPage] = useState(1);
  // Les liens du carrousel (/bourses?country=XX) arrivent ici : on suit l'URL…
  const qs = params.toString();
  useEffect(() => { setF(fromParams(new URLSearchParams(qs))); setPage(1); }, [qs]);
  // …et on la met à jour quand les filtres changent (lien partageable, retour arrière).
  useEffect(() => {
    const p = new URLSearchParams();
    KEYS.forEach((k) => { if (f[k] && f[k] !== EMPTY[k]) p.set(k, f[k]); });
    const next = p.toString();
    if (next !== qs) router.replace(next ? `${pathname}?${next}` : pathname, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f]);
  const [data, setData] = useState<{ total: number; items: Scholarship[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { getMeta().then(setMeta).catch((e) => setError(e.message)); }, []);
  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), per_page: "12" });
    Object.entries(f).forEach(([k, v]) => v && !(k === "kind" && v === "tout") && params.set(k, v));
    if (f.country) params.set("country_exact", "true"); // nombre identique à celui du carrousel
    const t = setTimeout(() => {
      type Page = { total: number; items: Scholarship[] };
      api<Page>(`/api/scholarships?${params}`)
        .catch(() => { params.set("sort", params.get("sort") === "priority" ? "deadline" : params.get("sort") ?? "deadline"); return api<Page>(`/api/scholarships?${params}`); })
        .then((d) => { setError(null); setData(d); })
        .catch((e) => setError(e.message));
    }, 200);
    return () => clearTimeout(t);
  }, [f, page]);

  const set = (k: keyof Filters) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { setPage(1); setF({ ...f, [k]: e.target.value }); };
  const pages = data ? Math.max(1, Math.ceil(data.total / 12)) : 1;

  const K = KINDS[f.kind] ?? KINDS.bourse;
  const active = KEYS.filter((k) => k !== "sort" && k !== "kind" && k !== "country_exact" && f[k] && f[k] !== EMPTY[k]).length;
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[1.65rem] leading-tight sm:text-3xl">{t(K.title)}</h1>
          <p className="mt-1 text-muted">{t("Les opportunités qui ferment bientôt passent en premier.")}</p>
        </div>
        <div className="flex w-full gap-2 sm:w-auto">
          <div className="relative flex-1 sm:w-72">
            <Icon name="search" className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input className="input pl-10" placeholder={t("Rechercher par nom ou organisme")} value={f.q} onChange={set("q")} aria-label={t("Rechercher")} />
          </div>
          <button type="button" className="btn-ghost lg:hidden" onClick={() => setOpen(!open)} aria-expanded={open}>
            <Icon name="filter" className="h-4 w-4" />{t("Filtres")}{active ? ` (${active})` : ""}
          </button>
        </div>
      </div>

      <div role="tablist" aria-label={t("Type d'opportunité")} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
        {Object.entries(KINDS).map(([k, v]) => (
          <button key={k} type="button" role="tab" aria-selected={f.kind === k} onClick={() => { setPage(1); setF({ ...f, kind: k }); }}
            className={`flex shrink-0 items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition ${f.kind === k ? "border-brand bg-brand-soft text-brand" : "border-line bg-card text-muted hover:border-brand/50 hover:text-ink"}`}>
            <Icon name={v.icon} className="h-4 w-4" />{t(v.label)}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)] lg:items-start">
        <aside className={`${open ? "block" : "hidden"} card space-y-5 p-5 lg:sticky lg:top-24 lg:block`} aria-label={t("Filtres")}>
          <Sel id="level" value={f.level} active={!!f.level && f.level !== EMPTY.level} onChange={set("level")} label={t("Niveau d'études")}>
            <option value="">{t("Tous les niveaux")}</option>
            {meta && Object.entries(meta.levels).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
          </Sel>
          <Sel id="full_funding" value={f.full_funding} active={!!f.full_funding && f.full_funding !== EMPTY.full_funding} onChange={set("full_funding")} label={t("Financement")}>
            <option value="">{t("Tout")}</option>
            <option value="true">{t("Financement complet")}</option>
            <option value="false">{t("Financement partiel")}</option>
          </Sel>
          <Sel id="domain" value={f.domain} active={!!f.domain && f.domain !== EMPTY.domain} onChange={set("domain")} label={t("Domaine")}>
            <option value="">{t("Tous les domaines")}</option>
            {meta && Object.entries(meta.domains).filter(([k]) => k !== "tous").map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
          </Sel>
          <Sel id="region" value={f.region} active={!!f.region && f.region !== EMPTY.region} onChange={set("region")} label={t("Région")}>
            <option value="">{t("Monde entier")}</option>
            {Object.entries(REGIONS).map(([k, r]) => <option key={k} value={k}>{t(r.label)}</option>)}
          </Sel>
          <Sel id="country" value={f.country} active={!!f.country && f.country !== EMPTY.country} onChange={set("country")} label={t("Pays")}>
            <option value="">{t("Tous les pays")}</option>
            {meta && Object.entries(meta.countries).filter(([k]) => !f.region || REGIONS[f.region]?.codes.includes(k)).map(([k, v]) => [k, countryName(k, lang, v)]).sort((a, b) => a[1].localeCompare(b[1], lang)).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Sel>
          <Sel id="nationality" value={f.nationality} active={!!f.nationality && f.nationality !== EMPTY.nationality} onChange={set("nationality")} label={t("Ma nationalité")}>
            <option value="">{t("Toutes")}</option>
            {meta && Object.entries(meta.countries).map(([k, v]) => [k, countryName(k, lang, v)]).sort((a, b) => a[1].localeCompare(b[1], lang)).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Sel>
          <Sel id="sort" value={f.sort} active={!!f.sort && f.sort !== EMPTY.sort} onChange={set("sort")} label={t("Trier par")}>
            <option value="priority">{t("Priorité (urgentes d'abord)")}</option>
            <option value="deadline">{t("Date limite")}</option>
            <option value="amount">{t("Financement")}</option>
            <option value="title">{t("Nom")}</option>
            <option value="recent">{t("Plus récentes")}</option>
          </Sel>
          <label className="flex cursor-pointer items-start gap-2 text-sm text-muted">
            <input type="checkbox" className="mt-0.5 accent-[#3ee0a8]" checked={f.include_expired === "true"} onChange={(e) => { setPage(1); setF({ ...f, include_expired: e.target.checked ? "true" : "" }); }} />
            {t("Afficher aussi les offres clôturées")}
          </label>
          {active > 0 && (
            <button className="w-full rounded-full border border-line py-2 text-xs font-semibold text-gold-dark hover:border-gold/50" onClick={() => { setPage(1); setF({ ...EMPTY, kind: f.kind }); }}>{t("Effacer les filtres")}</button>
          )}
          {active > 0 && (
            <SaveSearchButton filters={f} suggestedName={[
              t(K.label),
              f.region && REGIONS[f.region] ? t(REGIONS[f.region].label) : null,
              f.country && meta ? countryName(f.country, lang, meta.countries[f.country]) : null,
              f.level && meta ? meta.levels[f.level] : null,
              f.domain && meta ? meta.domains[f.domain] : null,
              f.q || null,
            ].filter(Boolean).join(" · ").slice(0, 120)} />
          )}
        </aside>

        <div className="min-w-0 space-y-5">
      {error && <p className="text-danger">{error}</p>}
      {data && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
          <p><span className="font-semibold text-ink">{data.total}</span> {t(f.include_expired ? (data.total > 1 ? K.allN : K.all1) : data.total > 1 ? K.openN : K.open1, { n: "" }).trim()}{f.region && REGIONS[f.region] ? ` · ${t(REGIONS[f.region].label)}` : ""}{f.country && meta ? ` · ${countryName(f.country, lang, meta.countries[f.country])}` : ""}</p>
          <p className="flex flex-wrap items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-warm" />{t("Urgent : moins de 14 jours")}</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-gold" />{t("Bientôt : moins de 45 jours")}</span>
            {f.include_expired && <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-danger" />{t("Clôturée")}</span>}
          </p>
        </div>
      )}
      {data && data.total === 0 && (
        <div className="card p-8 text-center">
          <p className="font-serif text-xl">{t("Rien ne correspond à ces filtres pour l'instant.")}</p>
          <p className="mt-1 text-sm text-muted">{t("Élargissez la région ou le niveau, ou affichez aussi les offres clôturées pour connaître leur prochaine session.")}</p>
          <button className="btn-ghost mt-4" onClick={() => { setPage(1); setF({ ...EMPTY, kind: f.kind }); }}>{t("Effacer les filtres")}</button>
        </div>
      )}
      <div className="grid gap-4 2xl:grid-cols-2">
        {data?.items.map((s) => <ScholarshipCard key={s.id} s={s} meta={meta} loggedIn={!!me} lockedScore={!me} />)}
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t("← Précédent")}</button>
          <span className="text-sm text-muted">{t("Page")} {page} / {pages}</span>
          <button className="btn-ghost" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t("Suivant →")}</button>
        </div>
      )}
        </div>
      </div>
    </div>
  );
}
