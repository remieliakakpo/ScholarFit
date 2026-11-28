"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ProgressBar, StatusChip } from "@/components/CoachingWorkspace";
import { useT } from "@/components/LangProvider";
import RequireAuth from "@/components/RequireAuth";
import { Coaching, CoachingMeta, api, formatDate, formatDateTime, getCoachingMeta } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

type Queue = "a_traiter" | "a_payer" | "clos";

/** Tableau de bord de l'expert : dossiers à traiter (payés), en attente de paiement, et clos. */
function List() {
  const { t } = useT();
  const { me } = useAuth();
  const [cm, setCm] = useState<CoachingMeta | null>(null);
  const [list, setList] = useState<Coaching[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queue, setQueue] = useState<Queue>("a_traiter");

  useEffect(() => {
    getCoachingMeta().then(setCm);
    api<Coaching[]>("/api/accompagnement/conseiller").then(setList).catch((e) => setError(e.message));
  }, []);

  if (me && !me.is_advisor) return <p className="text-danger">{t("Cet espace est réservé aux conseillers. Un administrateur peut vous donner ce rôle.")}</p>;
  if (error) return <p className="text-danger">{error}</p>;
  if (!list || !cm) return <p className="text-muted">{t("Chargement…")}</p>;

  const today = new Date().toISOString().slice(0, 10);
  const active = list.filter((c) => c.status === "en_cours" || c.status === "demande");
  const groups: Record<Queue, Coaching[]> = {
    a_traiter: active.filter((c) => c.payment_status !== "a_payer"),
    a_payer: active.filter((c) => c.payment_status === "a_payer"),
    clos: list.filter((c) => c.status === "termine" || c.status === "annule"),
  };
  // les plus urgents d'abord : messages non lus, étape en retard, puis prochaine échéance
  const urgency = (c: Coaching) => [c.unread > 0 ? 0 : 1, c.next_step?.due_date && c.next_step.due_date < today ? 0 : 1, c.next_step?.due_date ?? "9999"].join("|");
  const shown = [...groups[queue]].sort((a, b) => urgency(a).localeCompare(urgency(b)));
  const late = groups.a_traiter.filter((c) => c.next_step?.due_date && c.next_step.due_date < today).length;
  const unread = active.reduce((n, c) => n + c.unread, 0);
  const tabs: { k: Queue; label: string }[] = [
    { k: "a_traiter", label: t("À traiter") },
    { k: "a_payer", label: t("En attente de paiement") },
    { k: "clos", label: t("Clos") },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl">{t("Espace conseiller")}</h1>
        <p className="mt-1 text-muted">{t("Vos dossiers, du paiement jusqu'au dépôt de la candidature.")}</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          [t("À traiter"), groups.a_traiter.length, "text-brand"],
          [t("Étapes en retard"), late, late ? "text-danger" : "text-ink"],
          [t("Messages non lus"), unread, unread ? "text-gold-dark" : "text-ink"],
          [t("En attente de paiement"), groups.a_payer.length, "text-ink"],
        ].map(([label, n, cls]) => (
          <div key={label as string} className="card p-4">
            <p className={`font-serif text-3xl font-bold ${cls}`}>{n}</p>
            <p className="mt-1 text-xs text-muted">{label}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-line" role="tablist">
        {tabs.map((tb) => (
          <button key={tb.k} role="tab" aria-selected={queue === tb.k} onClick={() => setQueue(tb.k)}
            className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${queue === tb.k ? "border-brand font-semibold text-brand-dark" : "border-transparent text-muted hover:text-ink"}`}>
            {tb.label} · {groups[tb.k].length}
          </button>
        ))}
      </div>

      {shown.length === 0 && (
        <p className="card p-8 text-center text-muted">
          {queue === "a_traiter" ? t("Aucun dossier à traiter pour l'instant. Les nouvelles demandes vous sont attribuées selon votre langue, vos pays et vos domaines.")
            : queue === "a_payer" ? t("Aucun dossier en attente de paiement.") : t("Aucun accompagnement clos.")}
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {shown.map((c) => {
          const isLate = c.next_step?.due_date && c.next_step.due_date < today;
          return (
            <Link key={c.id} href={`/conseiller/${c.id}`} className="card block p-5 transition hover:border-brand">
              <div className="flex items-center justify-between gap-2">
                <p className="font-serif text-lg font-bold">{c.student_name}</p>
                <div className="flex items-center gap-2">
                  {c.unread > 0 && <span className="rounded-full bg-warm px-2 py-0.5 text-xs font-bold text-white">{t("{n} non lu(s)", { n: c.unread })}</span>}
                  <StatusChip status={c.status} label={cm.statuses[c.status]} />
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {c.offer_name && <span className="chip">{c.offer_name}</span>}
                {c.payment_status === "paye" && <span className="chip border-brand/40 text-brand">{t("Payé")}</span>}
                {c.payment_status === "offert" && <span className="chip">{t("Offert")}</span>}
                {c.payment_status === "a_payer" && <span className="chip border-warm/40 text-warm">{t("En attente de paiement")}</span>}
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-muted">{c.goal}</p>
              <div className="mt-3"><ProgressBar value={c.progress} /></div>
              <div className="mt-2 space-y-0.5 text-xs">
                {c.next_step && <p className={isLate ? "font-semibold text-danger" : "text-muted"}>{t("Prochaine étape :")} {c.next_step.title}{c.next_step.due_date ? ` · ${formatDate(c.next_step.due_date)}` : ""}</p>}
                {c.next_meeting && <p className="text-muted">{t("Rendez-vous :")} {formatDateTime(c.next_meeting.starts_at)}</p>}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default function ConseillerPage() {
  return <RequireAuth><List /></RequireAuth>;
}
