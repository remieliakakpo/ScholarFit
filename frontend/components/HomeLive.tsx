"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CountryStat, api, getCountryStats } from "@/lib/api";
import { REGIONS, regionOf } from "@/lib/geo";
import Flag from "./Flag";
import Icon from "./Icon";
import CountUp from "./CountUp";
import { useT } from "./LangProvider";
import WorldGlobe from "./WorldGlobe";
import { useLite } from "./AppRuntime";
import { countryName } from "@/lib/i18n";

function useCountryStats() {
  const [rows, setRows] = useState<CountryStat[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { getCountryStats().then(setRows).catch(() => setFailed(true)); }, []);
  return { rows, failed };
}

export function HeroGlobe() {
  const { rows } = useCountryStats();
  const { lang, t } = useT();
  const lite = useLite();
  if (lite) {
    const top = [...(rows ?? [])].sort((a, b) => b.count - a.count).slice(0, 12);
    return (
      <div className="card p-5">
        <p className="text-sm font-semibold">{t("Pays d'études les plus représentés")}</p>
        <ul className="mt-3 grid grid-cols-2 gap-2 text-sm">
          {top.map((r) => (
            <li key={r.code}>
              <Link href={`/bourses?country=${r.code}&country_exact=true&kind=bourse`} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1 hover:bg-surface">
                <span className="truncate">{countryName(r.code, lang, r.name)}</span><span className="tabular-nums text-muted">{r.count}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <div className="relative aspect-square w-full">
      <WorldGlobe markers={(rows ?? []).map((r) => ({ code: r.code, name: countryName(r.code, lang, r.name), count: r.count }))} />
      <p className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs text-muted">{t("Faites tourner le globe")}</p>
    </div>
  );
}

/** Carrousel des pays d'études : 4 pays visibles au plus, un pas toutes les 5 secondes, nombre exact de bourses. */
export function CountryCarousel() {
  const { rows, failed } = useCountryStats();
  const { lang, t } = useT();
  const [perView, setPerView] = useState(4);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    const fit = () => setPerView(window.innerWidth < 640 ? 1 : window.innerWidth < 1024 ? 2 : 4);
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);
  const count = rows?.length ?? 0;
  const last = Math.max(0, count - perView);
  useEffect(() => {
    if (paused || last === 0 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => setIndex((i) => (i >= last ? 0 : i + 1)), 5000);
    return () => clearInterval(t);
  }, [paused, last]);
  useEffect(() => { setIndex((i) => Math.min(i, last)); }, [last]);

  if (failed) return <p className="py-6 text-center text-sm text-muted">{t("Les pays s'afficheront dans un instant.")}</p>;
  if (!rows) return <div className="h-[132px]" />;
  const max = Math.max(1, ...rows.map((r) => r.count));
  const go = (d: number) => setIndex((i) => (i + d < 0 ? last : i + d > last ? 0 : i + d));
  return (
    <div onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}>
      <div className="overflow-hidden">
        <div className="flex transition-transform duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]" style={{ transform: `translateX(-${(100 * index) / perView}%)` }}>
          {rows.map((r) => {
            const region = r.region ?? regionOf(r.code);
            return (
              <div key={r.code} className="shrink-0 px-1.5" style={{ width: `${100 / perView}%` }}>
                <Link href={`/bourses?country=${r.code}&country_exact=true&kind=bourse`}
                  className="group flex h-full flex-col justify-between rounded-2xl border border-line bg-card p-5 transition hover:-translate-y-0.5 hover:border-brand/50">
                  <span className="flex items-start justify-between gap-2">
                    <span>
                      <span className="flex items-center gap-2 font-serif text-base font-semibold"><Flag code={r.code} className="h-4 w-6" />{countryName(r.code, lang, r.name)}</span>
                      <span className="text-xs text-muted">{region ? t(REGIONS[region]?.label ?? "International") : t("International")}</span>
                    </span>
                    <Icon name="arrow" className="h-4 w-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-brand" />
                  </span>
                  <span className="mt-4 flex items-end gap-2">
                    <span className="font-serif text-3xl font-bold leading-none">{r.count}</span>
                    <span className="pb-0.5 text-xs text-muted">{t(r.count > 1 ? "bourses ouvertes" : "bourse ouverte")}</span>
                  </span>
                  <span className="mt-3 block h-1 overflow-hidden rounded-full bg-surface"><span className="block h-full rounded-full bg-gradient-to-r from-mint to-gold" style={{ width: `${(100 * r.count) / max}%` }} /></span>
                </Link>
              </div>
            );
          })}
        </div>
      </div>
      {last > 0 && (
        <div className="mt-5 flex items-center justify-between gap-4 px-1.5">
          <div className="h-1 flex-1 overflow-hidden rounded-full bg-surface" aria-hidden="true">
            <div className="h-full rounded-full bg-brand transition-all duration-700" style={{ width: `${(100 * (index + perView)) / count}%` }} />
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => go(-1)} aria-label={t("Pays précédents")} className="grid h-9 w-9 place-items-center rounded-full border border-line bg-card text-ink hover:border-brand/60"><Icon name="arrow" className="h-4 w-4 rotate-180" /></button>
            <button type="button" onClick={() => go(1)} aria-label={t("Pays suivants")} className="grid h-9 w-9 place-items-center rounded-full border border-line bg-card text-ink hover:border-brand/60"><Icon name="arrow" className="h-4 w-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
}

type Stats = { total: number; open: number; closing_soon: number; countries: number; multi_country?: number; by_kind?: Record<string, number> };

export function LiveStats() {
  const [s, setS] = useState<Stats | null>(null);
  const { t } = useT();
  useEffect(() => {
    api<Stats>("/api/stats").then(setS).catch(async () => {
      try {
        const page = await api<{ total: number; items: { study_countries: string[]; deadline: string | null }[] }>("/api/scholarships?per_page=100");
        const soon = page.items.filter((x) => x.deadline && (new Date(x.deadline).getTime() - Date.now()) / 86400000 <= 45).length;
        setS({ total: page.total, open: page.total, closing_soon: soon, countries: new Set(page.items.flatMap((x) => x.study_countries)).size });
      } catch { /* l'API n'est pas lancée */ }
    });
  }, []);
  const v = (n: number | undefined) => (s ? <CountUp value={n ?? 0} /> : "…");
  const items = [
    { value: v(s?.by_kind?.bourse ?? s?.open), label: t("bourses ouvertes") },
    { value: v((s?.by_kind?.stage ?? 0) + (s?.by_kind?.conference ?? 0)), label: t("stages et conférences") },
    { value: v(s?.closing_soon), label: t("ferment dans moins de 45 jours") },
    { value: v(s?.countries), label: t("pays") },
  ];
  return (
    <dl className="grid grid-cols-2 gap-y-6 sm:grid-cols-4">
      {items.map((i) => (
        <div key={i.label} className="border-l border-line pl-4">
          <dt className="sr-only">{i.label}</dt>
          <dd className="font-serif text-3xl font-semibold sm:text-4xl">{i.value}</dd>
          <dd className="mt-1 text-xs text-muted">{i.label}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Bandeau de drapeaux qui défile : les pays où étudier. */
export function FlagMarquee() {
  const { rows } = useCountryStats();
  const { lang } = useT();
  if (!rows?.length) return <div className="h-10" />;
  const list = rows.slice(0, 30);
  return (
    <div className="pause-on-hover relative overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]">
      <div className="animate-marquee flex w-max gap-3">
        {[...list, ...list].map((r, i) => (
          <Link key={i} href={`/bourses?country=${r.code}&country_exact=true&kind=bourse`} tabIndex={i >= list.length ? -1 : undefined} aria-hidden={i >= list.length || undefined}
            className="flex shrink-0 items-center gap-2 rounded-full border border-line bg-card px-3 py-1.5 text-xs text-muted transition hover:border-brand/50 hover:text-ink">
            <Flag code={r.code} className="h-3.5 w-5" />{countryName(r.code, lang, r.name)}
          </Link>
        ))}
      </div>
    </div>
  );
}
