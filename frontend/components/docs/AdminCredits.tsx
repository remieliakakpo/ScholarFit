"use client";
import { useT } from "@/components/LangProvider";
import { useCallback, useEffect, useState } from "react";
import { docApi } from "@/lib/docs";

type Order = { id: number; amount: number; method: string; reference: string | null; payer_phone: string | null; status: string; status_label: string; created_at: string; email: string | null };
const METHODS: Record<string, string> = { flooz: "Flooz", mixx: "Mixx by Yas", taptap_send: "TapTap Send", lemfi: "LemFi", pi_spi: "PI-SPI" };

/** Paiements des abonnements CV + lettres à valider. */
export default function AdminCredits() {
  const { t, lang } = useT();
  const [orders, setOrders] = useState<Order[]>([]);
  const [filter, setFilter] = useState("en_verification");
  const load = useCallback(() => {
    docApi<Order[]>(`/api/admin/credit-orders${filter ? `?status=${filter}` : ""}`).then(setOrders).catch(() => setOrders([]));
  }, [filter]);
  useEffect(load, [load]);
  async function setStatus(id: number, status: string) {
    await docApi(`/api/admin/credit-orders/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
    load();
  }
  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg">{t("Paiements des abonnements CV et lettres")}</h2>
          <p className="text-sm text-muted">{t("Vérifiez la réception sur le compte Mobile Money, puis validez : l'abonnement de l'étudiant démarre pour 30 jours, ou est prolongé d'un mois.")}</p>
        </div>
        <select className="input !w-auto" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="en_verification">{t("À vérifier")}</option><option value="paye">{t("Payés")}</option><option value="refuse">{t("Refusés")}</option><option value="">{t("Tous")}</option>
        </select>
      </div>
      {orders.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t("Aucun paiement dans cette liste.")}</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted"><tr><th className="py-2">{t("Date")}</th><th>{t("Étudiant")}</th><th>{t("Moyen")}</th><th>{t("Référence")}</th><th>{t("Montant")}</th><th>{t("Statut")}</th><th /></tr></thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className="border-t border-line">
                  <td className="py-2">{new Date(o.created_at).toLocaleString(lang === "en" ? "en-GB" : "fr-FR", { dateStyle: "short", timeStyle: "short" })}</td>
                  <td>{o.email}</td>
                  <td>{METHODS[o.method] ?? o.method}</td>
                  <td>{o.reference || "-"}{o.payer_phone ? <span className="block text-xs text-muted">{o.payer_phone}</span> : null}</td>
                  <td>{o.amount.toLocaleString(lang === "en" ? "en-GB" : "fr-FR")} {t("F CFA")}</td>
                  <td>{o.status_label}</td>
                  <td className="space-x-2 whitespace-nowrap text-right">
                    {o.status !== "paye" && <button className="btn-primary px-3 py-1 text-xs" onClick={() => setStatus(o.id, "paye")}>{t("Valider")}</button>}
                    {o.status === "en_verification" && <button className="btn-ghost px-3 py-1 text-xs" onClick={() => setStatus(o.id, "refuse")}>{t("Refuser")}</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
