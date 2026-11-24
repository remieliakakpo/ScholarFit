"use client";
import { useT } from "@/components/LangProvider";
import { useState } from "react";
import Icon from "@/components/Icon";
import { Credits, PayMethod, docApi } from "@/lib/docs";

/** Bandeau : dossier offert, abonnement mensuel (dossiers restants sur la période) et souscription. */
export function CreditsBar({ credits, onBuy, compact = false }: { credits: Credits; onBuy: () => void; compact?: boolean }) {
  const { t } = useT();
  const sub = credits.subscription;
  return (
    <div className={`card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between ${compact ? "" : "sm:p-5"}`}>
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand"><Icon name="file" className="h-5 w-5" /></span>
        <div>
          <p className="text-sm font-semibold">
            {credits.free_left > 0
              ? t("Votre premier dossier est offert")
              : sub.active
                ? t("Abonnement actif jusqu'au {d} · {n} dossiers restants sur {m}", { d: sub.until_label, n: sub.left_this_period, m: sub.monthly_packs })
                : t("Dossier offert déjà utilisé")}
          </p>
          <p className="text-xs text-muted sm:text-sm">
            {t("Un dossier comprend le CV et la lettre adaptés à une bourse, avec {n} générations de chaque. Abonnement : {p}, jusqu'à {m} dossiers par mois.", { n: credits.regenerations, p: credits.price_label, m: sub.monthly_packs })}
            {credits.pending_orders > 0 && <span className="text-gold-dark"> {t("Paiement en cours de vérification.")}</span>}
          </p>
        </div>
      </div>
      <button className="btn-ghost shrink-0" onClick={onBuy}>{sub.active ? t("Prolonger d'un mois") : t("S'abonner")}</button>
    </div>
  );
}

export function PayModal({ credits, onClose, onDone }: { credits: Credits; onClose: () => void; onDone: () => void }) {
  const { t } = useT();
  const [method, setMethod] = useState<PayMethod>(credits.methods[0]);
  const [reference, setReference] = useState("");
  const [phone, setPhone] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await docApi("/api/credits/orders", { method: "POST", body: JSON.stringify({ method: method.code, reference, payer_phone: phone }) });
      setSent(true);
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-end bg-black/60 p-0 animate-fade-in sm:place-items-center sm:p-4" role="dialog" aria-modal="true" aria-labelledby="pay-title" onClick={onClose}>
      <div className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-3xl border border-line bg-card p-5 animate-pop-in sm:rounded-3xl sm:p-7" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{t("Abonnement mensuel")}</p>
            <h2 id="pay-title" className="mt-1 text-xl sm:text-2xl">{t("CV et lettres adaptés à {m} bourses par mois", { m: credits.subscription.monthly_packs })}</h2>
          </div>
          <button className="rounded-full p-2 text-muted hover:text-ink" onClick={onClose} aria-label={t("Fermer")}><Icon name="close" className="h-5 w-5" /></button>
        </div>
        {sent ? (
          <div className="mt-6 space-y-3 text-sm">
            <p className="flex items-center gap-2 font-semibold text-brand"><Icon name="check" className="h-5 w-5" /> {t("Paiement déclaré")}</p>
            <p className="text-muted">{t("Notre équipe vérifie la réception et active votre abonnement, en général dans l'heure aux horaires ouvrables. Vous pourrez alors générer vos CV et vos lettres.")}</p>
            <button className="btn-primary w-full" onClick={onClose}>{t("Compris")}</button>
          </div>
        ) : (
          <>
            <p className="mt-2 text-sm text-muted">{t("Montant :")} <strong className="text-ink">{credits.price_label}</strong>. {t("Choisissez votre moyen de paiement.")}</p>
            <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-5">
              {credits.methods.map((m) => (
                <button key={m.code} type="button" onClick={() => { setMethod(m); setCopied(false); }} aria-pressed={method.code === m.code}
                  className={`flex flex-col items-center gap-1.5 rounded-2xl border p-2 text-center text-[11px] font-medium transition ${method.code === m.code ? "border-brand ring-2 ring-brand/25" : "border-line hover:border-brand/50"}`}>
                  <span className="grid h-11 w-full place-items-center rounded-xl bg-white p-1.5">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={m.logo} alt="" className="max-h-8 max-w-full object-contain" />
                  </span>
                  {m.label}
                </button>
              ))}
            </div>
            <div className="mt-4 rounded-2xl border border-line bg-surface p-4">
              <p className="text-sm text-muted">{method.how}</p>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="label !mb-0.5">{["flooz", "mixx"].includes(method.code) ? t("Numéro {m}", { m: method.label }) : t("Numéro Mobile Money à créditer")}</p>
                  <p className="font-serif text-2xl font-bold tracking-wide">{method.number}</p>
                </div>
                <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => navigator.clipboard?.writeText(method.number.replace(/\s/g, "")).then(() => setCopied(true))}>
                  <Icon name="copy" className="h-4 w-4" /> {copied ? t("Copié") : t("Copier")}
                </button>
              </div>
              <p className="mt-2 text-xs text-muted">{t("Bénéficiaire : ScholarFit. Montant exact : {p}.", { p: credits.price_label })}</p>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div>
                <label className="label" htmlFor="pay-ref">{t("Référence de la transaction")}</label>
                <input id="pay-ref" className="input" value={reference} onChange={(e) => setReference(e.target.value)} placeholder={t("Reçue par SMS")} />
              </div>
              <div>
                <label className="label" htmlFor="pay-phone">{t("Numéro qui a payé")}</label>
                <input id="pay-phone" className="input" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+228 …" />
              </div>
            </div>
            {error && <p className="mt-3 text-sm text-danger">{error}</p>}
            <button className="btn-primary mt-5 w-full" disabled={busy || (!reference.trim() && !phone.trim())} onClick={submit}>{busy ? t("Envoi…") : t("J'ai payé, activer mon abonnement")}</button>
          </>
        )}
      </div>
    </div>
  );
}
