import Link from "next/link";
import Flag from "@/components/Flag";
import Icon from "@/components/Icon";
import ScholarshipCard from "@/components/ScholarshipCard";
import { Lang } from "@/lib/i18n";
import { Destination, KIND_OF, KIND_SLUGS, KindSlug, SITE_URL, inCountry } from "@/lib/seo";
import { Meta } from "@/lib/api";

type T = (fr: string, vars?: Record<string, string | number | null | undefined>) => string;
const LABEL: Record<KindSlug, string> = { bourses: "Bourses d'études", stages: "Stages", conferences: "Conférences" };

export function destinationTitle(d: Destination, kind: KindSlug | null, t: T, lang: Lang): string {
  const where = inCountry(d.name, lang);
  const now = new Date();
  const year = now.getMonth() >= 8 ? now.getFullYear() + 1 : now.getFullYear(); // dès septembre, on candidate pour l'année suivante
  if (kind === "stages") return t("Stages {w} {y}", { w: where, y: year });
  if (kind === "conferences") return t("Conférences {w} {y}", { w: where, y: year });
  return t("Bourses d'études {w} {y}", { w: where, y: year });
}

/** Page d'un pays (ou d'un type d'offre dans un pays) : en-tête, onglets, liste des offres ouvertes. */
export default function DestinationView({ d, meta, kind, t, lang }: { d: Destination; meta: Meta; kind: KindSlug | null; t: T; lang: Lang }) {
  const where = inCountry(d.name, lang);
  const title = kind ? destinationTitle(d, kind, t, lang) : t("Étudier {w} : bourses, stages et conférences", { w: where });
  const all = Object.values(d.counts).reduce((a, b) => a + b, 0);
  const crumbs = [{ "@type": "ListItem", position: 1, name: "ScholarFit", item: SITE_URL }, { "@type": "ListItem", position: 2, name: t("Destinations"), item: `${SITE_URL}/destinations` }, { "@type": "ListItem", position: 3, name: d.name, item: `${SITE_URL}/destinations/${d.slug}` }];
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      { "@type": "BreadcrumbList", itemListElement: kind ? [...crumbs, { "@type": "ListItem", position: 4, name: t(LABEL[kind]), item: `${SITE_URL}/destinations/${d.slug}/${kind}` }] : crumbs },
      { "@type": "ItemList", name: title, numberOfItems: d.total, itemListElement: d.items.slice(0, 30).map((s, i) => ({ "@type": "ListItem", position: i + 1, url: `${SITE_URL}/bourses/${s.id}`, name: s.title })) },
    ],
  };
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />
      <nav className="flex flex-wrap items-center gap-1.5 text-xs text-muted" aria-label={t("Fil d'Ariane")}>
        <Link href="/destinations" className="hover:text-brand">{t("Destinations")}</Link><span aria-hidden>/</span>
        {kind ? <Link href={`/destinations/${d.slug}`} className="hover:text-brand">{d.name}</Link> : <span className="text-ink">{d.name}</span>}
        {kind && <><span aria-hidden>/</span><span className="text-ink">{t(LABEL[kind])}</span></>}
      </nav>
      <header className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-start">
        <Flag code={d.code} className="h-9 w-12 sm:mt-1" />
        <div className="min-w-0 flex-1">
          {d.region_name && <p className="eyebrow">{d.region_name}</p>}
          <h1 className="mt-1 text-3xl leading-tight sm:text-4xl">{title}</h1>
          <p className="mt-3 max-w-3xl text-muted">
            {d.total === 0
              ? t("Aucune offre ouverte pour le moment. La liste est mise à jour chaque semaine : créez votre compte pour être prévenu dès qu'une offre s'ouvre {w}.", { w: where })
              : d.full_funding > 0
                ? t("{n} offres ouvertes {w}, dont {f} avec un financement complet. Chaque fiche détaille les conditions, les pièces à fournir et les étapes de candidature.", { n: d.total, w: where, f: d.full_funding })
                : t("{n} offres ouvertes {w}. Chaque fiche détaille les conditions, les pièces à fournir et les étapes de candidature.", { n: d.total, w: where })}
          </p>
        </div>
      </header>

      <div className="mt-8 flex gap-1 overflow-x-auto border-b border-line">
        <Link href={`/destinations/${d.slug}`} className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${!kind ? "border-brand font-semibold text-brand-dark" : "border-transparent text-muted hover:text-ink"}`}>{t("Tout")} · {all}</Link>
        {KIND_SLUGS.map((k) => (
          <Link key={k} href={`/destinations/${d.slug}/${k}`} className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${kind === k ? "border-brand font-semibold text-brand-dark" : "border-transparent text-muted hover:text-ink"}`}>
            {t(LABEL[k])} · {d.counts[KIND_OF[k]] ?? 0}
          </Link>
        ))}
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {d.items.map((s) => <ScholarshipCard key={s.id} s={s} meta={meta} lockedScore />)}
      </div>

      <section className="card mt-10 flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-serif text-xl font-bold">{t("Quelles offres vous correspondent {w} ?", { w: where })}</p>
          <p className="mt-1 text-sm text-muted">{t("Répondez à 5 questions : nous calculons votre score pour chaque offre et écartons celles auxquelles vous n'avez pas droit.")}</p>
        </div>
        <Link href="/questionnaire" className="btn-primary shrink-0">{t("Trouver mes bourses")} <Icon name="arrow" className="h-4 w-4" /></Link>
      </section>
    </div>
  );
}
