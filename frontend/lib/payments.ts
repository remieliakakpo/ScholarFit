// Paiement en ligne (CinetPay, ou simulation pour les essais). Voir backend/app/payments.py.
import { api } from "./api";

export type PaymentConfig = { online: boolean; provider: "cinetpay" | "simulation" | "manuel"; test_mode: boolean; label: string; methods: string[]; note: string };
export type Payment = {
  transaction_id: string; purpose: "abonnement" | "accompagnement"; coaching_id: number | null; amount: number; currency: string;
  amount_label: string; description: string; provider: string; status: "en_attente" | "paye" | "echoue" | "annule"; status_label: string;
  method: string | null; checkout_url: string | null; created_at: string | null; paid_at: string | null; email?: string | null;
};

let cached: Promise<PaymentConfig> | null = null;
export function getPaymentConfig(): Promise<PaymentConfig> {
  if (!cached) cached = api<PaymentConfig>("/api/payments/config").catch((e) => { cached = null; throw e; });
  return cached;
}

/** Crée le paiement et envoie le navigateur vers le guichet (CinetPay ou page d'essai). */
export async function startCheckout(purpose: Payment["purpose"], coachingId?: number): Promise<void> {
  const p = await api<Payment>("/api/payments/checkout", { method: "POST", body: JSON.stringify({ purpose, coaching_id: coachingId ?? null }) });
  try { sessionStorage.setItem("sf_last_payment", p.transaction_id); } catch { /* navigation privée */ }
  if (p.checkout_url) window.location.assign(p.checkout_url);
}
