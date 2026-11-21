"use client";
import Link from "next/link";
import Icon from "@/components/Icon";
import { useT } from "@/components/LangProvider";

/** Affichée par le service worker quand une page demandée n'a jamais été ouverte et qu'il n'y a pas de réseau. */
export default function OfflinePage() {
  const { t } = useT();
  return (
    <div className="mx-auto max-w-md py-10">
      <div className="card p-8 text-center">
        <Icon name="offline" className="mx-auto h-10 w-10 text-gold" />
        <h1 className="mt-4 text-2xl">{t("Pas de connexion")}</h1>
        <p className="mt-2 text-sm text-muted">{t("Cette page n'a pas encore été enregistrée sur votre téléphone. Les pages déjà ouvertes (vos bourses, votre suivi et les fiches de vos candidatures) restent lisibles sans réseau.")}</p>
        <div className="mt-6 grid gap-2">
          <Link href="/suivi" className="btn-primary">{t("Mon suivi")}</Link>
          <Link href="/mes-bourses" className="btn-ghost">{t("Mes bourses")}</Link>
          <button type="button" className="btn-ghost" onClick={() => window.location.reload()}>{t("Réessayer")}</button>
        </div>
      </div>
    </div>
  );
}
