import type { Metadata } from "next";
import Link from "next/link";
import Flag from "@/components/Flag";
import { getT } from "@/lib/i18n-server";
import { SITE_URL, loadDestinations } from "@/lib/seo";

const REGIONS: [string, string][] = [["afrique", "Afrique"], ["europe", "Europe"], ["amerique", "Amériques"], ["asie", "Asie et Moyen-Orient"], ["oceanie", "Océanie"]];

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getT();
  return {
    title: t("Bourses d'études par pays"),
    description: t("Toutes les bourses d'études, stages et conférences ouverts, classés par pays d'études, du bac au doctorat."),
    alternates: { canonical: `${SITE_URL}/destinations` },
  };
}

export default async function Page() {
  const { t, lang } = await getT();
  const rows = await loadDestinations(lang);
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
      <p className="eyebrow">{t("Destinations")}</p>
      <h1 className="mt-2 text-3xl sm:text-4xl">{t("Bourses d'études par pays")}</h1>
      <p className="mt-3 max-w-2xl text-muted">{t("Choisissez un pays pour voir les bourses, stages et conférences ouverts, avec leurs conditions et leurs dates limites.")}</p>
      <div className="mt-10 space-y-10">
        {REGIONS.map(([code, label]) => {
          const list = rows.filter((r) => r.region === code);
          if (!list.length) return null;
          return (
            <section key={code} aria-labelledby={`r-${code}`}>
              <h2 id={`r-${code}`} className="text-xl">{t(label)}</h2>
              <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {list.map((r) => (
                  <li key={r.code}>
                    <Link href={`/destinations/${r.slug}`} className="card flex items-center gap-3 px-4 py-3 transition hover:border-brand">
                      <Flag code={r.code} className="h-5 w-7" />
                      <span className="min-w-0 flex-1 truncate font-medium">{r.name}</span>
                      <span className="text-sm text-muted">{r.total}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
        {rows.length === 0 && <p className="card p-8 text-center text-muted">{t("Chargement…")}</p>}
      </div>
    </div>
  );
}
