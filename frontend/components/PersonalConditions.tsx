"use client";
// Conditions de la bourse confrontées au profil de la personne connectée : remplie, non remplie, à compléter.
import Link from "next/link";
import { useEffect, useState } from "react";
import { useT } from "@/components/LangProvider";
import { Fit, docApi } from "@/lib/docs";
import { getToken } from "@/lib/api";

const STYLE: Record<string, { cls: string; label: string }> = {
  ok: { cls: "bg-ok-soft text-ok", label: "Remplie" },
  ko: { cls: "bg-danger/10 text-danger", label: "Non remplie" },
  attention: { cls: "bg-gold-soft text-gold-dark", label: "À vérifier" },
  inconnu: { cls: "bg-surface text-muted", label: "À compléter" },
};

export default function PersonalConditions({ scholarshipId }: { scholarshipId: number }) {
  const { t } = useT();
  const [fit, setFit] = useState<Fit | null>(null);
  useEffect(() => {
    if (!getToken()) return;
    docApi<Fit>(`/api/scholarships/${scholarshipId}/fit`).then(setFit).catch(() => setFit(null));
  }, [scholarshipId]);
  if (!fit || !fit.checks.length) return null;
  const missing = fit.checks.some((c) => c.status === "inconnu");
  return (
    <div className="card mb-4 p-4 sm:p-5">
      <p className="text-sm font-semibold">{t("Votre situation pour cette bourse")}</p>
      <ul className="mt-3 space-y-2.5 text-sm">
        {fit.checks.map((c) => {
          const st = STYLE[c.status] ?? STYLE.inconnu;
          return (
            <li key={c.key} className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
              <span className={`w-fit shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${st.cls}`}>{t(st.label)}</span>
              <span><span className="font-semibold">{c.label}.</span> <span className="text-muted">{c.detail}</span></span>
            </li>
          );
        })}
      </ul>
      {missing && <Link href="/profil" className="mt-3 inline-block text-sm font-semibold text-brand hover:underline">{t("Compléter mon profil")} →</Link>}
    </div>
  );
}
