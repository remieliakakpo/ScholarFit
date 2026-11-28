"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Payment, PaymentConfig } from "@/lib/payments";

type Data = {
  totals: { month: number; last_30_days: number; all_time: number; pending: number; month_label: string; last_30_days_label: string; all_time_label: string };
  config: PaymentConfig;
  items: Payment[];
};

const STYLE: Record<string, string> = { paye: "text-brand", en_attente: "text-gold-dark", echoue: "text-danger", annule: "text-muted" };

/** Administration : paiements en ligne (CinetPay), encaissé du mois et paiements en attente. */
export default function AdminPayments() {
  const [d, setD] = useState<Data | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => api<Data>(`/api/admin/payments${filter ? `?status=${filter}` : ""}`).then(setD).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

  async function check(tx: string) {
    await api(`/api/admin/payments/${tx}/refresh`, { method: "POST" }).catch((e) => setError(e.message));
    load();
  }

  return (
    <section className="card space-y-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl">Paiements en ligne</h2>
        {d && <span className="chip">{d.config.provider === "cinetpay" ? "CinetPay" : d.config.provider === "simulation" ? "Mode d'essai (simulation)" : "Paiement en ligne désactivé"}</span>}
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
      {d && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[["Ce mois-ci", d.totals.month_label], ["30 derniers jours", d.totals.last_30_days_label], ["Depuis le début", d.totals.all_time_label], ["En attente", String(d.totals.pending)]].map(([l, v]) => (
              <div key={l} className="rounded-xl border border-line bg-surface p-3">
                <p className="font-serif text-xl font-bold">{v}</p>
                <p className="text-xs text-muted">{l}</p>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-2 text-sm">
            {[["", "Tous"], ["paye", "Payés"], ["en_attente", "En attente"], ["echoue", "Échoués"], ["annule", "Annulés"]].map(([k, l]) => (
              <button key={k} className={`chip ${filter === k ? "border-brand text-brand" : ""}`} onClick={() => setFilter(k)}>{l}</button>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted">
                <tr><th className="py-2">Date</th><th>Compte</th><th>Objet</th><th>Montant</th><th>Moyen</th><th>Statut</th><th /></tr>
              </thead>
              <tbody className="divide-y divide-line">
                {d.items.map((p) => (
                  <tr key={p.transaction_id}>
                    <td className="py-2 text-muted">{p.created_at ? new Date(p.created_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : ""}</td>
                    <td className="max-w-[12rem] truncate">{p.email}</td>
                    <td>{p.purpose === "abonnement" ? "Abonnement CV" : `Accompagnement n° ${p.coaching_id}`}</td>
                    <td className="whitespace-nowrap">{p.amount_label}</td>
                    <td className="text-muted">{p.method ?? p.provider}</td>
                    <td className={STYLE[p.status]}>{p.status_label}</td>
                    <td>{p.status === "en_attente" && p.provider === "cinetpay" && <button className="text-xs text-brand hover:underline" onClick={() => check(p.transaction_id)}>Revérifier</button>}</td>
                  </tr>
                ))}
                {d.items.length === 0 && <tr><td colSpan={7} className="py-6 text-center text-muted">Aucun paiement.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
