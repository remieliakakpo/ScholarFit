"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { useT } from "@/components/LangProvider";
import RequireAuth from "@/components/RequireAuth";
import { api } from "@/lib/api";
import { Payment } from "@/lib/payments";

/** Guichet d'essai (PAYMENT_PROVIDER=simulation) : reproduit le passage par CinetPay sans débit. */
function Guichet() {
  const { t } = useT();
  const tx = useSearchParams().get("tx") || "";
  const router = useRouter();
  const [p, setP] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (tx) api<Payment>(`/api/payments/${tx}`).then(setP).catch((e) => setError(e.message));
  }, [tx]);

  async function answer(outcome: "paye" | "annule") {
    setBusy(true);
    try {
      await api<Payment>(`/api/payments/${tx}/simulate`, { method: "POST", body: JSON.stringify({ outcome }) });
      router.replace(`/paiement/retour?tx=${tx}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  if (error) return <p className="card mx-auto max-w-md p-6 text-danger">{error}</p>;
  if (!p) return <p className="text-muted">{t("Chargement…")}</p>;
  return (
    <div className="card mx-auto max-w-md p-6 sm:p-8">
      <p className="eyebrow">{t("Paiement d'essai")}</p>
      <h1 className="mt-2 text-2xl">{p.description}</h1>
      <p className="mt-4 font-serif text-3xl font-bold">{p.amount_label}</p>
      <p className="mt-1 text-xs text-muted">{t("Référence")} {p.transaction_id}</p>
      <p className="mt-5 rounded-xl border border-gold/40 bg-gold-soft p-3 text-sm text-gold-dark">
        {t("Ce guichet remplace CinetPay pendant les essais. Aucun montant n'est débité. En production, le candidat paie ici par Flooz, Mixx by Yas, Orange Money, MTN, Wave ou carte.")}
      </p>
      {p.status === "en_attente" ? (
        <div className="mt-6 grid gap-2 sm:grid-cols-2">
          <button className="btn-primary" disabled={busy} onClick={() => answer("paye")}><Icon name="check" className="h-4 w-4" /> {t("Simuler un paiement réussi")}</button>
          <button className="btn-ghost" disabled={busy} onClick={() => answer("annule")}>{t("Annuler le paiement")}</button>
        </div>
      ) : (
        <Link href={`/paiement/retour?tx=${tx}`} className="btn-primary mt-6 w-full">{t("Voir le résultat")}</Link>
      )}
    </div>
  );
}

export default function Page() {
  return <RequireAuth><Suspense><Guichet /></Suspense></RequireAuth>;
}
