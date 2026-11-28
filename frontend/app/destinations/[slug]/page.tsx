import type { Metadata } from "next";
import { notFound } from "next/navigation";
import DestinationView from "@/components/DestinationView";
import { getT } from "@/lib/i18n-server";
import { SITE_URL, inCountry, loadDestination } from "@/lib/seo";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { t, lang } = await getT();
  const { slug } = await params;
  const data = await loadDestination(slug, null, lang);
  if (!data) return {};
  const { d } = data;
  const where = inCountry(d.name, lang);
  return {
    title: t("Bourses d'études, stages et conférences {w}", { w: where }),
    description: t("{n} offres ouvertes {w} : bourses d'études du bac au doctorat, stages et conférences. Conditions, pièces à fournir, dates limites et score de compatibilité.", { n: d.total, w: where }),
    alternates: { canonical: `${SITE_URL}/destinations/${d.slug}` },
  };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { t, lang } = await getT();
  const { slug } = await params;
  const data = await loadDestination(slug, null, lang);
  if (!data) notFound();
  return <DestinationView d={data.d} meta={data.meta} kind={null} t={t} lang={lang} />;
}
