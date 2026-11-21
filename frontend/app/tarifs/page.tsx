import type { Metadata } from "next";
import Link from "next/link";
import Icon from "@/components/Icon";
import Offers from "@/components/Offers";
import { getT } from "@/lib/i18n-server";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getT();
  return {
    title: t("Tarifs de l'accompagnement"),
    description: t("Postuler seul est gratuit. Un conseiller peut aussi monter votre dossier avec vous : formules Standard et Premium."),
  };
}

const STEPS = [
  { icon: "people", t: "Un conseiller vous est attribué", d: "Selon votre niveau, votre domaine, vos pays visés et votre langue, souvent le jour même." },
  { icon: "calendar", t: "Un plan d'étapes daté", d: "Construit à rebours depuis vos dates limites, avec un rappel la veille de chaque étape." },
  { icon: "file", t: "Votre dossier relu et préparé", d: "CV, lettre, recommandations, entretien blanc et visa selon la formule choisie." },
];

export default async function TarifsPage({ searchParams }: { searchParams: Promise<{ bourse?: string }> }) {
  const { t } = await getT();
  const bourse = Number((await searchParams).bourse) || undefined;
  return (
    <div className="mx-auto max-w-6xl space-y-12 py-4">
      <div>
        <p className="eyebrow">{t("Tarifs")}</p>
        <h1 className="mt-2 text-[1.9rem] leading-tight sm:text-4xl">{t("Postulez seul ou faites-vous")} <span className="accent">{t("accompagner.")}</span></h1>
        <p className="mt-3 max-w-2xl text-muted">{t("Postuler vous-même est gratuit. Si vous souhaitez qu'un expert relise votre dossier et vous prépare, choisissez une formule.")}</p>
      </div>

      <Offers scholarshipId={bourse} />

      <section className="grid gap-4 md:grid-cols-3">
        {STEPS.map((s, i) => (
          <div key={s.t} className="card p-5">
            <span className="text-xs font-semibold text-brand">0{i + 1}</span>
            <p className="mt-2 flex items-center gap-2 font-semibold"><Icon name={s.icon} className="h-4 w-4 text-brand" />{t(s.t)}</p>
            <p className="mt-1 text-sm text-muted">{t(s.d)}</p>
          </div>
        ))}
      </section>

      <section className="card p-6 text-sm text-muted">
        <p className="font-semibold text-ink">{t("Paiement")}</p>
        <p className="mt-1">{t("Le paiement se fait par Mobile Money (Flooz, Mixx by Yas…) une fois le conseiller attribué. Vous pouvez toujours postuler seul gratuitement, avec tous les outils de la plateforme.")}</p>
        <Link href="/#questions" className="mt-3 inline-flex items-center gap-1 font-semibold text-brand hover:underline">{t("Questions fréquentes")} <Icon name="arrow" className="h-3.5 w-3.5" /></Link>
      </section>
    </div>
  );
}
