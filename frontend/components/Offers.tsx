"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { DEFAULT_OFFERS, Offer, getOffers } from "@/lib/api";
import Icon from "./Icon";
import { useT } from "@/components/LangProvider";

/** Les formules : postuler seul (gratuit) ou avec un accompagnement payant. */
export default function Offers({ scholarshipId, compact = false, only }: { scholarshipId?: number; compact?: boolean; only?: string[] }) {
  const { t } = useT();
  const [offers, setOffers] = useState<Offer[]>(DEFAULT_OFFERS);
  useEffect(() => { getOffers().then(setOffers); }, []);
  const href = (o: Offer) => {
    if (o.code === "autonome") return scholarshipId ? `/lettre/${scholarshipId}` : "/questionnaire";
    const q = new URLSearchParams({ offre: o.code });
    if (scholarshipId) q.set("bourse", String(scholarshipId));
    return `/accompagnement?${q}`;
  };
  return (
    <div className={`grid gap-4 ${only && only.length === 2 ? "md:grid-cols-2" : compact ? "md:grid-cols-3" : "lg:grid-cols-3"}`}>
      {offers.filter((o) => !only || only.includes(o.code)).map((o) => (
        <div key={o.code} className={`relative flex flex-col rounded-2xl border p-6 ${o.recommended ? "border-brand/60 bg-card shadow-[0_24px_60px_-30px_rgba(62,224,168,0.45)]" : "border-line bg-card"}`}>
          {o.recommended && <span className="absolute -top-3 left-6 rounded-full bg-mint px-3 py-0.5 text-[11px] font-bold text-[#04140e]">{t("Le plus choisi")}</span>}
          <p className="text-sm font-semibold text-muted">{t(o.name)}</p>
          <p className="mt-2 font-serif text-3xl font-semibold">{t(o.price_label)}</p>
          <p className="mt-2 text-sm text-muted">{t(o.description)}</p>
          <ul className="mt-5 space-y-2 text-sm">
            {o.features.map((f) => <li key={f} className="flex gap-2"><Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-brand" />{t(f)}</li>)}
          </ul>
          <Link href={href(o)} className={`${o.recommended ? "btn-primary" : "btn-ghost"} mt-6 w-full`}>
            {o.code === "autonome" ? t("Je postule moi-même") : t("Choisir {name}", { name: t(o.name) })}
          </Link>
        </div>
      ))}
    </div>
  );
}
