"use client";
import Link from "next/link";
import { useEffect } from "react";
import { useT } from "@/components/LangProvider";
import { reportError } from "@/lib/report-error";

/** Erreur d'affichage d'une page : message clair au lieu d'un écran blanc, et remontée à l'équipe. */
export default function PageError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { t } = useT();
  useEffect(() => reportError(error), [error]);
  return (
    <div className="mx-auto max-w-md py-12">
      <div className="card p-8 text-center">
        <h1 className="text-2xl">{t("Cette page n'a pas pu s'afficher")}</h1>
        <p className="mt-2 text-sm text-muted">{t("L'équipe a été prévenue automatiquement. Vous pouvez réessayer ou revenir à l'accueil.")}</p>
        <div className="mt-6 grid gap-2">
          <button type="button" className="btn-primary" onClick={reset}>{t("Réessayer")}</button>
          <Link href="/" className="btn-ghost">{t("← Retour à l'accueil")}</Link>
        </div>
      </div>
    </div>
  );
}
