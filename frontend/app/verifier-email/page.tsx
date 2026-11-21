"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/components/LangProvider";

/** Lien reçu par e-mail après l'inscription : confirme l'adresse. */
function Page() {
  const { t } = useT();
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<"busy" | "ok" | "error">("busy");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setError(t("Lien incomplet : ouvrez le lien reçu par e-mail en entier."));
      return;
    }
    api("/api/auth/verifier-email", { method: "POST", body: JSON.stringify({ token }) })
      .then(() => {
        setState("ok");
        window.dispatchEvent(new Event("auth-change")); // le bandeau « confirmez votre adresse » disparaît
      })
      .catch((e) => {
        setState("error");
        setError((e as Error).message);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="mx-auto max-w-md py-10">
      <div className="card p-8 text-center">
        {state === "busy" && <p className="text-muted">{t("Vérification de votre adresse…")}</p>}
        {state === "ok" && (
          <>
            <h1 className="text-2xl">{t("Adresse confirmée")}</h1>
            <p className="mt-2 text-sm text-muted">{t("Merci ! Votre compte est complet : vous pouvez demander un accompagnement et payer vos dossiers.")}</p>
            <Link href="/mes-bourses" className="btn-primary mt-6 w-full">{t("Voir mes bourses")}</Link>
          </>
        )}
        {state === "error" && (
          <>
            <h1 className="text-2xl">{t("Lien non valable")}</h1>
            <p className="mt-2 text-sm text-danger">{error}</p>
            <p className="mt-2 text-sm text-muted">{t("Connectez-vous : un bouton « Renvoyer le lien » apparaît en haut de votre espace.")}</p>
            <Link href="/connexion" className="btn-primary mt-6 w-full">{t("Se connecter")}</Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return <Suspense><Page /></Suspense>;
}
