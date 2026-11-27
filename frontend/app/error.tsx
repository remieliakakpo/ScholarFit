"use client";
// Filet de sécurité : si une page plante dans le navigateur, on affiche ce message
// (avec l'en-tête et le menu du site) au lieu de l'écran noir « Application error ».
import Link from "next/link";
import { useEffect } from "react";
import { useT } from "@/components/LangProvider";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { t } = useT();
  useEffect(() => { console.error(error); }, [error]);
  return (
    <div className="card mx-auto my-10 max-w-md p-8 text-center">
      <p className="font-serif text-xl">{t("Un problème est survenu sur cette page.")}</p>
      <p className="mt-2 text-sm text-muted">{t("Rechargez la page. Si le problème continue, revenez dans quelques minutes : vos données ne sont pas perdues.")}</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <button className="btn-primary" onClick={() => reset()}>{t("Réessayer")}</button>
        <Link href="/" className="btn-ghost">{t("Retour à l'accueil")}</Link>
      </div>
    </div>
  );
}
