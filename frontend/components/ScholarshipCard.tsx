"use client";
import Link from "next/link";
import { Match, Meta, Scholarship, deadlineInfo, formatAmount, formatDate } from "@/lib/api";
import AddToTracker from "./AddToTracker";
import Flag from "./Flag";
import Icon from "./Icon";
import { useT } from "@/components/LangProvider";
import { countryName } from "@/lib/i18n";

const CHANCE = {
  bonne: { label: "Très compatible", ring: "#3ee0a8", panel: "from-[#0c3a2b] to-[#061a14]" },
  moyenne: { label: "Compatible", ring: "#ffb547", panel: "from-[#2d240f] to-[#120e06]" },
  faible: { label: "À renforcer", ring: "#ff8a5c", panel: "from-[#2e1911] to-[#140a06]" },
};

const DL_STYLE: Record<string, { cls: string; tag?: string }> = {
  expiree: { cls: "border border-danger/40 bg-surface text-danger" },
  urgente: { cls: "bg-warm-soft text-warm", tag: "Urgent" },
  bientot: { cls: "bg-gold-soft text-gold-dark", tag: "Bientôt" },
  ouverte: { cls: "border border-line bg-paper text-muted" },
  inconnue: { cls: "border border-line bg-paper text-muted" },
};

/** Date limite + statut (urgente ≤ 14 j, bientôt ≤ 45 j, clôturée). */
export function DeadlineBadge({ deadline, s }: { deadline: string | null; s?: Scholarship }) {
  const { t, lang } = useT();
  const info = deadlineInfo(s ?? ({ deadline } as Scholarship), lang);
  const st = DL_STYLE[info.status] ?? DL_STYLE.ouverte;
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${st.cls}`}>
      <Icon name="calendar" className="h-3 w-3" />
      {st.tag && <span className="font-semibold">{t(st.tag)} ·</span>}
      {info.label}
    </span>
  );
}

export function ScoreRing({ value, color, size = 76 }: { value: number; color: string; size?: number }) {
  const c = 2 * Math.PI * 15.5;
  return (
    <span className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg viewBox="0 0 36 36" className="absolute inset-0 -rotate-90">
        <circle cx="18" cy="18" r="15.5" fill="none" stroke="rgba(255,255,255,0.14)" strokeWidth="2.6" />
        <circle cx="18" cy="18" r="15.5" fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeDasharray={`${(Math.max(0, Math.min(100, value)) / 100) * c} ${c}`} />
      </svg>
      <span className="font-serif text-xl font-semibold text-white">{value}<span className="text-xs">%</span></span>
    </span>
  );
}

function Initials({ name }: { name: string }) {
  const words = name.replace(/\(.*?\)/g, " ").split(/[\s'’/-]+/).filter((w) => /^[A-ZÀ-Ý]/.test(w) && w.length > 2);
  const ini = (words.length ? words.slice(0, 2).map((w) => w[0]).join("") : name.replace(/[^A-Za-zÀ-ÿ]/g, "").slice(0, 2)) || "B";
  return <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-soft font-serif text-sm font-semibold uppercase text-brand">{ini}</span>;
}

export default function ScholarshipCard({ s, match, meta, loggedIn, lockedScore }: { s: Scholarship; match?: Match; meta?: Meta | null; loggedIn?: boolean; lockedScore?: boolean }) {
  const { t, lang } = useT();
  const countries = s.study_countries.length ? s.study_countries.map((c) => countryName(c, lang, meta?.countries[c])).join(", ") : t("Plusieurs pays");
  const levels = s.levels.map((l) => (meta?.levels[l] ? t(meta.levels[l]) : l).split(" : ").pop()).join(" · ");
  const ch = match?.chance && match.score != null ? CHANCE[match.chance] : null;
  return (
    <article className="card flex overflow-hidden transition hover:shadow-[0_12px_40px_-20px_rgba(18,20,43,0.35)]">
      <div className="flex min-w-0 flex-1 flex-col gap-3 p-5">
        <div className="flex items-start gap-3">
          <Initials name={s.organization} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
              {lockedScore && !match && <Link href="/connexion?mode=inscription" className="rounded-full bg-night px-2 py-0.5 font-semibold text-[#3ee0a8] sm:hidden">{t("Votre score : créez un compte")}</Link>}
              {match && ch && <span className="rounded-full bg-night px-2 py-0.5 font-semibold text-white sm:hidden" style={{ color: ch.ring }}>{match.score} % · {t(ch.label)}</span>}
              {s.kind && s.kind !== "bourse" && <span className="rounded-full bg-brand-soft px-2 py-0.5 font-semibold text-brand">{s.kind_label ? t(s.kind_label) : s.kind === "stage" ? t("Stage") : t("Conférence")}</span>}
              <DeadlineBadge deadline={s.deadline} s={s} />
              {s.full_funding && <span className="rounded-full bg-ok-soft px-2 py-0.5 font-semibold text-ok">{t("Financement complet")}</span>}
            </div>
            <h3 className="mt-1.5 text-lg leading-snug">
              <Link href={`/bourses/${s.id}`} className="hover:text-gold-dark">{s.title}</Link>
            </h3>
            <p className="text-sm text-muted">{s.organization}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-sm text-muted sm:grid-cols-2">
          <span className="flex items-center gap-2">{s.study_countries.length ? <span className="flex shrink-0 items-center gap-0.5">{s.study_countries.slice(0, 3).map((c) => <Flag key={c} code={c} />)}</span> : <Icon name="globe" className="h-4 w-4 shrink-0" />}<span className="truncate">{countries}</span></span>
          <span className="flex items-center gap-2"><Icon name="cap" className="h-4 w-4 shrink-0" /><span className="truncate">{levels || t("Tous niveaux")}</span></span>
          {(s.event_start || s.duration || s.city || s.remote) && (
            <span className="flex items-center gap-2 sm:col-span-2"><Icon name="calendar" className="h-4 w-4 shrink-0" /><span className="truncate">
              {[s.event_start && (s.event_end && s.event_end !== s.event_start ? t("Du {a} au {b}", { a: formatDate(s.event_start, lang), b: formatDate(s.event_end, lang) }) : t("Le {a}", { a: formatDate(s.event_start, lang) })), s.duration, s.remote ? t("En ligne") : s.city].filter(Boolean).join(" · ")}
            </span></span>
          )}
          <span className="flex items-center gap-2 font-medium text-ink"><Icon name="medal" className="h-4 w-4 shrink-0 text-gold-dark" /><span className="truncate">{formatAmount(s, lang)}</span></span>
        </div>

        {match ? (
          (match.reasons.length > 0 || match.gaps.length > 0) && (
            <div className="rounded-xl bg-surface p-3 text-sm">
              {match.reasons.length > 0 && (
                <p className="flex gap-2"><Icon name="sparkle" className="mt-0.5 h-4 w-4 shrink-0 text-gold-dark" /><span><span className="font-semibold">{t("Vos points forts :")} </span>{match.reasons.join(", ")}.</span></p>
              )}
              {match.gaps.length > 0 && <p className="mt-1.5 pl-6 text-warm"><span className="font-semibold">{t("À surveiller :")} </span>{match.gaps.join(" ; ")}.</p>}
            </div>
          )
        ) : (
          <p className="line-clamp-2 text-sm text-muted">{s.summary}</p>
        )}

        <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
          {loggedIn && <AddToTracker scholarshipId={s.id} />}
          {loggedIn && <Link href={`/lettre/${s.id}`} className="btn-ghost px-4 py-2 text-xs">{t("Lettre de motivation")}</Link>}
          <Link href={`/postuler/${s.id}`} className="btn-primary ml-auto px-4 py-2 text-xs">{t("Postuler")} <Icon name="arrow" className="h-3.5 w-3.5" /></Link>
        </div>
      </div>

      {lockedScore && !match && (
        <Link href="/connexion?mode=inscription" className="hidden w-36 shrink-0 flex-col items-center justify-center gap-2 bg-gradient-to-b from-[#13232d] to-[#071017] p-4 text-center text-white sm:flex">
          <span className="grid h-[68px] w-[68px] place-items-center rounded-full border-2 border-dashed border-white/25 font-serif text-xl text-white/60"><span>?<span className="text-xs">%</span></span></span>
          <span className="text-[11px] font-semibold leading-tight text-[#3ee0a8]">{t("Créez un compte pour voir votre score")}</span>
        </Link>
      )}
      {match && ch && (
        <div className={`hidden w-36 shrink-0 flex-col items-center justify-center gap-2 bg-gradient-to-b p-4 text-center sm:flex ${ch.panel}`}>
          <ScoreRing value={match.score ?? 0} color={ch.ring} />
          <span className="text-[11px] font-semibold uppercase tracking-wider text-white/90">{t(ch.label)}</span>
        </div>
      )}
    </article>
  );
}
