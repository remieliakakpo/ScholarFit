"use client";
import Link from "next/link";
import Icon from "./Icon";
import { useT } from "./LangProvider";

/** Bandeau horizontal qui propose l'aide d'un conseiller ; les formules et prix sont sur /tarifs. */
export default function AdvisorBanner({ scholarshipId, note }: { scholarshipId?: number; note?: React.ReactNode }) {
  const { t } = useT();
  const href = scholarshipId ? `/tarifs?bourse=${scholarshipId}` : "/tarifs";
  return (
    // overflow-clip (et non hidden) : le halo est coupé sans rendre le bandeau défilable
    // (sinon le focus clavier sur le bouton peut décaler tout le contenu vers la gauche)
    <div className="relative flex flex-col gap-5 overflow-clip rounded-3xl bg-night p-6 text-white sm:flex-row sm:items-center sm:p-8">
      <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-mint/20 blur-3xl" />
      <span className="relative grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-mint/15 text-[#3ee0a8]">
        <Icon name="people" className="h-7 w-7" />
      </span>
      <div className="relative min-w-0 flex-1">
        <p className="font-serif text-xl font-semibold leading-snug sm:text-2xl">{t("Un expert pour monter votre dossier ?")}</p>
        <p className="mt-1 text-sm text-white/70">
          {t("Un conseiller choisit avec vous les bonnes bourses, relit votre CV et votre lettre, et vous prépare à l'entretien. Postuler seul reste gratuit.")}
        </p>
        {note && <p className="mt-2 text-sm text-[#ffc979]">{note}</p>}
      </div>
      <Link href={href} className="btn-primary relative shrink-0 whitespace-nowrap">
        {t("Parler à un conseiller")} <Icon name="arrow" className="h-4 w-4" />
      </Link>
    </div>
  );
}
