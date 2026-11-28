"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { useT } from "@/components/LangProvider";
import RequireAuth from "@/components/RequireAuth";
import { api } from "@/lib/api";
import { Payment } from "@/lib/payments";

/** Retour après le guichet CinetPay : on interroge l'API jusqu'à la confirmation (2 minutes au plus). */
function Retour() {
  const { t } = useT();
  const fromUrl = useSearchParams().get("tx");
  const [tx, setTx] = useState<string | null>(fromUrl);
  const [p, setP] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    if (fromUrl) return;
    try { setTx(sessionStorage.getItem("sf_last_payment")); } catch { setTx(null); }
  }, [fromUrl]);

  useEffect(() => {
    if (!tx) return;
    let stop = false;
    let tries = 0;
    async function poll() {
      try {
        const r = await api<Payment>(`/api/payments/${tx}`);
        if (stop) return;
        setP(r);
        if (r.status === "en_attente" && tries++ < 24) setTimeout(poll, 5000);
        else if (r.status === "en_attente") setGaveUp(true);
      } catch (e) {
        if (!stop) setError((e as Error).message);
      }
    }
    poll();
    return () => { stop = true; };
  }, [tx]);

  if (error) return <p className="card mx-auto max-w-md p-6 text-danger">{error}</p>;
  if (!tx) return <p className="card mx-auto max-w-md p-6 text-muted">{t("Aucun paiement en cours.")}</p>;
  if (!p) return <p className="text-muted">{t("Vérification du paiement…")}</p>;

  const next = p.purpose === "abonnement" ? { href: "/cv", label: t("Préparer mes documents") } : { href: "/accompagnement", label: t("Ouvrir mon accompagnement") };
  return (
    <div className="card mx-auto max-w-md p-6 text-center sm:p-8">
      {p.status === "paye" && (
        <>
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-brand-soft text-brand"><Icon name="check" className="h-7 w-7" /></span>
          <h1 className="mt-4 text-2xl">{t("Paiement confirmé")}</h1>
          <p className="mt-2 text-sm text-muted">
            {p.purpose === "abonnement"
              ? t("Votre abonnement est actif. Vous pouvez préparer vos CV et lettres adaptés dès maintenant.")
              : t("Votre expert prend en charge votre dossier. Vous retrouvez son plan et vos échanges dans votre espace d'accompagnement.")}
          </p>
          <p className="mt-3 text-xs text-muted">{p.amount_label} · {t("Référence")} {p.transaction_id}. {t("Un reçu vous a été envoyé par e-mail.")}</p>
          <Link href={next.href} className="btn-primary mt-6 w-full">{next.label} <Icon name="arrow" className="h-4 w-4" /></Link>
        </>
      )}
      {p.status === "en_attente" && (
        <>
          <span className="mx-auto block h-10 w-10 animate-spin rounded-full border-2 border-line border-t-brand" aria-hidden />
          <h1 className="mt-4 text-2xl">{t("Confirmation en cours")}</h1>
          <p className="mt-2 text-sm text-muted">
            {gaveUp
              ? t("Votre opérateur n'a pas encore confirmé le paiement. Si vous avez validé l'opération sur votre téléphone, votre accès s'activera automatiquement dans les prochaines minutes et vous recevrez un e-mail.")
              : t("Validez l'opération sur votre téléphone si votre opérateur vous le demande. Cette page se met à jour toute seule.")}
          </p>
        </>
      )}
      {(p.status === "echoue" || p.status === "annule") && (
        <>
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-warm-soft text-warm"><Icon name="close" className="h-7 w-7" /></span>
          <h1 className="mt-4 text-2xl">{p.status === "annule" ? t("Paiement annulé") : t("Paiement non abouti")}</h1>
          <p className="mt-2 text-sm text-muted">{t("Aucun montant n'a été prélevé. Vous pouvez réessayer ou choisir le paiement par transfert.")}</p>
          <Link href={p.purpose === "abonnement" ? "/cv" : "/accompagnement"} className="btn-primary mt-6 w-full">{t("Réessayer")}</Link>
        </>
      )}
    </div>
  );
}

export default function Page() {
  return <RequireAuth><Suspense><Retour /></Suspense></RequireAuth>;
}
