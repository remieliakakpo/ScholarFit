import type { Metadata } from "next";
import { notFound } from "next/navigation";
import DestinationView, { destinationTitle } from "@/components/DestinationView";
import { getT } from "@/lib/i18n-server";
import { KIND_SLUGS, KindSlug, SITE_URL, inCountry, loadDestination } from "@/lib/seo";

type P = { params: Promise<{ slug: string; kind: string }> };

export async function generateMetadata({ params }: P): Promise<Metadata> {
  const { t, lang } = await getT();
  const { slug, kind } = await params;
  if (!KIND_SLUGS.includes(kind as KindSlug)) return {};
  const data = await loadDestination(slug, kind as KindSlug, lang);
  if (!data) return {};
  const { d } = data;
  const where = inCountry(d.name, lang);
  return {
    title: destinationTitle(d, kind as KindSlug, t, lang),
    description: t(kind === "stages" ? "{n} stages ouverts {w}, avec les conditions, les pièces à fournir, les dates limites et votre score de compatibilité."
      : kind === "conferences" ? "{n} conférences ouvertes {w}, avec les conditions, les pièces à fournir, les dates limites et votre score de compatibilité."
      : "{n} bourses d'études ouvertes {w}, avec les conditions, les pièces à fournir, les dates limites et votre score de compatibilité.", { n: d.total, w: where }),
    alternates: { canonical: `${SITE_URL}/destinations/${d.slug}/${kind}` },
  };
}

export default async function Page({ params }: P) {
  const { t, lang } = await getT();
  const { slug, kind } = await params;
  if (!KIND_SLUGS.includes(kind as KindSlug)) notFound();
  const data = await loadDestination(slug, kind as KindSlug, lang);
  if (!data) notFound();
  return <DestinationView d={data.d} meta={data.meta} kind={kind as KindSlug} t={t} lang={lang} />;
}
