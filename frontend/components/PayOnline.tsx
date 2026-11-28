"use client";
import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { useT } from "@/components/LangProvider";
import { Payment, PaymentConfig, getPaymentConfig, startCheckout } from "@/lib/payments";

/** Bouton « Payer par Mobile Money ou carte ». Ne s'affiche pas si le paiement en ligne est désactivé. */
export default function PayOnline({ purpose, coachingId, amountLabel, onConfig, className = "", orTransfer = false }: {
  purpose: Payment["purpose"]; coachingId?: number; amountLabel?: string | null; onConfig?: (c: PaymentConfig) => void; className?: string;
  /** Ajoute en dessous « Ou par transfert sur nos numéros » (quand le paiement manuel suit). */
  orTransfer?: boolean;
}) {
  const { t } = useT();
  const [cfg, setCfg] = useState<PaymentConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPaymentConfig().then((c) => { setCfg(c); onConfig?.(c); }).catch(() => setCfg(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!cfg?.online) return null;

  async function pay() {
    setBusy(true);
    setError(null);
    try {
      await startCheckout(purpose, coachingId);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className={className}>
    <div className="rounded-2xl border border-brand/40 bg-brand-soft/40 p-4">
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand"><Icon name="lock" className="h-4 w-4" /></span>
        <div className="min-w-0">
          <p className="text-sm font-semibold">{t("Paiement en ligne sécurisé")}</p>
          <p className="mt-0.5 text-xs text-muted">{cfg.methods.join(" · ")}</p>
        </div>
      </div>
      <button className="btn-primary mt-3 w-full" onClick={pay} disabled={busy}>
        {busy ? t("Ouverture du paiement…") : amountLabel ? t("Payer {p}", { p: amountLabel }) : t("Payer par Mobile Money ou carte")}
        {!busy && <Icon name="arrow" className="h-4 w-4" />}
      </button>
      <p className="mt-2 text-xs text-muted">{t("Paiement sécurisé par CinetPay. Votre accès est activé dès la confirmation du paiement.")}</p>
      {cfg.test_mode && <p className="mt-1 text-xs text-gold-dark">{t("Mode d'essai : aucun montant n'est débité.")}</p>}
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
    </div>
    {orTransfer && (
      <p className="mt-4 flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.12em] text-muted">
        <span className="h-px flex-1 bg-line" />{t("Ou par transfert sur nos numéros")}<span className="h-px flex-1 bg-line" />
      </p>
    )}
    </div>
  );
}
