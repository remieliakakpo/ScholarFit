"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Scholarship, api, deadlineInfo } from "@/lib/api";
import Flag from "./Flag";
import Icon from "./Icon";
import { ConferenceArt, InternshipArt } from "./Illustrations";
import { useT } from "./LangProvider";

type Page = { total: number; items: Scholarship[] };

/** Section d'accueil : stages et conférences, avec les trois prochaines offres de chaque type. */
export default function KindsShowcase() {
  const { t } = useT();
  const [data, setData] = useState<Record<string, Page | null>>({ stage: null, conference: null });
  useEffect(() => {
    (["stage", "conference"] as const).forEach((k) =>
      api<Page>(`/api/scholarships?kind=${k}&per_page=3`).then((p) => setData((d) => ({ ...d, [k]: p }))).catch(() => setData((d) => ({ ...d, [k]: { total: 0, items: [] } }))),
    );
  }, []);
  const blocks = [
    { kind: "stage", art: InternshipArt, eyebrow: t("Stages"), title: t("Une première expérience à l'international."), text: t("Stages rémunérés dans les organisations internationales, les institutions européennes et les grandes entreprises, ouverts aux étudiants et jeunes diplômés."), cta: t("Voir tous les stages"), unit: (n: number) => t(n > 1 ? "{n} stages ouverts" : "{n} stage ouvert", { n }) },
    { kind: "conference", art: ConferenceArt, eyebrow: t("Conférences"), title: t("Rencontrer, présenter, se faire connaître."), text: t("Conférences, écoles d'été et sommets pour jeunes chercheurs et étudiants, souvent avec frais de voyage et d'hébergement pris en charge."), cta: t("Voir toutes les conférences"), unit: (n: number) => t(n > 1 ? "{n} conférences ouvertes" : "{n} conférence ouverte", { n }) },
  ];
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {blocks.map((b) => {
        const page = data[b.kind];
        const Art = b.art;
        return (
          <div key={b.kind} className="card group relative flex flex-col overflow-hidden p-6 sm:p-8">
            <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-mint/10 blur-3xl" />
            <div className="relative flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="eyebrow">{b.eyebrow}</p>
                <h3 className="mt-2 text-xl sm:text-2xl">{b.title}</h3>
                <p className="mt-2 text-sm text-muted">{b.text}</p>
              </div>
              <Art className="lite-hide hidden w-32 shrink-0 sm:block md:w-40" />
            </div>
            <ul className="relative mt-6 space-y-2">
              {page === null
                ? [0, 1, 2].map((i) => <li key={i} className="h-[58px] animate-pulse rounded-xl bg-surface" />)
                : page.items.map((s) => (
                    <li key={s.id}>
                      <Link href={`/bourses/${s.id}`} className="flex items-center gap-3 rounded-xl border border-line bg-surface px-3.5 py-2.5 transition hover:-translate-y-0.5 hover:border-brand/50">
                        {s.study_countries[0] ? <Flag code={s.study_countries[0]} className="h-4 w-6" /> : <Icon name="globe" className="h-4 w-4 shrink-0 text-muted" />}
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold">{s.title}</span>
                          <span className="block truncate text-xs text-muted">{s.organization}</span>
                        </span>
                        <span className="hidden shrink-0 text-[11px] text-muted sm:block">{deadlineInfo(s).label}</span>
                      </Link>
                    </li>
                  ))}
            </ul>
            <div className="relative mt-5 flex flex-wrap items-center justify-between gap-3 pt-1">
              <span className="text-sm font-semibold text-brand">{page ? b.unit(page.total) : " "}</span>
              <Link href={`/bourses?kind=${b.kind}`} className="btn-ghost px-4 py-2 text-sm">{b.cta} <Icon name="arrow" className="h-4 w-4" /></Link>
            </div>
          </div>
        );
      })}
    </div>
  );
}
